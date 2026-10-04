"""
Nhận định trận đấu ngắn gọn bằng AI (Claude Haiku), sinh MỘT LẦN cho mỗi
cặp (trận, ngôn ngữ) rồi lưu cache dùng chung cho mọi người xem — tuyệt
đối không gọi AI riêng cho từng lượt xem, nếu không chi phí sẽ tăng theo
số người dùng thay vì theo số trận.

Hỗ trợ hai nhà cung cấp, chọn theo key nào có trong .env — ưu tiên
Anthropic nếu có cả hai, vì đó là hướng chính thức lâu dài; Gemini có gói
miễn phí nên hợp để test trước khi nạp credit Anthropic.

Không có key nào thì trả về None, không làm hỏng phần còn lại của app.
"""
from __future__ import annotations
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Optional

import httpx

from .models import AiPrediction, Match, MatchSplitStats, StatCardDto
from .paths import data_file

_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

_GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

_PATH = data_file("ai_analysis_cache.json")
_lock = asyncio.Lock()

# "Cầu chì" tạm ngưng gọi một nhà cung cấp sau khi nó vừa báo lỗi không thể
# tự khỏi trong vài phút tới (hết credit, hết quota ngày) — tránh mỗi trang
# chi tiết trận đều phải chờ hết round-trip TCP + đợi (sleep) rồi mới thất
# bại, gây cảm giác trang tải chậm dù AI chắc chắn sẽ lỗi.
_anthropic_backoff_until = 0.0
_gemini_backoff_until = 0.0
_BACKOFF_SECONDS = 300


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


def _build_prompt(
    match: Match, split: MatchSplitStats, lang: str,
    home_cards: Optional[list[StatCardDto]] = None,
    away_cards: Optional[list[StatCardDto]] = None,
    window: int = 10,
) -> str:
    home, away = match.home.name, match.away.name
    goals = split.goals.full
    cards = split.cards.full
    played = match.status == "finished"

    if lang == "en":
        if played:
            facts = (
                f"{home} {int(goals.home)} - {int(goals.away)} {away}. "
                f"Yellow cards: {home} {cards.home.yellow}, {away} {cards.away.yellow}. "
                f"Red cards: {home} {cards.home.red}, {away} {cards.away.red}."
            )
            task = "Write a short, engaging 2-3 sentence recap of this match based only on the facts above."
        elif home_cards and away_cards:
            facts = (
                f"Upcoming match: {home} vs {away}. Last {window} matches average — "
                f"{home}: {_avg(home_cards, 'goalsFor'):.1f} goals for, {_avg(home_cards, 'goalsAgainst'):.1f} "
                f"goals against, {_avg(home_cards, 'corners'):.1f} corners, {_avg(home_cards, 'yellowCards'):.1f} "
                f"yellow cards per match. {away}: {_avg(away_cards, 'goalsFor'):.1f} goals for, "
                f"{_avg(away_cards, 'goalsAgainst'):.1f} goals against, {_avg(away_cards, 'corners'):.1f} corners, "
                f"{_avg(away_cards, 'yellowCards'):.1f} yellow cards per match."
            )
            task = "Write a short, insightful 2-3 sentence preview referencing this recent form data (e.g. attack vs defense strength)."
        else:
            facts = f"Upcoming match: {home} vs {away}."
            task = "Write a short, neutral 2-3 sentence preview teaser for this upcoming match. Do not invent stats or predict a scoreline."
        return f"{facts}\n\n{task} Keep it concise, no more than 3 sentences, plain text, no markdown."

    if played:
        facts = (
            f"{home} {int(goals.home)} - {int(goals.away)} {away}. "
            f"Thẻ vàng: {home} {cards.home.yellow}, {away} {cards.away.yellow}. "
            f"Thẻ đỏ: {home} {cards.home.red}, {away} {cards.away.red}."
        )
        task = "Viết một đoạn nhận định ngắn gọn (2-3 câu) tóm tắt trận đấu này, chỉ dựa trên số liệu trên."
    elif home_cards and away_cards:
        facts = (
            f"Trận sắp diễn ra: {home} vs {away}. Trung bình {window} trận gần nhất — "
            f"{home}: {_avg(home_cards, 'goalsFor'):.1f} bàn thắng, {_avg(home_cards, 'goalsAgainst'):.1f} bàn thua, "
            f"{_avg(home_cards, 'corners'):.1f} phạt góc, {_avg(home_cards, 'yellowCards'):.1f} thẻ vàng mỗi trận. "
            f"{away}: {_avg(away_cards, 'goalsFor'):.1f} bàn thắng, {_avg(away_cards, 'goalsAgainst'):.1f} bàn thua, "
            f"{_avg(away_cards, 'corners'):.1f} phạt góc, {_avg(away_cards, 'yellowCards'):.1f} thẻ vàng mỗi trận."
        )
        task = "Viết một đoạn nhận định ngắn gọn (2-3 câu), có nhắc đến số liệu phong độ trên (ví dụ sức tấn công, hàng thủ đội nào chắc chắn hơn)."
    else:
        facts = f"Trận sắp diễn ra: {home} vs {away}."
        task = "Viết một đoạn giới thiệu ngắn gọn (2-3 câu) cho trận sắp diễn ra này, giọng trung lập. Không bịa số liệu hay dự đoán tỷ số."
    return f"{facts}\n\n{task} Ngắn gọn, tối đa 3 câu, văn bản thuần, không dùng markdown."


