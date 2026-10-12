"""
Kho chỉ số theo hiệp của những trận đã đá, lưu vĩnh viễn trên đĩa.

VÌ SAO CẦN: thẻ "đọc nhanh" trước mỗi trận lấy phong độ 10 trận gần
nhất của cả hai đội. Mỗi trận cũ ấy lại là một lượt gọi riêng tới nhà
cung cấp để lấy diễn biến rồi mới đếm được bàn/góc/thẻ theo hiệp. Hai
đội là hai mươi lượt gọi, chạy bốn luồng một lúc nên phải năm đợt.

Đo trên máy chủ thật: thẻ ấy mất 2,6 giây với giải quen và 4,6 giây với
giải ít người xem — trong khi lần thứ hai chỉ mất 0,2 giây. Nói cách
khác toàn bộ thời gian chờ nằm ở hai mươi lượt gọi kia, không phải ở
tính toán.

Cache trong bộ nhớ không cứu được: nó chết theo tiến trình, mà mỗi lần
đẩy code lên là container dựng lại từ đầu. Người mở trận đầu tiên sau
mỗi lần deploy luôn phải chờ trọn mấy giây đó.

Kho này ghi xuống đĩa và giữ mãi. Chỉ giữ trận ĐÃ ĐÁ XONG: tỉ số, số
quả phạt góc, số thẻ của một trận đã kết thúc thì vĩnh viễn không đổi
nữa, nên đọc lại từ đĩa luôn đúng. Trận đang đá hoặc chưa đá vẫn đi
đường cũ.

Khoảng 300 byte mỗi trận. Cả 39 giải, mỗi giải vài trăm trận một mùa,
tổng cộng dưới 10 MB — rẻ hơn nhiều so với việc bắt người dùng chờ.

Song song với predictor/results_store.py, chỉ khác phần lưu: kho kia
giữ tỉ số để học hệ số, kho này giữ chi tiết theo hiệp để dựng thẻ
thống kê.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from .models import MatchSplitStats
from .paths import DATA_DIR

_lock = asyncio.Lock()

# Đọc tệp một lần rồi giữ trong bộ nhớ: mỗi lượt dựng thẻ hỏi tới hàng
# chục trận, mở lại tệp JSON từng lần là tự tạo ra điểm nghẽn mới.
_mem: dict[str, dict[str, Any]] = {}


def _file(league: str):
    d = DATA_DIR / "splits"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{league}.json"


def _read(league: str) -> dict[str, Any]:
    cached = _mem.get(league)
    if cached is not None:
        return cached
    p = _file(league)
    data: dict[str, Any] = {}
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
        except (json.JSONDecodeError, OSError):
            data = {}
    _mem[league] = data
    return data


def _write(league: str, data: dict[str, Any]) -> None:
    p = _file(league)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    tmp.replace(p)
    _mem[league] = data


async def get(league: str, external_id: str) -> Optional[MatchSplitStats]:
    """Chỉ số của một trận, None nếu chưa có trong kho."""
    async with _lock:
        raw = _read(league).get(external_id)
    if raw is None:
        return None
    try:
        return MatchSplitStats.model_validate(raw)
    except Exception:
        # Bản ghi hỏng hoặc được ghi bởi phiên bản mô hình cũ: coi như
        # chưa có, đường gọi mạng cũ sẽ lấy lại rồi ghi đè.
        return None


async def get_many(
    league: str, external_ids: list[str],
) -> dict[str, MatchSplitStats]:
    """Lấy nhiều trận trong một lượt mở kho."""
    if not external_ids:
        return {}
    async with _lock:
        data = _read(league)
        raws = {e: data.get(e) for e in external_ids}
    out: dict[str, MatchSplitStats] = {}
    for ext, raw in raws.items():
        if raw is None:
            continue
        try:
            out[ext] = MatchSplitStats.model_validate(raw)
        except Exception:
            continue
    return out


async def put_many(league: str, items: dict[str, MatchSplitStats]) -> int:
    """
    Ghi thêm các trận vào kho. Trả về số trận mới thực sự được thêm.

    Gọi một lần cho cả mẻ chứ không ghi từng trận: ghi tệp là thao tác
    đồng bộ, rải ra từng trận sẽ chặn vòng lặp sự kiện nhiều lần.
    """
    if not items:
        return 0
    async with _lock:
        data = _read(league)
        before = len(data)
        for ext, split in items.items():
            data[ext] = split.model_dump(exclude_none=True)
        _write(league, data)
        return len(data) - before


async def summary() -> dict[str, int]:
    """Số trận đang giữ cho từng giải, để soi qua endpoint tình trạng."""
    d = DATA_DIR / "splits"
    if not d.exists():
        return {}
    out: dict[str, int] = {}
    for p in sorted(d.glob("*.json")):
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            out[p.stem] = len(raw)
        except (json.JSONDecodeError, OSError):
            continue
    return out
