"""
Lưu bộ phân loại đã học và các câu người dùng dạy cho nó.

Hai phần tách riêng, có chủ đích:

  - examples: câu hỏi thật kèm ý định ĐÃ ĐƯỢC NGƯỜI DÙNG XÁC NHẬN. Đây
    là tài sản thật sự — câu mẫu tôi viết sẵn chỉ là mồi, còn cách người
    Việt thật sự gõ thì chỉ người dùng mới dạy được.
  - model: trọng số đã học, để khởi động lại không phải học lại từ đầu.

Chống đầu độc dữ liệu: bộ phân loại mới chỉ được NHẬN nếu nó chấm trên
phần giữ lại không tệ hơn bộ đang chạy. Không có chốt này thì chỉ cần
vài chục câu rác là bot dốt đi mà không ai phát hiện ra, vì không có
chỗ nào báo lỗi cả — nó chỉ đơn giản là trả lời sai nhiều hơn.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict
from typing import Any, Optional

from ..paths import data_file
from .classifier import Model, train
from .intents import ALL_INTENTS

_FILE = data_file("chat_model.json")
_lock = asyncio.Lock()

# Số câu người dùng dạy giữ lại tối đa cho MỖI ý định. Giữ hết thì một
# ý định hay gặp sẽ lấn át hẳn các ý định khác và bộ phân loại học
# thành "cứ đoán nhóm đông nhất là xong".
MAX_PER_INTENT = 400

# Câu quá ngắn hoặc quá dài đều không dạy được gì: "ok" không có thông
# tin, còn một đoạn văn dài thường là người dùng dán nhầm.
MIN_LEN = 2
MAX_LEN = 160

_cache: Optional[Model] = None


def _blank() -> dict[str, Any]:
    return {"examples": [], "model": None, "history": []}


def _read() -> dict[str, Any]:
    if not _FILE.exists():
        return _blank()
    try:
        data = json.loads(_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _blank()
    for key, default in _blank().items():
        data.setdefault(key, default)
    return data


def _write(data: dict[str, Any]) -> None:
    tmp = _FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_FILE)


def _to_model(raw: dict[str, Any]) -> Model:
    return Model(
        weights=raw.get("weights", {}),
        bias=raw.get("bias", {}),
        intents=raw.get("intents", []),
        trained_on=raw.get("trained_on", 0),
        accuracy=raw.get("accuracy", 0.0),
    )


def _from_model(m: Model) -> dict[str, Any]:
    d = asdict(m)
    # errors chỉ để soi lúc chỉnh câu mẫu, không cần lưu.
    d.pop("errors", None)
    return d


async def get_model() -> Model:
    """
    Bộ phân loại đang dùng. Chưa có thì học từ câu mẫu rồi lưu lại.

    Giữ trong bộ nhớ sau lần đọc đầu: mỗi câu hỏi đều cần nó, mà đọc
    lại file JSON vài trăm KB cho từng câu thì phí vô ích.
    """
    global _cache
    if _cache is not None:
        return _cache

    async with _lock:
        if _cache is not None:
            return _cache
        raw = _read().get("model")
        if raw and raw.get("intents"):
            _cache = _to_model(raw)
            return _cache

    # Học lần đầu tốn vài giây nên đẩy sang luồng khác, không chặn
    # vòng lặp sự kiện đang phục vụ các request khác.
    from .classifier import seed_model
    model = await asyncio.to_thread(seed_model)
    async with _lock:
        data = _read()
        data["model"] = _from_model(model)
        data["history"].append({
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "accuracy": round(model.accuracy, 4),
            "examples": 0,
            "note": "mồi từ câu mẫu",
        })
        _write(data)
        _cache = model
    return model


async def teach(question: str, intent: str) -> bool:
    """
    Ghi lại một câu hỏi thật kèm ý định người dùng đã chọn.

    Trả về True nếu câu được nhận. Không học lại ngay tại đây: học lại
    mất vài giây, mà người dùng đang chờ câu trả lời.
    """
    question = (question or "").strip()
    if intent not in ALL_INTENTS:
        return False
    if not (MIN_LEN <= len(question) <= MAX_LEN):
        return False

    async with _lock:
        data = _read()
        key = question.lower()
        same = [e for e in data["examples"] if e.get("intent") == intent]
        if any(e.get("q", "").lower() == key for e in same):
            return True
        if len(same) >= MAX_PER_INTENT:
            return False
        data["examples"].append({
            "q": question, "intent": intent,
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        _write(data)
    return True


async def retrain() -> dict[str, Any]:
    """
    Học lại từ câu mẫu CỘNG những câu người dùng đã dạy.

    Chỉ thay bộ đang chạy khi bộ mới chấm không tệ hơn. Ngưỡng nới một
    chút (0.02) vì phần giữ lại nhỏ nên con số dao động nhẹ giữa các
    lần chia; siết quá thì không bao giờ nhận được cải tiến thật.
    """
    global _cache
    from .intents import SEEDS

    async with _lock:
        data = _read()
        taught = list(data["examples"])
        current_acc = (data.get("model") or {}).get("accuracy", 0.0)

    seen: set[str] = set()
    examples: list[tuple[str, str]] = []
    for intent, texts in SEEDS.items():
        for text in texts:
            key = text.strip().lower()
            if key not in seen:
                seen.add(key)
                examples.append((text, intent))
    for e in taught:
        key = (e.get("q") or "").strip().lower()
        if key and key not in seen and e.get("intent") in ALL_INTENTS:
            seen.add(key)
            examples.append((e["q"], e["intent"]))

    model = await asyncio.to_thread(train, examples)
    accepted = model.accuracy >= current_acc - 0.02

    async with _lock:
        data = _read()
        data["history"].append({
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "accuracy": round(model.accuracy, 4),
            "previous": round(current_acc, 4),
            "examples": len(taught),
            "accepted": accepted,
        })
        del data["history"][:-40]
        if accepted:
            data["model"] = _from_model(model)
        _write(data)
        if accepted:
            _cache = model

    return {
        "accepted": accepted,
        "accuracy": round(model.accuracy, 4),
        "previous": round(current_acc, 4),
        "taught": len(taught),
        "examples": len(examples),
    }


async def summary() -> dict[str, Any]:
    """Tình trạng bộ phân loại, để theo dõi qua endpoint riêng."""
    async with _lock:
        data = _read()
    model = data.get("model") or {}
    per_intent: dict[str, int] = {}
    for e in data["examples"]:
        per_intent[e.get("intent", "?")] = per_intent.get(e.get("intent", "?"), 0) + 1
    return {
        "accuracy": model.get("accuracy"),
        "trainedOn": model.get("trained_on"),
        "intents": len(model.get("intents", [])),
        "taught": len(data["examples"]),
        "taughtPerIntent": per_intent,
        "history": data["history"][-10:],
    }
