"""
Kho kết quả trận đã đá, lưu vĩnh viễn trên đĩa.

VÌ SAO CẦN: trước đây mỗi lượt huấn luyện tải lại lịch 4 mùa của từng
đội từ nhà cung cấp — khoảng 80 lượt gọi cho mỗi giải, lặp lại mỗi 6
tiếng, mãi mãi. Trong đó phần lớn là những trận đá xong từ năm 2023,
vĩnh viễn không bao giờ đổi tỉ số nữa.

Có cache rồi, nhưng cache đặt hạn 6 tiếng đúng bằng chu kỳ huấn luyện
nên nó hết hạn đúng lúc cần dùng lại — tức là chưa từng giúp được gì.
Lại chỉ nằm trong bộ nhớ, khởi động lại là mất sạch.

Kho này sửa cả hai: ghi xuống đĩa, giữ mãi, và chỉ tải thêm phần MỚI.

Chỉ lưu đúng những trường phần huấn luyện cần (mã hai đội, hai tỉ số,
ngày đá) chứ không lưu cả đối tượng trận: khoảng 100 byte mỗi trận,
cả 39 giải chưa tới 4 MB. Logo, đội hình, diễn biến đều không liên
quan tới việc học hệ số.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from ..paths import DATA_DIR

_lock = asyncio.Lock()

# Khoá đặc biệt giữ thông tin về chính kho, không phải một trận.
#
# Cần nó vì nếu chỉ nhìn ngày trận mới nhất thì giải đang nghỉ giữa mùa
# sẽ bị quét lại đúng những ngày trống ấy ở MỌI lượt huấn luyện — mốc
# không bao giờ tiến lên vì không có trận mới để đẩy nó đi.
_META = "_meta"


def _file(league: str):
    d = DATA_DIR / "results"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{league}.json"


def _read(league: str) -> dict[str, dict[str, Any]]:
    p = _file(league)
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write(league: str, data: dict[str, dict[str, Any]]) -> None:
    p = _file(league)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    tmp.replace(p)


async def load(league: str) -> dict[str, dict[str, Any]]:
    """Các trận trong kho. Bản ghi thông tin về kho được lọc ra."""
    async with _lock:
        return {k: v for k, v in _read(league).items() if k != _META}


async def merge(league: str, records: list[dict[str, Any]]) -> int:
    """
    Gộp các trận mới vào kho. Trả về số trận thực sự được thêm.

    Khoá theo mã trận nên gọi lại nhiều lần cũng không nhân đôi dữ liệu;
    một trận có được tải lại thì chỉ ghi đè chính nó.
    """
    if not records:
        return 0
    async with _lock:
        data = _read(league)
        before = len(data)
        for r in records:
            mid = r.get("id")
            if mid:
                data[mid] = r
        _write(league, data)
        return len(data) - before


async def last_date(league: str) -> Optional[str]:
    """Ngày của trận mới nhất trong kho, dạng YYYYMMDD."""
    data = await load(league)
    dates = [r.get("d") for r in data.values() if r.get("d")]
    return max(dates) if dates else None


async def checked_through(league: str) -> Optional[str]:
    """Đã quét tới ngày nào, kể cả những ngày không có trận nào."""
    async with _lock:
        return (_read(league).get(_META) or {}).get("checked")


async def set_checked(league: str, date: str) -> None:
    async with _lock:
        data = _read(league)
        meta = data.get(_META) or {}
        meta["checked"] = date
        data[_META] = meta
        _write(league, data)


async def summary() -> dict[str, int]:
    """Số trận đang giữ cho từng giải, để soi qua endpoint tình trạng."""
    d = DATA_DIR / "results"
    if not d.exists():
        return {}
    out: dict[str, int] = {}
    for p in sorted(d.glob("*.json")):
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            out[p.stem] = len([k for k in raw if k != _META])
        except (json.JSONDecodeError, OSError):
            continue
    return out
