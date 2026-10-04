"""
Mô hình dự đoán bóng đá. Thuần thống kê, KHÔNG gọi AI.

Cách tiếp cận: Poisson có hệ số đội, kèm hiệu chỉnh Dixon-Coles.

  λ_nhà    = exp(công_nhà  + thủ_khách + lợi_thế_sân_nhà)
  λ_khách  = exp(công_khách + thủ_nhà)

Số bàn mỗi đội ghi được coi là biến ngẫu nhiên Poisson với kỳ vọng λ.
Từ đó dựng được bảng xác suất cho MỌI tỉ số, và mọi thứ khác — thắng /
hoà / thua, tài xỉu, hai đội cùng ghi bàn — đều là phép cộng trên bảng
đó chứ không phải một mô hình riêng. Nhờ vậy các con số luôn nhất quán
với nhau, điều mà việc hỏi AI từng câu một không bao giờ bảo đảm được.

Ba điểm khiến mô hình này khác một phép trung bình cộng đơn thuần:

  1. HIỆU CHỈNH DIXON-COLES. Poisson thuần giả định số bàn hai đội độc
     lập, và nó ước lượng sai một cách có hệ thống ở các tỉ số thấp
     (0-0, 1-0, 0-1, 1-1) — vốn chiếm phần lớn các trận bóng đá. Tham số
     rho kéo bốn ô đó về đúng thực tế.

  2. GIẢM TRỌNG SỐ THEO THỜI GIAN. Trận cách đây một năm không nói lên
     nhiều về phong độ hôm nay bằng trận tuần trước. Trọng số giảm theo
     hàm mũ với tốc độ xi, nên mô hình tự thích nghi khi đội lên hoặc
     xuống phong độ, không cần ai can thiệp.

  3. RÀNG BUỘC TỔNG BẰNG KHÔNG. Hệ số công và thủ chỉ có ý nghĩa tương
     đối với nhau; không ràng buộc thì chúng trôi vô hạn mà kết quả
     không đổi. Ép tổng bằng 0 sau mỗi bước để số liệu đọc được và so
     sánh được giữa các mùa.

Cố ý không dùng numpy/scipy: bài toán chỉ vài chục tham số mỗi giải, tự
viết gradient chạy thừa nhanh, mà máy chủ triển khai nhẹ đi hẳn.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Iterable, Optional

# Số bàn tối đa xét tới khi dựng bảng xác suất tỉ số. Xác suất một đội
# ghi hơn 8 bàn nhỏ tới mức không ảnh hưởng kết quả nào bên dưới.
MAX_GOALS = 8


@dataclass
class MatchResult:
    """Một trận ĐÃ ĐÁ XONG, dùng để huấn luyện."""
    home: str
    away: str
    home_goals: int
    away_goals: int
    """Số ngày tính tới hiện tại. Càng lớn càng ít ảnh hưởng."""
    days_ago: float


@dataclass
class Ratings:
    """Hệ số đã học được của một giải."""
    attack: dict[str, float] = field(default_factory=dict)
    defence: dict[str, float] = field(default_factory=dict)
    home_adv: float = 0.25
    rho: float = -0.05
    """Số trận đã dùng để học."""
    matches: int = 0
    """Hệ số nền (log): mức bàn thắng của một đội TRUNG BÌNH khi đá sân
    khách. Mọi hệ số công/thủ là độ lệch quanh mốc này."""
    intercept: float = 0.3
    """Giữ lại cho tương thích ngược với bản lưu cũ."""
    base: float = 1.35

    def known(self, team: str) -> bool:
        return team in self.attack


def _dc_tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    """
    Hệ số hiệu chỉnh Dixon-Coles cho bốn tỉ số thấp.

    Chặn dưới ở một số dương nhỏ: rho lớn có thể đẩy tau xuống âm, mà
    xác suất âm thì log-likelihood thành vô nghĩa.
    """
    if x == 0 and y == 0:
        v = 1.0 - lam * mu * rho
    elif x == 0 and y == 1:
        v = 1.0 + lam * rho
    elif x == 1 and y == 0:
        v = 1.0 + mu * rho
    elif x == 1 and y == 1:
        v = 1.0 - rho
    else:
        return 1.0
    return max(v, 1e-6)


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))


def fit(
    results: list[MatchResult],
    xi: float = 0.0045,
    iterations: int = 400,
    lr: float = 0.10,
    prior: Optional[Ratings] = None,
    reg: float = 0.05,
) -> Ratings:
    """
    Học hệ số công/thủ bằng cách tối đa hoá log-likelihood có trọng số.

    Dùng gradient ascent thường chứ không phải thuật toán tối ưu tinh
    vi: hàm mục tiêu lõm theo từng tham số quanh nghiệm, dữ liệu lại ít
    nhiễu, nên vài trăm bước là hội tụ. Đổi lại không phải kéo theo
    scipy lên máy chủ.

    prior: hệ số của lần học trước, dùng làm điểm khởi đầu. Nhờ vậy lần
    học sau nhanh hơn nhiều và hệ số không nhảy lung tung giữa hai lần.

    reg: lực kéo hệ số về 0 (co giãn về trung bình giải). Đội mới đá vài
    trận, hoặc đội vừa thua đậm một trận, sẽ bị đẩy ra hệ số cực đoan mà
    thực tế không đúng như vậy. Kéo về giữa làm dự đoán bớt tự tin thái
    quá — đúng hướng, vì Brier phạt rất nặng việc tự tin mà sai.

    Trước đây tôi chặn cứng hệ số trong khoảng ±1,2. Cách đó thô: nó
    không phân biệt đội đá 40 trận với đội đá 4 trận, trong khi chính đội
    ít trận mới cần kéo về nhiều nhất. Co giãn theo lực reg tự làm đúng
    việc đó, vì đội ít trận có gradient yếu nên bị lực kéo thắng thế.
    """
    teams = sorted({m.home for m in results} | {m.away for m in results})
    if not teams or not results:
        return prior or Ratings()

    # Hệ số nền PHẢI được học chứ không cố định.
    #
    # Lần đầu tôi gán cứng bằng log của trung bình bàn thắng chung. Sai:
    # khi đó lợi thế sân nhà phải gánh cả phần chênh lệch nhà–khách, mà
    # hệ số công/thủ lại bị ràng buộc tổng bằng 0 nên không có tham số
    # nào diễn tả được "đội khách ghi ít hơn mặt bằng chung". Kết quả đo
    # được: lợi thế sân nhà bị đẩy về 0 và Brier 0,66 — gần như đoán bừa.
    #
    # Để nền tự do thì nó hội tụ về mức bàn thắng của đội khách trung
    # bình, còn lợi thế sân nhà nhận đúng phần chênh lệch còn lại.
    away_mean = sum(m.away_goals for m in results) / len(results)
    intercept = math.log(max(0.3, away_mean))

    attack = {t: (prior.attack.get(t, 0.0) if prior else 0.0) for t in teams}
    defence = {t: (prior.defence.get(t, 0.0) if prior else 0.0) for t in teams}
    home_adv = prior.home_adv if prior else 0.2

    weights = [math.exp(-xi * m.days_ago) for m in results]

    # Tổng trọng số CỦA RIÊNG từng đội, để chuẩn hoá gradient.
    #
    # Đây là chỗ dễ sai nhất. Chia gradient của một đội cho tổng số trận
    # của cả giải sẽ làm bước cập nhật nhỏ đi đúng bằng số đội — mô hình
    # bò rất chậm và dừng lại khi chưa tới đâu. Đo được: lợi thế sân nhà
    # hội tụ ở 0,047 (thực tế quanh 0,25) và điểm Brier 0,652, tức gần
    # như đoán bừa. Phải chia cho tổng trọng số các trận CÓ ĐỘI ĐÓ.
    w_team: dict[str, float] = {t: 0.0 for t in teams}
    for m, w in zip(results, weights):
        w_team[m.home] += w
        w_team[m.away] += w
    w_total = sum(weights) or 1.0

    for _ in range(iterations):
        g_att = {t: 0.0 for t in teams}
        g_def = {t: 0.0 for t in teams}
        g_home = 0.0

        g_int = 0.0
        for m, w in zip(results, weights):
            lam = math.exp(intercept + attack[m.home] + defence[m.away] + home_adv)
            mu = math.exp(intercept + attack[m.away] + defence[m.home])

            # d/dθ của log P(x|λ) với λ = exp(θ) là (x - λ).
            d_lam = w * (m.home_goals - lam)
            d_mu = w * (m.away_goals - mu)

            g_att[m.home] += d_lam
            g_def[m.away] += d_lam
            g_home += d_lam
            g_int += d_lam + d_mu
            g_att[m.away] += d_mu
            g_def[m.home] += d_mu

        intercept += lr * g_int / (2 * w_total)
        for t in teams:
            denom = w_team[t] or 1.0
            attack[t] += lr * (g_att[t] / denom - reg * attack[t])
            defence[t] += lr * (g_def[t] / denom - reg * defence[t])
        home_adv += lr * g_home / w_total

        # Ràng buộc tổng bằng không, xem ghi chú ở đầu file.
        ma = sum(attack.values()) / len(teams)
        md = sum(defence.values()) / len(teams)
        for t in teams:
            attack[t] -= ma
            defence[t] -= md

        # Biên an toàn rộng, chỉ để chặn trường hợp bệnh lý. Việc kéo hệ
        # số về mức hợp lý đã do reg lo.
        for t in teams:
            attack[t] = max(-2.0, min(2.0, attack[t]))
            defence[t] = max(-2.0, min(2.0, defence[t]))
        home_adv = max(0.0, min(0.6, home_adv))

    rho = _fit_rho(results, weights, attack, defence, home_adv, intercept)

    return Ratings(
        attack=attack, defence=defence, home_adv=home_adv, rho=rho,
        matches=len(results), intercept=intercept,
        base=math.exp(intercept),
    )


def _fit_rho(
    results: list[MatchResult], weights: list[float],
    attack: dict[str, float], defence: dict[str, float],
    home_adv: float, intercept: float,
) -> float:
    """
    Tìm rho bằng cách quét qua một dải giá trị.

    Chỉ một tham số và miền hợp lệ rất hẹp, nên quét thẳng vừa đơn giản
    vừa chắc chắn hơn gradient — không sợ mắc kẹt ở cực trị địa phương.
    """
    best_rho, best_ll = 0.0, -math.inf
    for step in range(-25, 11):
        rho = step / 100.0
        ll = 0.0
        ok = True
        for m, w in zip(results, weights):
            lam = math.exp(intercept + attack[m.home] + defence[m.away] + home_adv)
            mu = math.exp(intercept + attack[m.away] + defence[m.home])
            tau = _dc_tau(m.home_goals, m.away_goals, lam, mu, rho)
            if tau <= 0:
                ok = False
                break
            ll += w * math.log(tau)
        if ok and ll > best_ll:
            best_ll, best_rho = ll, rho
    return best_rho


@dataclass
class Prediction:
    """Kết quả dự đoán cho một trận."""
    lambda_home: float
    lambda_away: float
    prob_home: float
    prob_draw: float
    prob_away: float
    prob_over25: float
    prob_btts: float
    expected_goals: float
    """Tỉ số khả dĩ nhất và xác suất của chính tỉ số đó."""
    top_score: tuple[int, int]
    top_score_prob: float
    """Ba tỉ số khả dĩ nhất, dùng để hiện thêm phương án."""
    top_scores: list[tuple[int, int, float]]
    """
    Bảng xác suất đầy đủ: grid[x][y] là xác suất trận kết thúc x-y.

    Giữ lại thay vì tính xong rồi bỏ, vì MỌI câu hỏi về bàn thắng đều
    chỉ là phép cộng vài ô của bảng này — trên/dưới bất kỳ mốc nào, chấp
    bao nhiêu trái, một đội có giữ sạch lưới không. Nhờ vậy phần hỏi đáp
    không cần mô hình riêng và không bao giờ nói lệch con số hiện trên
    thẻ dự đoán, vì cả hai đọc chung một bảng.
    """
    grid: list[list[float]] = field(default_factory=list)


def predict(r: Ratings, home: str, away: str) -> Prediction:
    """
    Dựng bảng xác suất tỉ số rồi rút ra mọi con số từ đó.

    Đội chưa từng gặp (mới lên hạng, hoặc giải cúp có đội hạng dưới)
    được gán hệ số 0 — nghĩa là "đội trung bình của giải". Thà dự đoán
    nhạt còn hơn từ chối trả lời.
    """
    base = r.intercept
    lam = math.exp(base + r.attack.get(home, 0.0) + r.defence.get(away, 0.0) + r.home_adv)
    mu = math.exp(base + r.attack.get(away, 0.0) + r.defence.get(home, 0.0))

    grid: list[list[float]] = []
    total = 0.0
    for x in range(MAX_GOALS + 1):
        row = []
        for y in range(MAX_GOALS + 1):
            p = _poisson_pmf(x, lam) * _poisson_pmf(y, mu) * _dc_tau(x, y, lam, mu, r.rho)
            row.append(p)
            total += p
        grid.append(row)

    # Chuẩn hoá: cắt ở 8 bàn và hiệu chỉnh Dixon-Coles đều làm tổng lệch
    # khỏi 1 một chút.
    if total > 0:
        grid = [[p / total for p in row] for row in grid]

    p_home = p_draw = p_away = 0.0
    p_over = p_btts = 0.0
    scores: list[tuple[int, int, float]] = []
    exp_goals = 0.0

    for x in range(MAX_GOALS + 1):
        for y in range(MAX_GOALS + 1):
            p = grid[x][y]
            if p <= 0:
                continue
            if x > y:
                p_home += p
            elif x == y:
                p_draw += p
            else:
                p_away += p
            if x + y > 2:
                p_over += p
            if x > 0 and y > 0:
                p_btts += p
            exp_goals += p * (x + y)
            scores.append((x, y, p))

    scores.sort(key=lambda s: s[2], reverse=True)
    top = scores[0] if scores else (0, 0, 0.0)

    return Prediction(
        lambda_home=lam, lambda_away=mu,
        prob_home=p_home, prob_draw=p_draw, prob_away=p_away,
        prob_over25=p_over, prob_btts=p_btts,
        expected_goals=exp_goals,
        top_score=(top[0], top[1]), top_score_prob=top[2],
        top_scores=scores[:3],
        grid=grid,
    )


# --------------------------------------------------------------------------
# Truy vấn bảng xác suất.
#
# Mỗi hàm dưới đây chỉ là một vòng lặp cộng các ô thoả điều kiện. Cố ý
# viết tách ra từng hàm nhỏ thay vì một hàm tổng quát nhận biểu thức:
# phần hỏi đáp gọi thẳng theo tên, đọc lại biết ngay đang hỏi gì, và
# không có đường nào để một câu hỏi lạ chạy ra con số vô nghĩa.
# --------------------------------------------------------------------------

def _sum_where(p: Prediction, cond) -> float:
    """Cộng xác suất mọi tỉ số thoả điều kiện cond(bàn_nhà, bàn_khách)."""
    if not p.grid:
        return 0.0
    total = 0.0
    for x, row in enumerate(p.grid):
        for y, q in enumerate(row):
            if q > 0 and cond(x, y):
                total += q
    return total


def p_over(p: Prediction, line: float) -> float:
    """Xác suất TỔNG bàn cả trận vượt mốc. Mốc 2.5 nghĩa là từ 3 bàn."""
    return _sum_where(p, lambda x, y: x + y > line)


def p_under(p: Prediction, line: float) -> float:
    return _sum_where(p, lambda x, y: x + y < line)


def p_team_over(p: Prediction, side: str, line: float) -> float:
    """Xác suất RIÊNG một đội ghi vượt mốc. side là 'home' hoặc 'away'."""
    if side == "home":
        return _sum_where(p, lambda x, y: x > line)
    return _sum_where(p, lambda x, y: y > line)


def p_exact(p: Prediction, home_goals: int, away_goals: int) -> float:
    return _sum_where(p, lambda x, y: x == home_goals and y == away_goals)


def p_clean_sheet(p: Prediction, side: str) -> float:
    """Xác suất đội side không thủng lưới bàn nào."""
    if side == "home":
        return _sum_where(p, lambda x, y: y == 0)
    return _sum_where(p, lambda x, y: x == 0)


def p_scores(p: Prediction, side: str) -> float:
    """Xác suất đội side ghi được ít nhất một bàn."""
    return p_team_over(p, side, 0.5)


def p_margin_at_least(p: Prediction, side: str, goals: int) -> float:
    """Xác suất đội side thắng cách biệt từ `goals` bàn trở lên."""
    if side == "home":
        return _sum_where(p, lambda x, y: x - y >= goals)
    return _sum_where(p, lambda x, y: y - x >= goals)


def p_handicap(p: Prediction, side: str, line: float) -> tuple[float, float, float]:
    """
    Xác suất (qua, hoàn, không qua) khi cộng `line` bàn cho đội side.

    line âm là đội đó chấp đối thủ (-1.5 nghĩa là phải thắng từ 2 bàn),
    line dương là được cộng trước. Mốc nguyên có khả năng hoà đúng bằng
    vạch, nên trả về ba số chứ không phải một — gộp lại thành một con số
    là cách dễ nhất để nói sai.
    """
    win = push = lose = 0.0
    if not p.grid:
        return 0.0, 0.0, 0.0
    for x, row in enumerate(p.grid):
        for y, q in enumerate(row):
            if q <= 0:
                continue
            diff = (x - y) if side == "home" else (y - x)
            adjusted = diff + line
            if adjusted > 0:
                win += q
            elif adjusted == 0:
                push += q
            else:
                lose += q
    return win, push, lose


def most_likely_scores(p: Prediction, count: int = 3) -> list[tuple[int, int, float]]:
    """Các tỉ số khả dĩ nhất, nhiều hơn ba nếu cần."""
    if not p.grid:
        return []
    flat = [
        (x, y, q)
        for x, row in enumerate(p.grid)
        for y, q in enumerate(row)
        if q > 0
    ]
    flat.sort(key=lambda s: s[2], reverse=True)
    return flat[:count]


def brier_score(pred: Prediction, home_goals: int, away_goals: int) -> float:
    """
    Điểm Brier cho dự đoán thắng/hoà/thua. Càng THẤP càng tốt.

    Đoán bừa đều nhau cho ra 0,667; luôn đoán đúng chắc chắn cho ra 0.
    Đây là thước đo dùng để biết mô hình có thật sự khá lên hay không,
    thay vì chỉ cảm giác.
    """
    actual = (
        1.0 if home_goals > away_goals else 0.0,
        1.0 if home_goals == away_goals else 0.0,
        1.0 if home_goals < away_goals else 0.0,
    )
    got = (pred.prob_home, pred.prob_draw, pred.prob_away)
    return sum((g - a) ** 2 for g, a in zip(got, actual))
