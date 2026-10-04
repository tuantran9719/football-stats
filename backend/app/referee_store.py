"""
Tích luỹ thống kê rút thẻ theo trọng tài, dựa hoàn toàn trên các trận mà
app đã từng xem qua (không có nguồn dữ liệu lịch sử trọng tài nào miễn phí).

Mỗi lần get_match_detail tính xong số thẻ một trận đã kết thúc, cộng dồn
vào đây. Càng nhiều người dùng xem trận, số liệu trọng tài càng chính xác
theo thời gian — không tốn thêm lệnh gọi API nào so với hiện tại.

Lưu bằng một file JSON phẳng thay vì cơ sở dữ liệu thật, vì quy mô nhỏ
(vài trăm trọng tài) và backend hiện chưa dùng database nào khác. Lưu ý:
nếu host trên nền tảng có ổ đĩa tạm thời (một số gói miễn phí của
Railway/Render), file này có thể mất khi redeploy — chấp nhận được vì đây
là số liệu tích luỹ dần, không phải dữ liệu gốc.
"""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import Optional
from .paths import data_file

_PATH = data_file("referee_stats.json")
_lock = asyncio.Lock()


def _load() -> dict:
    if not _PATH.exists():
        return {}
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


async def record_match(referee_name: str, match_id: str, yellow: int, red: int) -> None:
    async with _lock:
        data = _load()
        entry = data.get(referee_name, {"matches": {}})
        # Khoá theo matchId để xem lại trận cũ (cache TTL_MEDIUM) không cộng
        # trùng nhiều lần vào cùng một trận.
        entry["matches"][match_id] = {"yellow": yellow, "red": red}
        data[referee_name] = entry
        _save(data)


async def get_stats(referee_name: str) -> Optional[dict]:
    async with _lock:
        data = _load()
        entry = data.get(referee_name)
        if not entry or not entry.get("matches"):
            return None
        rows = list(entry["matches"].values())
        n = len(rows)
        return {
            "matchesTracked": n,
            "avgYellowCards": sum(r["yellow"] for r in rows) / n,
            "avgRedCards": sum(r["red"] for r in rows) / n,
        }
