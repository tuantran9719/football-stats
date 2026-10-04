"""
Dựng câu trả lời từ con số của mô hình.

Nguyên tắc xuyên suốt: MỌI con số trong câu trả lời đều đọc ra từ bảng
xác suất của mô hình Poisson hoặc từ bảng phong độ — không có chỗ nào
sinh chữ tự do. Nhờ vậy câu trả lời của bot không bao giờ lệch với con
số hiển thị trên thẻ dự đoán ngay phía trên, vì cả hai đọc chung một
nguồn. Đây chính là thứ mà một bot viết bằng AI không bảo đảm được.

Thiếu dữ liệu thì NÓI LÀ THIẾU. Mô hình chưa học giải đó, hoặc nguồn
không có số liệu chấn thương, thì trả lời thẳng là không có — tuyệt
đối không suy ra từ cái gần đúng rồi trình bày như thể là số thật.

Ngôn ngữ: tiếng Việt và tiếng Anh viết đủ. Mười thứ tiếng còn lại tạm
dùng tiếng Anh và sẽ bổ sung sau khi câu chữ chốt lại qua thử nghiệm
thật — dịch sớm 12 thứ tiếng cho một đoạn sắp sửa lại là công bỏ đi.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..predictor import model as pm
from . import intents as I


@dataclass
class MatchContext:
    """Tất cả dữ liệu một câu trả lời có thể cần, gom sẵn một chỗ."""
    home: str
    away: str
    """Tên đầy đủ, chỉ dùng để nhận ra đội khi người dùng gõ tên dài
    ("Manchester United" thay vì "MUN"). Hiển thị thì luôn dùng tên
    ngắn cho câu trả lời đỡ dài."""
    home_full: Optional[str] = None
    away_full: Optional[str] = None
    prediction: Optional[pm.Prediction] = None
    learned_matches: int = 0

    """Trung bình 10 trận gần nhất của mỗi đội (từ thẻ chỉ số trước trận)."""
    expected_goals: Optional[float] = None
    expected_corners: Optional[float] = None
    expected_cards: Optional[float] = None
    first_half_pct: Optional[float] = None
    home_corners: Optional[float] = None
    away_corners: Optional[float] = None
    home_cards: Optional[float] = None
    away_cards: Optional[float] = None
    home_over95_corners: Optional[float] = None
    away_over95_corners: Optional[float] = None
    home_over35_cards: Optional[float] = None
    away_over35_cards: Optional[float] = None
    window: int = 10

    """Chuỗi kết quả gần nhất, phần tử là 'W' / 'D' / 'L', mới nhất trước."""
    home_form: list[str] = field(default_factory=list)
    away_form: list[str] = field(default_factory=list)

    kickoff_utc: Optional[str] = None
    venue: Optional[str] = None
    tz_minutes: int = 0
    """Tên nguồn dữ liệu để nói với người dùng. Truyền vào từ bên ngoài
    chứ không viết cứng ở đây: đổi nguồn mà câu trả lời vẫn khoe tên
    nguồn cũ thì bot đang nói dối người dùng."""
    source: str = ""


@dataclass
class Answer:
    text: str
    """Tab nên mở để xem tiếp, nếu câu hỏi cần dữ liệu nằm ở chỗ khác."""
    action: Optional[str] = None


# --------------------------------------------------------------------------
# Định dạng số
# --------------------------------------------------------------------------

def _pct(value: float) -> str:
    """Xác suất 0..1 thành phần trăm, làm tròn tới số nguyên."""
    return f"{round(value * 100)}%"


def _dec(value: float, lang: str, digits: int = 1) -> str:
    """Số thập phân. Tiếng Việt dùng dấu phẩy, tiếng Anh dùng dấu chấm."""
    text = f"{value:.{digits}f}"
    return text.replace(".", ",") if lang == "vi" else text


def _line(value: float, lang: str) -> str:
    """Mốc như 2.5 — bỏ phần thập phân nếu là số nguyên."""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return _dec(value, lang, 1)


def _vi(lang: str) -> bool:
    return lang == "vi"


# --------------------------------------------------------------------------
# Từng ý định một.
#
# Mỗi hàm nhận (ctx, slots, lang) và trả về Answer. Hàm nào cần dữ liệu
# không có thì trả lời là không có, chứ không ném lỗi — bot phải luôn
# nói được một câu tử tế.
# --------------------------------------------------------------------------

def _no_model(ctx: MatchContext, lang: str) -> Answer:
    if _vi(lang):
        return Answer(
            "Mô hình chưa học đủ dữ liệu cho giải này nên mình chưa đưa ra "
            "con số được. Các mục thống kê phong độ ở trên vẫn dùng bình thường."
        )
    return Answer(
        "The model has not learned enough data for this competition yet, so I "
        "have no numbers here. The form statistics above still work."
    )


def _outcome(ctx, s, lang) -> Answer:
    p = ctx.prediction
    if p is None:
        return _no_model(ctx, lang)
    ph, pd, pa = p.prob_home, p.prob_draw, p.prob_away
    best = max(ph, pd, pa)
    tight = (best - min(ph, pa)) < 0.08

    if _vi(lang):
        lead = (
            f"Mô hình nghiêng về {ctx.home}" if ph > pa and ph > pd
            else f"Mô hình nghiêng về {ctx.away}" if pa > ph and pa > pd
            else "Mô hình thấy hai đội rất cân bằng"
        )
        text = (f"{lead}. {ctx.home} thắng {_pct(ph)}, hoà {_pct(pd)}, "
                f"{ctx.away} thắng {_pct(pa)}.")
        if tight:
            text += " Chênh lệch nhỏ như vậy nghĩa là kết quả nào cũng có cửa."
        return Answer(text)

    lead = (
        f"The model leans to {ctx.home}" if ph > pa and ph > pd
        else f"The model leans to {ctx.away}" if pa > ph and pa > pd
        else "The model sees this as very even"
    )
    text = (f"{lead}. {ctx.home} {_pct(ph)}, draw {_pct(pd)}, "
            f"{ctx.away} {_pct(pa)}.")
    if tight:
        text += " With a gap that small, any result is live."
    return Answer(text)


def _score(ctx, s, lang) -> Answer:
    p = ctx.prediction
    if p is None:
        return _no_model(ctx, lang)
    top = pm.most_likely_scores(p, 3)
    if not top:
        return _no_model(ctx, lang)
    x, y, q = top[0]
    rest = ", ".join(f"{a}-{b} ({_pct(c)})" for a, b, c in top[1:])

    if _vi(lang):
        return Answer(
            f"Tỷ số dễ xảy ra nhất là {x}-{y} ({_pct(q)}). "
            f"Kế đó: {rest}. "
            f"Không tỷ số nào quá {_pct(q)} — tỷ số chính xác luôn là thứ "
            f"khó trúng nhất, nên đừng coi con số này là chắc chắn."
        )
    return Answer(
        f"The most likely score is {x}-{y} ({_pct(q)}). "
        f"Next: {rest}. No scoreline goes above {_pct(q)} — an exact score is "
        f"always the hardest thing to call."
    )


def _total_goals(ctx, s, lang) -> Answer:
    p = ctx.prediction
    if p is None:
        return _no_model(ctx, lang)
    o15 = pm.p_over(p, 1.5)
    o25 = pm.p_over(p, 2.5)
    o35 = pm.p_over(p, 3.5)
    if _vi(lang):
        return Answer(
            f"Kỳ vọng {_dec(p.expected_goals, lang)} bàn cả trận. "
            f"Từ 2 bàn trở lên: {_pct(o15)}. Từ 3 bàn: {_pct(o25)}. "
            f"Từ 4 bàn: {_pct(o35)}."
        )
    return Answer(
        f"Expected {_dec(p.expected_goals, lang)} goals in total. "
        f"Two or more: {_pct(o15)}. Three or more: {_pct(o25)}. "
        f"Four or more: {_pct(o35)}."
    )


def _over_under(ctx, s, lang) -> Answer:
    p = ctx.prediction
    if p is None:
        return _no_model(ctx, lang)
    line = s.line if s.line_given and s.line is not None else 2.5
    # Mốc nguyên (3 bàn) khác mốc rưỡi (2.5 bàn): mốc nguyên có khả
    # năng trúng đúng vạch. Đẩy về mốc rưỡi gần nhất và nói rõ, thay vì
    # im lặng trả lời một câu hỏi khác câu được hỏi.
    shifted = False
    if abs(line - round(line)) < 1e-9:
        line = line - 0.5
        shifted = True
    line = max(0.5, min(line, 7.5))

    over = pm.p_over(p, line)
    under = 1.0 - over
    shown = _line(line, lang)

    if _vi(lang):
        text = f"Trên {shown} bàn: {_pct(over)}. Dưới {shown} bàn: {_pct(under)}."
        if shifted:
            text += f" (Mình quy về mốc {shown} để không có trường hợp hoà vạch.)"
        if not s.line_given:
            text += " Hỏi kèm con số nếu bạn muốn mốc khác, ví dụ \"trên 3,5 bàn\"."
        return Answer(text)

    text = f"Over {shown}: {_pct(over)}. Under {shown}: {_pct(under)}."
    if shifted:
        text += f" (Moved to {shown} so there is no exact-line push.)"
    if not s.line_given:
        text += " Add a number for a different line, e.g. \"over 3.5\"."
    return Answer(text)


def _btts(ctx, s, lang) -> Answer:
    p = ctx.prediction
    if p is None:
        return _no_model(ctx, lang)
    b = p.prob_btts
    if _vi(lang):
        return Answer(
            f"Hai đội cùng ghi bàn: {_pct(b)}. Không xảy ra: {_pct(1 - b)}. "
            f"Riêng {ctx.home} ghi được ít nhất 1 bàn: "
            f"{_pct(pm.p_scores(p, 'home'))}, {ctx.away}: "
            f"{_pct(pm.p_scores(p, 'away'))}."
        )
    return Answer(
        f"Both teams to score: {_pct(b)}. Not: {_pct(1 - b)}. "
        f"{ctx.home} to score at all: {_pct(pm.p_scores(p, 'home'))}, "
        f"{ctx.away}: {_pct(pm.p_scores(p, 'away'))}."
    )


def _handicap(ctx, s, lang) -> Answer:
    p = ctx.prediction
    if p is None:
        return _no_model(ctx, lang)
    side = s.side or "home"
    name = ctx.home if side == "home" else ctx.away
    other = ctx.away if side == "home" else ctx.home

    raw = s.line if s.line_given and s.line is not None else 1.0
    # Người dùng gõ "chấp 1.5" nghĩa là đội đó BỚT đi 1.5, nên dấu âm.
    line = -abs(raw)
    win, push, lose = pm.p_handicap(p, side, line)
    shown = _line(abs(line), lang)

    if _vi(lang):
        text = (f"{name} chấp {shown} bàn: qua {_pct(win)}")
        if push > 0.0005:
            text += f", hoà vạch {_pct(push)}"
        text += f", không qua {_pct(lose)}."
        text += (f" Nói cách khác, {name} cần thắng cách biệt "
                 f"{int(abs(line)) + 1} bàn trở lên." if push <= 0.0005 else
                 f" {name} thắng đúng {int(abs(line))} bàn thì hoà vạch.")
        text += f" (Đối thủ: {other}.)"
        return Answer(text)

    text = f"{name} giving {shown}: covers {_pct(win)}"
    if push > 0.0005:
        text += f", push {_pct(push)}"
    text += f", fails {_pct(lose)}."
    return Answer(text)


def _team_goals(ctx, s, lang) -> Answer:
    p = ctx.prediction
    if p is None:
        return _no_model(ctx, lang)
    side = s.side or "home"
    name = ctx.home if side == "home" else ctx.away
    lam = p.lambda_home if side == "home" else p.lambda_away
    at_least_1 = pm.p_team_over(p, side, 0.5)
    at_least_2 = pm.p_team_over(p, side, 1.5)

    if _vi(lang):
        return Answer(
            f"{name} kỳ vọng {_dec(lam, lang)} bàn. "
            f"Ghi ít nhất 1 bàn: {_pct(at_least_1)}. "
            f"Từ 2 bàn trở lên: {_pct(at_least_2)}. "
            f"Không ghi bàn nào: {_pct(1 - at_least_1)}."
        )
    return Answer(
        f"{name} are expected to score {_dec(lam, lang)}. "
        f"At least one: {_pct(at_least_1)}. Two or more: {_pct(at_least_2)}. "
        f"Blank: {_pct(1 - at_least_1)}."
    )


def _clean_sheet(ctx, s, lang) -> Answer:
    p = ctx.prediction
    if p is None:
        return _no_model(ctx, lang)
    ch = pm.p_clean_sheet(p, "home")
    ca = pm.p_clean_sheet(p, "away")
    if s.side:
        name = ctx.home if s.side == "home" else ctx.away
        value = ch if s.side == "home" else ca
        if _vi(lang):
            return Answer(f"{name} giữ sạch lưới: {_pct(value)}.")
        return Answer(f"{name} to keep a clean sheet: {_pct(value)}.")

    if _vi(lang):
        return Answer(
            f"{ctx.home} giữ sạch lưới: {_pct(ch)}. {ctx.away}: {_pct(ca)}. "
            f"Cả hai cùng không thủng lưới (0-0): {_pct(pm.p_exact(p, 0, 0))}."
        )
    return Answer(
        f"{ctx.home} clean sheet: {_pct(ch)}. {ctx.away}: {_pct(ca)}. "
        f"Goalless (0-0): {_pct(pm.p_exact(p, 0, 0))}."
    )


def _corners(ctx, s, lang) -> Answer:
    if ctx.expected_corners is None:
        if _vi(lang):
            return Answer("Chưa đủ dữ liệu phạt góc cho hai đội này.")
        return Answer("Not enough corner data for these two teams yet.")

    if _vi(lang):
        text = (f"Kỳ vọng {_dec(ctx.expected_corners, lang)} quả phạt góc "
                f"cả trận, tính từ {ctx.window} trận gần nhất của mỗi đội.")
        if ctx.home_over95_corners is not None and ctx.away_over95_corners is not None:
            text += (f" Các trận của {ctx.home} vượt 9,5 góc "
                     f"{round(ctx.home_over95_corners)}% số lần, "
                     f"{ctx.away} {round(ctx.away_over95_corners)}%.")
        text += (" Phạt góc tính từ trung bình phong độ chứ không từ mô hình "
                 "bàn thắng — nó phụ thuộc lối chơi nhiều hơn mạnh yếu.")
        return Answer(text)

    text = (f"Around {_dec(ctx.expected_corners, lang)} corners expected, "
            f"from the last {ctx.window} matches of each side.")
    if ctx.home_over95_corners is not None and ctx.away_over95_corners is not None:
        text += (f" {ctx.home} games went over 9.5 in "
                 f"{round(ctx.home_over95_corners)}% of them, "
                 f"{ctx.away} {round(ctx.away_over95_corners)}%.")
    return Answer(text)


def _cards(ctx, s, lang) -> Answer:
    if ctx.expected_cards is None:
        if _vi(lang):
            return Answer("Chưa đủ dữ liệu thẻ phạt cho hai đội này.")
        return Answer("Not enough card data for these two teams yet.")

    if _vi(lang):
        text = (f"Kỳ vọng {_dec(ctx.expected_cards, lang)} thẻ cả trận, "
                f"tính từ {ctx.window} trận gần nhất của mỗi đội.")
        if ctx.home_over35_cards is not None and ctx.away_over35_cards is not None:
            text += (f" Các trận của {ctx.home} vượt 3,5 thẻ "
                     f"{round(ctx.home_over35_cards)}% số lần, "
                     f"{ctx.away} {round(ctx.away_over35_cards)}%.")
        return Answer(text)

    text = (f"Around {_dec(ctx.expected_cards, lang)} cards expected, "
            f"from the last {ctx.window} matches of each side.")
    if ctx.home_over35_cards is not None and ctx.away_over35_cards is not None:
        text += (f" {ctx.home} games went over 3.5 in "
                 f"{round(ctx.home_over35_cards)}%, "
                 f"{ctx.away} {round(ctx.away_over35_cards)}%.")
    return Answer(text)


def _halves(ctx, s, lang) -> Answer:
    fh = ctx.first_half_pct
    if fh is None:
        if _vi(lang):
            return Answer("Chưa có đủ bàn thắng ở các trận gần đây để tách theo hiệp.")
        return Answer("Not enough recent goals to split by half.")
    if _vi(lang):
        return Answer(
            f"Ở {ctx.window} trận gần nhất của hai đội, {round(fh)}% số bàn "
            f"rơi vào hiệp 1 và {round(100 - fh)}% vào hiệp 2. "
            f"Đây là số liệu lịch sử, không phải dự đoán cho riêng trận này."
        )
    return Answer(
        f"Across the last {ctx.window} matches, {round(fh)}% of goals came in "
        f"the first half and {round(100 - fh)}% in the second. This is history, "
        f"not a prediction for this match."
    )


def _form_line(results: list[str], lang: str) -> str:
    w = results.count("W")
    d = results.count("D")
    l = results.count("L")
    if _vi(lang):
        return f"{w} thắng, {d} hoà, {l} thua"
    return f"{w}W {d}D {l}L"


def _form(ctx, s, lang) -> Answer:
    if not ctx.home_form and not ctx.away_form:
        if _vi(lang):
            return Answer("Chưa tải được phong độ gần đây của hai đội.")
        return Answer("Recent form is not available for these teams.")

    sides = [s.side] if s.side else ["home", "away"]
    parts = []
    for side in sides:
        name = ctx.home if side == "home" else ctx.away
        res = ctx.home_form if side == "home" else ctx.away_form
        if not res:
            continue
        chain = " ".join(res[:5])
        if _vi(lang):
            parts.append(f"{name}: {_form_line(res, lang)} trong {len(res)} trận "
                         f"gần nhất (mới nhất trước: {chain}).")
        else:
            parts.append(f"{name}: {_form_line(res, lang)} in the last "
                         f"{len(res)} (most recent first: {chain}).")
    if not parts:
        if _vi(lang):
            return Answer("Chưa tải được phong độ gần đây của hai đội.")
        return Answer("Recent form is not available for these teams.")
    return Answer(" ".join(parts))


def _h2h(ctx, s, lang) -> Answer:
    if _vi(lang):
        return Answer(
            "Lịch sử đối đầu nằm ở tab Đối đầu — ở đó có từng trận, ngày "
            "tháng, giải đấu và lọc được theo giải.",
            action="history",
        )
    return Answer(
        "Head-to-head sits in the Head to head tab — every meeting with its "
        "date and competition, filterable by competition.",
        action="history",
    )


def _standings(ctx, s, lang) -> Answer:
    if _vi(lang):
        return Answer(
            "Bảng xếp hạng nằm ở tab Bảng xếp hạng ngoài màn hình chính. "
            "Chạm vào một đội ở đó để xem phong độ riêng của đội đó.",
            action="standings",
        )
    return Answer(
        "The table is on the Standings tab on the main screen. Tap a team "
        "there to see its own form.",
        action="standings",
    )


def _kickoff(ctx, s, lang) -> Answer:
    when = None
    if ctx.kickoff_utc:
        try:
            dt = datetime.fromisoformat(ctx.kickoff_utc.replace("Z", "+00:00"))
            local = dt.astimezone(timezone(timedelta(minutes=ctx.tz_minutes)))
            when = local.strftime("%H:%M %d/%m/%Y")
        except ValueError:
            when = None

    if _vi(lang):
        if when and ctx.venue:
            return Answer(f"Trận đá lúc {when} (giờ máy bạn), tại {ctx.venue}.")
        if when:
            return Answer(f"Trận đá lúc {when} theo giờ máy bạn.")
        if ctx.venue:
            return Answer(f"Trận đá tại {ctx.venue}.")
        return Answer("Mình chưa có giờ thi đấu của trận này.")

    if when and ctx.venue:
        return Answer(f"Kick-off at {when} your time, at {ctx.venue}.")
    if when:
        return Answer(f"Kick-off at {when} your time.")
    if ctx.venue:
        return Answer(f"Played at {ctx.venue}.")
    return Answer("I do not have a kick-off time for this match.")


def _injuries(ctx, s, lang) -> Answer:
    """
    Câu trả lời này cố ý nói thẳng là KHÔNG CÓ.

    Đã kiểm tra tận nơi: nguồn ESPN trả về danh sách chấn thương rỗng
    cho mọi đội ở các giải app đang dùng. Suy ra từ đội hình trận trước
    rồi trình bày như tin chấn thương là kiểu sai nguy hiểm nhất — người
    đọc không có cách nào biết đó là phỏng đoán.
    """
    if _vi(lang):
        return Answer(
            "Nguồn dữ liệu hiện tại không công bố danh sách chấn thương hay "
            "treo giò, nên mình không có số liệu để trả lời — và mình sẽ "
            "không đoán. Đội hình ra sân thường có trước giờ bóng lăn khoảng "
            "một tiếng, lúc đó xem ở tab Đội hình.",
            action="lineups",
        )
    return Answer(
        "The data source does not publish injury or suspension lists, so I "
        "have nothing to answer with — and I will not guess. Confirmed "
        "line-ups usually appear about an hour before kick-off, in the "
        "Line-ups tab.",
        action="lineups",
    )


def _model_info(ctx, s, lang) -> Answer:
    n = ctx.learned_matches
    src_vi = f" qua dữ liệu {ctx.source}" if ctx.source else ""
    src_en = f" from {ctx.source} data" if ctx.source else ""
    if _vi(lang):
        return Answer(
            f"Các con số đến từ một mô hình Poisson có hệ số từng đội "
            f"(Dixon-Coles), tự viết trong app, học từ {n} trận đã đá của "
            f"giải này{src_vi}. Nó học lại vài tiếng một lần và tự "
            f"chấm điểm mình trên những trận chưa dùng để học, nên biết được "
            f"mình đang tốt lên hay kém đi. Không gọi AI, không có con số nào "
            f"do máy tự nghĩ ra. Dù vậy đây vẫn là xác suất, không phải điều "
            f"chắc chắn."
        )
    return Answer(
        f"The numbers come from a team-rated Poisson model (Dixon-Coles) "
        f"written inside the app, trained on {n} completed matches of this "
        f"competition{src_en}. It retrains every few hours and scores "
        f"itself on matches it did not learn from. No AI is involved. These "
        f"are still probabilities, not certainties."
    )


def _out_of_scope(ctx, s, lang) -> Answer:
    if _vi(lang):
        return Answer(
            "Mình chỉ trả lời số liệu của riêng trận này — bàn thắng, phạt "
            "góc, thẻ, phong độ. Thử một trong những câu gợi ý bên dưới nhé."
        )
    return Answer(
        "I only answer statistics about this match — goals, corners, cards, "
        "form. Try one of the suggestions below."
    )


BUILDERS = {
    I.OUTCOME: _outcome,
    I.SCORE: _score,
    I.TOTAL_GOALS: _total_goals,
    I.OVER_UNDER: _over_under,
    I.BTTS: _btts,
    I.HANDICAP: _handicap,
    I.TEAM_GOALS: _team_goals,
    I.CLEAN_SHEET: _clean_sheet,
    I.CORNERS: _corners,
    I.CARDS: _cards,
    I.HALVES: _halves,
    I.FORM: _form,
    I.H2H: _h2h,
    I.STANDINGS: _standings,
    I.KICKOFF: _kickoff,
    I.INJURIES: _injuries,
    I.MODEL_INFO: _model_info,
    I.OTHER: _out_of_scope,
}

# Thiếu hàm trả lời cho một ý định là lỗi lúc nạp mô-đun, không phải lỗi
# lúc người dùng hỏi trúng ý định đó.
_missing = set(I.ALL_INTENTS) - set(BUILDERS)
assert not _missing, f"thiếu hàm trả lời cho: {sorted(_missing)}"


def build(intent: str, slots, ctx: MatchContext, lang: str) -> Answer:
    builder = BUILDERS.get(intent)
    if builder is None:
        return _out_of_scope(ctx, slots, lang)
    return builder(ctx, slots, lang)
