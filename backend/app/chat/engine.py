"""
Ghép phân loại + rút tham số + trả lời thành một lượt hỏi đáp.

Luồng một câu hỏi gõ tay:

    câu gõ → chuẩn hoá → phân loại → đủ tin? → rút tham số → trả lời
                                   ↘ không đủ tin → hỏi lại kèm 3 lựa chọn

Nhánh "hỏi lại" mới là phần đáng giá. Người dùng chạm vào một lựa chọn
thì vừa nhận được câu trả lời, vừa dạy cho bộ phân loại biết câu vừa
gõ thuộc nhóm nào — nhãn huấn luyện tự đến mà không ai phải ngồi gán
tay, và nó là nhãn từ chính người gõ câu đó nên đúng hơn bất kỳ ai đoán
hộ.

Nút gợi ý bấm thẳng thì KHÔNG qua bộ phân loại: đã biết chắc ý định
rồi, cho nó đi vòng qua chỗ có thể đoán sai là tự chuốc lỗi.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import intents as I
from . import store
from .answer import Answer, MatchContext, build
from .classifier import classify
from .slots import extract

# Nút gợi ý hiện sẵn lúc mới mở khung chat. Chọn theo thứ tự người ta
# hay hỏi nhất, và cố ý dừng ở sáu nút: nhiều hơn thì thành bảng chọn,
# mất tác dụng "nhìn phát biết hỏi được gì".
STARTERS = (I.OUTCOME, I.TOTAL_GOALS, I.OVER_UNDER, I.BTTS, I.CORNERS, I.CARDS)

# Dưới mức này thì vẫn trả lời, nhưng mời người dùng sửa nếu hiểu sai.
# Đặt khá cao so với ngưỡng dám trả lời (0.34) là có chủ đích: chỗ tốn
# kém nhất không phải lúc bot im lặng, mà lúc bot trả lời nhầm câu một
# cách tự tin. Mời sửa ở cả vùng "khá chắc" thì bắt được những lần đó.
SURE_ENOUGH = 0.75

# Gợi ý tiếp theo sau khi đã trả lời, theo kiểu "hỏi cái này rồi thường
# hỏi tiếp cái kia". Không có trong bảng thì dùng STARTERS.
FOLLOW_UP = {
    I.OUTCOME: (I.SCORE, I.HANDICAP, I.FORM),
    I.SCORE: (I.OUTCOME, I.TOTAL_GOALS, I.BTTS),
    I.TOTAL_GOALS: (I.OVER_UNDER, I.BTTS, I.HALVES),
    I.OVER_UNDER: (I.TOTAL_GOALS, I.BTTS, I.TEAM_GOALS),
    I.BTTS: (I.TEAM_GOALS, I.CLEAN_SHEET, I.OVER_UNDER),
    I.HANDICAP: (I.OUTCOME, I.SCORE, I.TEAM_GOALS),
    I.TEAM_GOALS: (I.CLEAN_SHEET, I.BTTS, I.FORM),
    I.CLEAN_SHEET: (I.TEAM_GOALS, I.BTTS, I.OUTCOME),
    I.CORNERS: (I.CARDS, I.TOTAL_GOALS, I.FORM),
    I.CARDS: (I.CORNERS, I.TOTAL_GOALS, I.FORM),
    I.HALVES: (I.TOTAL_GOALS, I.OVER_UNDER, I.FORM),
    I.FORM: (I.H2H, I.OUTCOME, I.STANDINGS),
    I.H2H: (I.FORM, I.OUTCOME, I.STANDINGS),
    I.STANDINGS: (I.FORM, I.H2H, I.OUTCOME),
    I.KICKOFF: (I.OUTCOME, I.FORM, I.INJURIES),
    I.INJURIES: (I.FORM, I.OUTCOME, I.KICKOFF),
    I.MODEL_INFO: (I.OUTCOME, I.TOTAL_GOALS, I.FORM),
    I.OTHER: STARTERS[:3],
}


@dataclass
class ChatReply:
    intent: str
    confidence: float
    text: str
    action: Optional[str] = None
    """Mã ý định để giao diện tự dịch thành nhãn nút."""
    suggestions: list[str] = field(default_factory=list)
    """True khi bot không chắc và đang chờ người dùng chọn giúp — giao
    diện dùng cờ này để gửi lại câu đã chọn về cho bot học."""
    asking_back: bool = False
    """
    True khi bot ĐÃ trả lời nhưng chưa thật chắc mình hiểu đúng.

    Có cờ này thì giao diện mời người dùng sửa bằng một chạm. Đây mới
    là nguồn nhãn huấn luyện chính: nhánh "hỏi lại" chỉ nổ khi bot
    hoang mang hẳn, vốn hiếm, còn nhánh này bắt được đúng vùng nguy
    hiểm — bot đủ tự tin để trả lời nhưng chưa đủ để nên tin.
    """
    correctable: bool = False


async def reply(
    ctx: MatchContext,
    lang: str = "vi",
    question: Optional[str] = None,
    intent: Optional[str] = None,
) -> ChatReply:
    """
    Trả lời một lượt. Truyền `intent` khi người dùng bấm nút gợi ý,
    truyền `question` khi người dùng gõ tay.
    """
    slots = extract(question or "", ctx.home_full, ctx.away_full, ctx.home, ctx.away)

    # Nhánh bấm nút: biết chắc ý định, đi thẳng tới câu trả lời.
    if intent and intent in I.ALL_INTENTS:
        answer = build(intent, slots, ctx, lang)
        return ChatReply(
            intent=intent, confidence=1.0, text=answer.text,
            action=answer.action,
            suggestions=list(FOLLOW_UP.get(intent, STARTERS)),
        )

    if not (question or "").strip():
        return ChatReply(
            intent=I.UNKNOWN, confidence=0.0,
            text=build(I.OTHER, slots, ctx, lang).text,
            suggestions=list(STARTERS), asking_back=True,
        )

    model = await store.get_model()
    guess, confidence, ranked = classify(model, question or "")

    # Câu nhắc đích danh MỘT đội mà lại hỏi về bàn thắng thì gần như
    # chắc chắn hỏi riêng đội đó, không phải tổng cả trận. Bộ phân loại
    # không thấy được điều này vì tên đội đổi theo từng trận nên không
    # bao giờ nằm trong câu mẫu; phần rút tham số thì thấy. Để phần
    # thấy được sửa cho phần không thấy.
    if guess == I.TOTAL_GOALS and slots.side is not None:
        guess = I.TEAM_GOALS

    out_of_scope = guess == I.OTHER and confidence >= I.MIN_CONFIDENCE
    unsure = guess == I.UNKNOWN or confidence < I.MIN_CONFIDENCE

    if out_of_scope or unsure:
        if out_of_scope or confidence < 0.15:
            # Câu lạc đề hẳn, hoặc lạ tới mức thứ hạng các nhóm chỉ là
            # nhiễu — đưa bộ nút mặc định còn hơn ba cái tên bốc ngẫu
            # nhiên, vốn làm người dùng tưởng bot hiểu nhầm chứ không
            # phải không hiểu.
            options = list(STARTERS[:3])
        else:
            # Bỏ nhóm "ngoài phạm vi" ra khỏi lựa chọn: đưa nó lên thì
            # chẳng khác gì mời người ta bấm vào "không có gì cả".
            options = [i for i, _ in ranked if i not in (I.OTHER, I.UNKNOWN)][:3]
            if len(options) < 3:
                options += [i for i in STARTERS if i not in options]
        answer = build(I.OTHER, slots, ctx, lang)
        return ChatReply(
            intent=I.UNKNOWN, confidence=round(confidence, 3),
            text=answer.text, suggestions=options[:3],
            # Chỉ nhờ người dùng dạy khi bot THẬT SỰ phân vân. Câu lạc
            # đề hẳn thì không có gì để học, mà nhận bừa nhãn cho nó
            # còn làm bẩn dữ liệu huấn luyện.
            asking_back=not out_of_scope,
        )

    answer = build(guess, slots, ctx, lang)
    return ChatReply(
        intent=guess, confidence=round(confidence, 3),
        text=answer.text, action=answer.action,
        suggestions=list(FOLLOW_UP.get(guess, STARTERS)),
        correctable=confidence < SURE_ENOUGH,
    )