async def _call_anthropic(prompt: str, client: httpx.AsyncClient) -> str:
    res = await client.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": _ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": _ANTHROPIC_MODEL,
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    res.raise_for_status()
    body = res.json()
    return "".join(
        block.get("text", "") for block in body.get("content", [])
        if block.get("type") == "text"
    ).strip()


async def _call_gemini(prompt: str, client: httpx.AsyncClient) -> str:
    res = await client.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{_GEMINI_MODEL}:generateContent",
        params={"key": _GEMINI_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            # thinkingBudget:0 tắt bước "suy nghĩ" ẩn của model — nếu bật,
            # nó ăn gần hết maxOutputTokens trước khi kịp trả lời, khiến
            # câu trả lời bị cắt cụt giữa chừng (đã gặp thực tế khi test).
            "generationConfig": {
                "maxOutputTokens": 300,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        },
    )
    res.raise_for_status()
    body = res.json()
    candidates = body.get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


async def _call_ai(prompt: str) -> str:
    """Ưu tiên Anthropic; nếu lỗi (ví dụ chưa nạp credit) mà có sẵn key
    Gemini thì tự chuyển sang Gemini, không cần đổi cấu hình tay. Khi nạp
    credit Anthropic xong, lần gọi kế tiếp tự thành công ngay từ bước đầu,
    không còn rơi xuống Gemini nữa.

    Mỗi nhà cung cấp có "cầu chì": vừa lỗi kiểu không tự khỏi trong vài
    phút (hết credit, hết quota ngày) thì bỏ qua hẳn lệnh gọi mạng cho các
    request tiếp theo trong lúc cầu chì còn hiệu lực, thay vì bắt người
    dùng chờ round-trip rồi mới nhận lỗi giống hệt lần trước."""
    global _anthropic_backoff_until, _gemini_backoff_until
    now = time.monotonic()
    text = ""
    async with httpx.AsyncClient(timeout=20.0) as client:
        if _ANTHROPIC_KEY and now >= _anthropic_backoff_until:
            try:
                text = await _call_anthropic(prompt, client)
            except Exception:
                text = ""
                _anthropic_backoff_until = time.monotonic() + _BACKOFF_SECONDS
        if not text and _GEMINI_KEY and now >= _gemini_backoff_until:
            try:
                text = await _call_gemini(prompt, client)
            except httpx.HTTPStatusError as e:
                text = ""
                if e.response.status_code == 503:
                    # "Quá tải" tạm thời — đáng thử lại một lần sau khoảng
                    # nghỉ ngắn, không cần bật cầu chì.
                    await asyncio.sleep(1.5)
                    try:
                        text = await _call_gemini(prompt, client)
                    except Exception:
                        text = ""
                else:
                    # 429 hết quota ngày, 4xx khác... đều không tự khỏi
                    # trong vài phút tới — bật cầu chì luôn.
                    _gemini_backoff_until = time.monotonic() + _BACKOFF_SECONDS
            except Exception:
                text = ""
                _gemini_backoff_until = time.monotonic() + _BACKOFF_SECONDS
    return text


async def _cached_call(cache_key: str, prompt: str) -> Optional[str]:
    async with _lock:
        data = _load()
        cached = data.get(cache_key)
    if cached:
        return cached

    text = await _call_ai(prompt)
    if not text:
        return None

    async with _lock:
        data = _load()
        data[cache_key] = text
        _save(data)
    return text


