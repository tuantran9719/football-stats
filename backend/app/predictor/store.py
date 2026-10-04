"""
Lưu hệ số đã học và nhật ký độ chính xác.

Hai thứ tách riêng:
  - ratings: kết quả học, đọc ra là dùng được ngay, không cần học lại.
  - accuracy: điểm Brier của từng lần huấn luyện, để biết mô hình có
    thật sự khá lên hay không thay vì chỉ tin là nó khá lên.
"""
from __future__ import annotations
import asyncio
import json
import time
from typing import Any, Optional

from ..paths import data_file
from .model import Ratings

_FILE = data_file("predictor.json")
_lock = asyncio.Lock()

# Giữ lại bấy nhiêu lần chấm điểm gần nhất cho mỗi giải.
_HISTORY = 40


def _blank() -> dict[str, Any]:
    return {"ratings": {}, "accuracy": {}}


def _read() -> dict[str, Any]:
    if not _FILE.exists():
        return _blank()
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _blank()


def _write(data: dict[str, Any]) -> None:
    tmp = _FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_FILE)


def _to_dict(r: Ratings) -> dict[str, Any]:
    return {
        "attack": r.attack, "defence": r.defence,
        "home_adv": r.home_adv, "rho": r.rho,
        "matches": r.matches, "base": r.base, "intercept": r.intercept,
    }


def _from_dict(d: dict[str, Any]) -> Ratings:
    return Ratings(
        attack=d.get("attack", {}), defence=d.get("defence", {}),
        home_adv=d.get("home_adv", 0.25), rho=d.get("rho", -0.05),
        matches=d.get("matches", 0), base=d.get("base", 1.35),
        intercept=d.get("intercept", 0.3),
    )


async def get_ratings(league: str) -> Optional[Ratings]:
    async with _lock:
        raw = _read()["ratings"].get(league)
    return _from_dict(raw) if raw else None


async def save_ratings(league: str, r: Ratings, xi: float, reg: float = 0.0) -> None:
    async with _lock:
        data = _read()
        entry = _to_dict(r)
        entry["xi"] = xi
        entry["reg"] = reg
        entry["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        data["ratings"][league] = entry
        _write(data)


async def log_accuracy(
    league: str, brier: float, samples: int,
    xi: float, reg: float = 0.0, baseline: Optional[float] = None,
) -> None:
    async with _lock:
        data = _read()
        hist = data["accuracy"].setdefault(league, [])
        hist.append({
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "brier": round(brier, 4),
            "baseline": round(baseline, 4) if baseline is not None else None,
            "samples": samples,
            "xi": xi,
            "reg": reg,
        })
        del hist[:-_HISTORY]
        _write(data)


async def summary() -> dict[str, Any]:
    """Tình trạng mô hình, để soi qua /api/health hay endpoint riêng."""
    async with _lock:
        data = _read()
    out: dict[str, Any] = {}
    for league, r in data["ratings"].items():
        hist = data["accuracy"].get(league, [])
        out[league] = {
            "teams": len(r.get("attack", {})),
            "matches": r.get("matches", 0),
            "homeAdvantage": round(r.get("home_adv", 0), 3),
            "xi": r.get("xi"),
            "trainedAt": r.get("at"),
            "brier": hist[-1]["brier"] if hist else None,
            "baseline": hist[-1].get("baseline") if hist else None,
            "brierFirst": hist[0]["brier"] if hist else None,
            "runs": len(hist),
        }
    return out
