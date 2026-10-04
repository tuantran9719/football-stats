"""
Cache trong bộ nhớ. Cổng lại từ apps/api/src/cache.ts bản Node trước đây.

Trận đã đá xong không đổi nữa nên giữ lâu, dữ liệu đang diễn ra giữ ngắn.

Ba cơ chế thêm vào khi làm tính năng tỉ số trực tiếp, đều nhằm một mục
đích: ESPN là API không chính thức, bị gọi dày là ăn 429 hoặc bị chặn IP
tạm thời. Mỗi cơ chế chặn một kiểu gây tải khác nhau.

  1. Gộp lượt gọi trùng (single-flight). Mười người cùng mở app đúng lúc
     cache vừa hết hạn thì chỉ một lượt gọi ESPN thật sự chạy, chín người
     còn lại chờ chung kết quả đó. Không có bước này, cứ mỗi lần cache hết
     hạn là ESPN ăn nguyên một chùm request giống hệt nhau.

  2. Giữ lại bản cũ (stale). Hết hạn không có nghĩa là xóa. ESPN lỗi hoặc
     trả 429 thì trả bản cũ kèm nhãn stale, còn hơn là ném lỗi ra màn hình.
     Bản cũ chỉ bị bỏ hẳn sau STALE_GRACE.

  3. Xê dịch hạn dùng (jitter). Mười hai giải cùng được nạp một lượt thì
     cũng hết hạn cùng một giây, tạo ra đúng cái chùm request ở mục 1
     nhưng theo chu kỳ. Cộng thêm 0-20% ngẫu nhiên để chúng lệch nhau dần.

  4. Hết hạn thì trả bản cũ NGAY rồi làm mới ở nền (stale-while-
     revalidate). Đây là thứ quyết định cảm giác nhanh chậm của app.

     Trang chủ ở chế độ "tất cả các giải" cần dữ liệu của 12 giải, mà
     ESPN mỗi lượt gọi chỉ trả về một giải — đo được ~10 giây khi cache
     nguội. Dữ liệu hôm nay lại chỉ giữ được 60 giây, nên nếu chờ nạp
     xong mới trả lời thì cứ cách một phút lại có một người phải ngồi
     chờ trọn 10 giây đó.

     Trả bản cũ trước thì chỉ đúng người đầu tiên trong đời phải chờ;
     những người sau luôn nhận ngay lập tức, dữ liệu chậm nhất là cũ hơn
     vài chục giây — với bảng tỉ số thì hoàn toàn chấp nhận được, và
     phần tỉ số trực tiếp vốn đã có vòng cập nhật riêng.
"""
from __future__ import annotations
import asyncio
import random
import time
from typing import Awaitable, Callable, Optional, TypeVar

T = TypeVar("T")

TTL_LIVE = 15
TTL_SHORT = 60
TTL_MEDIUM = 10 * 60
TTL_LONG = 6 * 60 * 60

# Sau khi hết hạn, bản cũ còn được giữ thêm chừng này.
#
# Một tiếng chứ không phải mười lăm phút: bản cũ là thứ giúp người dùng
# không phải ngồi chờ (xem mục 4 ở đầu file), nên nó cần sống lâu hơn
# khoảng nghỉ giữa hai lần ai đó mở app. Hết một tiếng không ai vào thì
# người tiếp theo đành chờ một lần.
STALE_GRACE = 60 * 60


class _Entry:
    __slots__ = ("value", "expires_at", "drop_at")

    def __init__(self, value: object, ttl: int) -> None:
        self.value = value
        self.touch(ttl)

    def touch(self, ttl: int) -> None:
        now = time.time()
        # Jitter dương: không bao giờ ngắn hơn ttl yêu cầu, chỉ dài thêm.
        self.expires_at = now + ttl * (1.0 + random.random() * 0.2)
        self.drop_at = self.expires_at + STALE_GRACE