async def get_analysis(
    match: Match, split: MatchSplitStats, lang: str,
    home_cards: Optional[list[StatCardDto]] = None,
    away_cards: Optional[list[StatCardDto]] = None,
    window: int = 10,
) -> Optional[str]:
    if not _ANTHROPIC_KEY and not _GEMINI_KEY:
        return None
    cache_key = f"{match.id}:{lang}:{match.status}"
    prompt = _build_prompt(match, split, lang, home_cards, away_cards, window)
    return await _cached_call(cache_key, prompt)


def _avg(cards: list[StatCardDto], key: str) -> float:
    return next((c.stats.avgFull for c in cards if c.key == key), 0.0)


def _build_prediction_prompt(
    match: Match, home_cards: list[StatCardDto], away_cards: list[StatCardDto],
    window: int, lang: str,
) -> str:
    home, away = match.home.name, match.away.name
    gf_h, ga_h = _avg(home_cards, "goalsFor"), _avg(home_cards, "goalsAgainst")
    co_h, yc_h = _avg(home_cards, "corners"), _avg(home_cards, "yellowCards")
    gf_a, ga_a = _avg(away_cards, "goalsFor"), _avg(away_cards, "goalsAgainst")
    co_a, yc_a = _avg(away_cards, "corners"), _avg(away_cards, "yellowCards")

    if lang == "en":
        return (
            f"Last {window} matches average — {home}: {gf_h:.1f} goals for, {ga_h:.1f} goals against, "
            f"{co_h:.1f} corners, {yc_h:.1f} yellow cards per match. "
            f"{away}: {gf_a:.1f} goals for, {ga_a:.1f} goals against, {co_a:.1f} corners, "
            f"{yc_a:.1f} yellow cards per match.\n\n"
            f"Based only on these stats, predict the final score, total corners and total yellow "
            f"cards for {home} vs {away}. Reply with ONLY a JSON object, no other text, no markdown "
            f'fences, exactly in this shape: {{"homeScore": <int>, "awayScore": <int>, "corners": <int>, '
            f'"yellowCards": <int>, "note": "<one short sentence, max 20 words>"}}'
        )

    return (
        f"Trung bình {window} trận gần nhất — {home}: {gf_h:.1f} bàn thắng, {ga_h:.1f} bàn thua, "
        f"{co_h:.1f} phạt góc, {yc_h:.1f} thẻ vàng mỗi trận. "
        f"{away}: {gf_a:.1f} bàn thắng, {ga_a:.1f} bàn thua, {co_a:.1f} phạt góc, "
        f"{yc_a:.1f} thẻ vàng mỗi trận.\n\n"
        f"Chỉ dựa trên số liệu trên, dự đoán tỷ số chung cuộc, tổng phạt góc, tổng thẻ vàng cho trận "
        f"{home} vs {away}. CHỈ trả lời bằng một object JSON, không thêm chữ nào khác, không dùng "
        f'markdown, đúng khuôn sau: {{"homeScore": <số nguyên>, "awayScore": <số nguyên>, '
        f'"corners": <số nguyên>, "yellowCards": <số nguyên>, "note": "<1 câu ngắn, tối đa 20 từ>"}}'
    )


def _parse_prediction_json(raw: str) -> Optional[dict]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


async def get_prediction(
    match: Match, home_cards: list[StatCardDto], away_cards: list[StatCardDto],
    window: int, lang: str,
) -> Optional[AiPrediction]:
    if not _ANTHROPIC_KEY and not _GEMINI_KEY:
        return None
    if match.status != "scheduled":
        return None

    cache_key = f"predict:{match.id}:{lang}"
    async with _lock:
        cached = _load().get(cache_key)
    if cached:
        try:
            return AiPrediction(**cached)
        except Exception:
            pass

    prompt = _build_prediction_prompt(match, home_cards, away_cards, window, lang)
    raw = await _call_ai(prompt)
    if not raw:
        return None
    parsed = _parse_prediction_json(raw)
    if not parsed:
        return None
    try:
        prediction = AiPrediction(**parsed)
    except Exception:
        return None

    async with _lock:
        data = _load()
        data[cache_key] = prediction.model_dump()
        _save(data)
    return prediction
