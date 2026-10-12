"""
Mô hình dự đoán: kiểm tính nhất quán của bảng xác suất.

Vì sao đáng kiểm: mọi con số người dùng thấy — tỉ lệ thắng, trên/dưới,
hai đội cùng ghi bàn, cách biệt — đều rút ra từ CÙNG một bảng. Nếu các
phép cộng trên bảng đó lệch nhau thì app sẽ nói hai điều mâu thuẫn ở
hai chỗ khác nhau trong cùng một màn hình, mà không có lỗi nào hiện ra.
"""
from __future__ import annotations

import math

import pytest

from app.predictor.model import (
    MatchResult, Ratings, brier_score, fit, most_likely_scores, p_clean_sheet,
    p_exact, p_handicap, p_margin_at_least, p_over, p_scores, p_team_over,
    p_under, predict,
)


@pytest.fixture(scope="module")
def pred():
    r = Ratings(
        attack={"A": 0.30, "B": -0.10}, defence={"A": -0.20, "B": 0.10},
        home_adv=0.17, rho=-0.05, matches=500, intercept=0.10,
    )
    return predict(r, "A", "B")


def test_bang_xac_suat_cong_lai_bang_mot(pred):
    total = sum(sum(row) for row in pred.grid)
    assert math.isclose(total, 1.0, abs_tol=1e-9)


def test_thang_hoa_thua_cong_lai_bang_mot(pred):
    assert math.isclose(
        pred.prob_home + pred.prob_draw + pred.prob_away, 1.0, abs_tol=1e-9,
    )


def test_tren_duoi_la_phan_bu_cua_nhau(pred):
    for line in (0.5, 1.5, 2.5, 3.5, 4.5):
        assert math.isclose(
            p_over(pred, line) + p_under(pred, line), 1.0, abs_tol=1e-9,
        ), f"mốc {line} không cộng về 1"


def test_so_luu_san_khop_voi_phep_cong_tren_bang(pred):
    """prob_over25 lưu sẵn phải bằng đúng phép cộng lại từ bảng.

    Đây là chỗ dễ lệch nhất: thẻ dự đoán đọc trường lưu sẵn, còn bot
    hỏi đáp tự cộng từ bảng. Lệch là hai nơi nói hai số khác nhau.
    """
    assert math.isclose(pred.prob_over25, p_over(pred, 2.5), abs_tol=1e-12)

    # Hai đội cùng ghi bàn = 1 trừ (nhà tịt) trừ (khách tịt) cộng lại
    # phần 0-0 vì nó bị trừ hai lần. Đây là một đẳng thức CHÍNH XÁC,
    # không phải xấp xỉ.
    nha_tit = 1 - p_scores(pred, "home")
    khach_tit = 1 - p_scores(pred, "away")
    assert math.isclose(
        pred.prob_btts,
        1 - nha_tit - khach_tit + p_exact(pred, 0, 0),
        abs_tol=1e-9,
    )


def test_chap_bong_cong_lai_bang_mot(pred):
    for line in (-2.0, -1.5, -1.0, -0.5, 0.5, 1.0):
        win, push, lose = p_handicap(pred, "home", line)
        assert math.isclose(win + push + lose, 1.0, abs_tol=1e-9), f"mốc {line}"


def test_moc_nguyen_co_hoa_vach_moc_ruoi_thi_khong(pred):
    _, push_int, _ = p_handicap(pred, "home", -1.0)
    _, push_half, _ = p_handicap(pred, "home", -1.5)
    assert push_int > 0, "chấp 1 trái phải có khả năng hoà vạch"
    assert push_half == 0, "chấp 1,5 trái thì không thể hoà vạch"


def test_cach_biet_cang_lon_xac_suat_cang_nho(pred):
    xs = [p_margin_at_least(pred, "home", n) for n in (1, 2, 3, 4)]
    assert xs == sorted(xs, reverse=True)


def test_moi_xac_suat_nam_trong_khoang_hop_le(pred):
    vals = [
        pred.prob_home, pred.prob_draw, pred.prob_away, pred.prob_over25,
        pred.prob_btts, p_clean_sheet(pred, "home"), p_clean_sheet(pred, "away"),
        p_team_over(pred, "home", 1.5), p_scores(pred, "away"),
    ]
    assert all(0.0 <= v <= 1.0 for v in vals)


def test_ti_so_kha_di_nhat_xep_giam_dan(pred):
    tops = most_likely_scores(pred, 5)
    probs = [p for _, _, p in tops]
    assert probs == sorted(probs, reverse=True)
    assert math.isclose(tops[0][2], pred.top_score_prob, abs_tol=1e-12)


def test_doi_manh_hon_thi_xac_suat_thang_cao_hon():
    r = Ratings(
        attack={"MANH": 0.8, "YEU": -0.8}, defence={"MANH": -0.5, "YEU": 0.5},
        home_adv=0.0, rho=-0.05, matches=500, intercept=0.1,
    )
    assert predict(r, "MANH", "YEU").prob_home > predict(r, "YEU", "MANH").prob_home


def test_doi_chua_tung_gap_khong_lam_sap_mo_hinh():
    """Đội mới lên hạng được gán hệ số 0 thay vì ném lỗi."""
    r = Ratings(attack={"A": 0.3}, defence={"A": -0.2}, home_adv=0.2,
                rho=-0.05, matches=100, intercept=0.1)
    p = predict(r, "A", "DOI_LA")
    assert math.isclose(sum(sum(row) for row in p.grid), 1.0, abs_tol=1e-9)


def test_hoc_duoc_loi_the_san_nha_duong():
    """Dữ liệu có lợi thế sân nhà rõ rệt thì hệ số phải dương.

    Từng có lúc hệ số này bị kẹt ở 0 vì hệ số nền bị cố định, khiến mô
    hình không có tham số nào diễn tả được chênh lệch nhà-khách.
    """
    data = [
        MatchResult(home=f"T{i%6}", away=f"T{(i+3)%6}",
                    home_goals=2, away_goals=0, days_ago=i)
        for i in range(120)
    ]
    r = fit(data, xi=0.005, iterations=200, lr=0.15, reg=0.3)
    assert r.home_adv > 0.05, f"lợi thế sân nhà học ra quá thấp: {r.home_adv}"


def test_diem_brier_cang_doan_dung_cang_thap(pred):
    """Dự đoán trúng phải cho điểm thấp hơn dự đoán trượt."""
    x, y = pred.top_score
    trung = brier_score(pred, x, y)
    truot = brier_score(pred, 0, 5)
    assert trung < truot
