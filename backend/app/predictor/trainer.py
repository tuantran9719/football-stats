"""
Thu thập kết quả từ ESPN, học hệ số, và tự chấm điểm.

Phần "tự học, tự cải tiến" nằm ở đây, và nó có nghĩa cụ thể chứ không
phải khẩu hiệu:

  1. HỌC LẠI ĐỊNH KỲ. Mỗi lần chạy lại nạp thêm các trận vừa đá xong.
     Trọng số giảm theo thời gian nên hệ số tự dịch chuyển theo phong
     độ, đội đang lên tự được nâng, đội sa sút tự bị hạ.

  2. TỰ CHỌN THAM SỐ. Tốc độ quên xi không cố định. Mỗi lần huấn luyện
     thử vài giá trị, chấm điểm trên phần dữ liệu KHÔNG dùng để học, rồi
     giữ giá trị tốt nhất. Giải đá ổn định và giải nhiều biến động sẽ tự
     hội tụ về tốc độ quên khác nhau.

  3. TỰ ĐO. Điểm Brier của mỗi lần huấn luyện được ghi lại, nên trả lời
     được câu "mô hình có khá lên không" bằng số chứ không bằng cảm
     giác.

Kiểm định là kiểu tiến dần theo thời gian: học trên các trận cũ, chấm
trên các trận mới hơn. Trộn ngẫu nhiên sẽ cho điểm đẹp giả tạo vì mô
hình được nhìn trước tương lai.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Optional

from ..models import Match
from . import store
from .model import MatchResult, Ratings, brier_score, fit, predict

# Các tốc độ quên đem ra thử. 0.002 ~ nhớ khoảng hai năm, 0.015 ~ chỉ
# nhớ vài tháng gần nhất.
XI_CANDIDATES = (0.0035, 0.0075, 0.015)

# Lực co giãn về trung bình giải.
#
# Dải này chọn sau khi quét thực tế trên dữ liệu Ngoại hạng Anh: điểm
# tốt nhất nằm quanh 1,2 và là cực tiểu THẬT (0,7 và 2,0 đều kém hơn),
# chứ không phải chạm biên. Giữ vài giá trị hai bên để giải khác tự tìm
# được mức phù hợp của nó.
REG_CANDIDATES = (0.35, 0.7, 1.2, 2.0)

# Dưới ngần này trận thì học ra hệ số vô nghĩa, thà không dự đoán.
MIN_MATCHES = 40

# Phần dữ liệu mới nhất giữ lại để chấm điểm, không cho học.
HOLDOUT = 0.2


def to_results(matches: list[Match]) -> list[MatchResult]:
    """Lọc lấy trận đã đá xong và có tỉ số, quy về dạng huấn luyện."""
    now = datetime.now(timezone.utc)
    out: list[MatchResult] = []
    for m in matches:
        if m.status != "finished" or m.score is None:
            continue
        try:
            when = datetime.fromisoformat(m.kickoffUtc.replace("Z", "+00:00"))
        except ValueError:
            continue
        out.append(MatchResult(
            home=m.home.id, away=m.away.id,
            home_goals=int(m.score.home), away_goals=int(m.score.away),
            days_ago=max(0.0, (now - when).total_seconds() / 86400.0),
        ))
    out.sort(key=lambda r: -r.days_ago)  # cũ trước, mới sau
    return out


def _evaluate(r: Ratings, test: list[MatchResult]) -> tuple[float, int]:
    """Điểm Brier trung bình trên tập chấm. Càng thấp càng tốt."""
    total, n = 0.0, 0
    for m in test:
        if not (r.known(m.home) and r.known(m.away)):
            continue
        total += brier_score(predict(r, m.home, m.away), m.home_goals, m.away_goals)
        n += 1
    return (total / n if n else 1.0), n


async def train_league(
    league: str, matches: list[Match],
) -> Optional[dict]:
    """
    Học hệ số cho một giải và ghi lại. Trả về tóm tắt, hoặc None nếu
    chưa đủ dữ liệu.
    """
    results = to_results(matches)
    if len(results) < MIN_MATCHES:
        return None

    cut = max(MIN_MATCHES // 2, int(len(results) * (1 - HOLDOUT)))
    train, test = results[:cut], results[cut:]
    prior = await store.get_ratings(league)

    best: tuple[float, float, float, int] | None = None
    for xi in XI_CANDIDATES:
        for reg in REG_CANDIDATES:
            # Chạy trong luồng riêng: vòng lặp gradient là tính toán
            # thuần CPU, để nguyên sẽ chặn vòng lặp sự kiện của server.
            cand = await asyncio.to_thread(fit, train, xi, 500, 0.12, prior, reg)
            brier, n = _evaluate(cand, test)
            if n == 0:
                continue
            if best is None or brier < best[0]:
                best = (brier, xi, reg, n)

    if best is None:
        return None

    brier, xi, reg, samples = best

    # Học lại lần cuối trên TOÀN BỘ dữ liệu với tham số tốt nhất: tập
    # chấm cũng là các trận gần đây nhất, bỏ đi thì phí thông tin quý
    # nhất.
    final = await asyncio.to_thread(fit, results, xi, 600, 0.12, prior, reg)

    # Mốc để biết mô hình có hơn việc đoán theo tỉ lệ nền hay không.
    baseline = _baseline_brier(train, test)

    await store.save_ratings(league, final, xi, reg)
    await store.log_accuracy(league, brier, samples, xi, reg, baseline)

    return {
        "league": league,
        "matches": len(results),
        "teams": len(final.attack),
        "xi": xi,
        "reg": reg,
        "brier": round(brier, 4),
        "baseline": round(baseline, 4),
        "samples": samples,
        "homeAdvantage": round(final.home_adv, 3),
    }


def _baseline_brier(train: list[MatchResult], test: list[MatchResult]) -> float:
    """
    Điểm Brier nếu chỉ đoán theo tỉ lệ thắng/hoà/thua chung của giải.

    Mô hình phải thấp hơn con số này thì mới thật sự có ích; bằng hoặc
    cao hơn nghĩa là hệ số đội không mang thêm thông tin gì.
    """
    if not train or not test:
        return 1.0
    hw = sum(1 for m in train if m.home_goals > m.away_goals) / len(train)
    dr = sum(1 for m in train if m.home_goals == m.away_goals) / len(train)
    aw = max(0.0, 1.0 - hw - dr)
    total = 0.0
    for m in test:
        actual = (
            1.0 if m.home_goals > m.away_goals else 0.0,
            1.0 if m.home_goals == m.away_goals else 0.0,
            1.0 if m.home_goals < m.away_goals else 0.0,
        )
        total += sum((p - a) ** 2 for p, a in zip((hw, dr, aw), actual))
    return total / len(test)