_store: dict[str, _Entry] = {}
_inflight: dict[str, asyncio.Future] = {}
# Giữ tham chiếu tới các lượt làm mới chạy nền; không giữ thì Python có
# thể thu gom giữa chừng và bản cũ không bao giờ được thay.
_refreshing: set[asyncio.Task] = set()
_stats = {
    "hits": 0, "misses": 0, "stale_served": 0, "coalesced": 0, "bg_refresh": 0,
}


def _fresh(key: str) -> Optional[_Entry]:
    e = _store.get(key)
    if e and e.expires_at > time.time():
        return e
    return None


def _stale(key: str) -> Optional[_Entry]:
    e = _store.get(key)
    if e and e.drop_at > time.time():
        return e
    if e:
        _store.pop(key, None)
    return None


async def _load_once(
    key: str, load: Callable[[], Awaitable[T]], ttl_of: Callable[[T], int],
) -> T:
    """Chạy load đúng một lần cho mỗi key, ai tới sau thì chờ ké."""
    running = _inflight.get(key)
    if running is not None:
        _stats["coalesced"] += 1
        return await asyncio.shield(running)

    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    _inflight[key] = fut
    try:
        value = await load()
    except BaseException as exc:
        if not fut.done():
            fut.set_exception(exc)
        # Không để future lỗi nổi lên dưới dạng "exception was never
        # retrieved" khi tất cả bên chờ đều đã bỏ đi.
        fut.exception()
        raise
    else:
        _store[key] = _Entry(value, ttl_of(value))
        if not fut.done():
            fut.set_result(value)
        return value
    finally:
        _inflight.pop(key, None)


def _refresh_in_background(
    key: str, load: Callable[[], Awaitable[T]], ttl_of: Callable[[T], int],
) -> None:
    """Làm mới một key ở nền. Đang có lượt chạy rồi thì thôi."""
    if key in _inflight:
        return
    _stats["bg_refresh"] += 1

    async def run() -> None:
        try:
            await _load_once(key, load, ttl_of)
        except Exception:
            # Nguồn lỗi thì giữ nguyên bản cũ; lần sau sẽ thử lại.
            pass

    task = asyncio.ensure_future(run())
    _refreshing.add(task)
    task.add_done_callback(_refreshing.discard)


async def cached_dynamic(
    key: str, load: Callable[[], Awaitable[T]], ttl_of: Callable[[T], int],
) -> T:
    """
    Như cached nhưng thời hạn được tính từ chính kết quả trả về. Dùng cho
    danh sách trận: hễ trong đó có trận đang đá thì giữ 15 giây, còn lại
    giữ lâu hơn.
    """
    hit = _fresh(key)
    if hit is not None:
        _stats["hits"] += 1
        return hit.value  # type: ignore[return-value]

    # Hết hạn nhưng còn trong thời gian ân hạn: trả ngay bản cũ, việc nạp
    # lại để nền lo. Xem mục 4 ở đầu file về lý do.
    stale = _stale(key)
    if stale is not None:
        _stats["stale_served"] += 1
        _refresh_in_background(key, load, ttl_of)
        return stale.value  # type: ignore[return-value]

    # Chưa từng có dữ liệu cho key này thì đành chờ.
    _stats["misses"] += 1
    return await _load_once(key, load, ttl_of)


async def cached(key: str, ttl_seconds: int, load: Callable[[], Awaitable[T]]) -> T:
    return await cached_dynamic(key, load, lambda _v: ttl_seconds)


def invalidate(prefix: str) -> int:
    """Xóa mọi key bắt đầu bằng prefix. Trả về số mục đã xóa."""
    keys = [k for k in _store if k.startswith(prefix)]
    for k in keys:
        _store.pop(k, None)
    return len(keys)


def cache_stats() -> dict:
    now = time.time()
    alive = sum(1 for e in _store.values() if e.expires_at > now)
    total = _stats["hits"] + _stats["misses"]
    return {
        "entries": len(_store),
        "alive": alive,
        "stale": len(_store) - alive,
        "inflight": len(_inflight),
        "hitRate": round(_stats["hits"] / total, 3) if total else None,
        **_stats,
    }
