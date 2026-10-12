"""
Bộ hỏi đáp: hiểu đúng câu trong phạm vi, và TỪ CHỐI câu ngoài phạm vi.

Bài quan trọng nhất ở đây là nhóm "ngoài phạm vi". Lúc mới dựng, câu
"hôm nay trời đẹp quá" bị gán vào ý định "ai thắng" với độ tin cậy
67% — không phải vì mô hình tin, mà vì nó không có cửa nào khác để đi.
Bot trả lời tự tin một câu hỏi không ai hỏi là cách nhanh nhất làm
người dùng mất tin vào mọi con số còn lại trong app.
"""
from __future__ import annotations

import pytest

from app.chat.answer import MatchContext
from app.chat.classifier import classify, seed_model
from app.chat.engine import reply
from app.chat.intents import MIN_CONFIDENCE
from app.chat.normalize import normalize
from app.chat.slots import extract
from app.predictor.model import Ratings, predict


@pytest.fixture(scope="module")
def model():
    return seed_model()


@pytest.fixture(scope="module")
def ctx():
    r = Ratings(attack={"A": 0.3, "B": -0.1}, defence={"A": -0.2, "B": 0.1},
                home_adv=0.17, rho=-0.05, matches=1373, intercept=0.1)
    return MatchContext(
        home="SAO", away="SAN", home_full="Sao Paulo", away_full="Santos",
        prediction=predict(r, "A", "B"), learned_matches=1373,
        expected_corners=11.1, expected_cards=4.9, first_half_pct=40.0,
        home_form=["W", "D", "L", "W", "W"], away_form=["L", "L", "W", "D", "W"],
        source="TEST",
    )


# ---- Chuẩn hoá chữ -------------------------------------------------

@pytest.mark.parametrize("gõ,mong_đợi", [
    ("Trận này mấy bàn?", "tran nay may ban"),
    ("tran nay may ban ko", "tran nay may ban khong"),
    ("Trên 2,5 bàn có ăn ko", "tren 2.5 ban co an khong"),
    ("Tỉ số bao nhiêu", "ty so bao nhieu"),
    ("tỷ số", "ty so"),
])
def test_moi_cach_go_ve_cung_mot_dang(gõ, mong_đợi):
    assert normalize(gõ) == mong_đợi


# ---- Phân loại ý định ----------------------------------------------

TRONG_PHAM_VI = [
    ("trận này mấy bàn", "total_goals"),
    ("ai thắng", "outcome"),
    ("trên 2.5 bàn có ăn ko", "over_under"),
    ("ti so bn", "score"),
    ("hai doi cung ghi ban khong", "btts"),
    ("may qua phat goc", "corners"),
    ("the vang bao nhieu", "cards"),
    ("phong do doi nha", "form"),
    ("ai chan thuong", "injuries"),
    ("may gio da", "kickoff"),
    ("chap 1.5 qua khong", "handicap"),
    ("hiep nao nhieu ban hon", "halves"),
    ("dung thu may", "standings"),
    ("doi dau", "h2h"),
    ("chinh xac khong", "model_info"),
    ("doi nha co giu sach luoi khong", "clean_sheet"),
    ("doi khach ghi may ban", "team_goals"),
]


@pytest.mark.parametrize("câu,ý_định", TRONG_PHAM_VI)
def test_hieu_dung_cau_trong_pham_vi(model, câu, ý_định):
    got, conf, _ = classify(model, câu)
    assert got == ý_định, f"{câu!r} → {got} ({conf:.0%})"


NGOAI_PHAM_VI = [
    "hom nay troi dep qua", "messi hay ronaldo gioi hon", "xin chao",
    "xem truc tiep o dau", "toi muon nap tien", "giá vàng hôm nay",
    "ke chuyen cuoi di", "ban ten gi", "bong ro co hay khong", "abcxyz",
]


@pytest.mark.parametrize("câu", NGOAI_PHAM_VI)
def test_khong_tra_loi_bua_cau_ngoai_pham_vi(model, câu):
    got, conf, _ = classify(model, câu)
    lọt = got not in ("unknown", "other") and conf >= MIN_CONFIDENCE
    assert not lọt, f"{câu!r} bị gán nhầm vào {got} với {conf:.0%}"


def test_do_chinh_xac_tren_phan_giu_lai_khong_tut(model):
    """Chốt chặn cho vòng tự học: bộ phân loại mới không được kém đi.

    Ngưỡng đặt dưới mức đo được một chút, vì phần giữ lại nhỏ nên con
    số dao động nhẹ giữa các lần chia.
    """
    assert model.accuracy >= 0.75, f"chính xác tụt còn {model.accuracy:.0%}"


# ---- Rút tham số ---------------------------------------------------

@pytest.mark.parametrize("câu,mốc,dưới,bên", [
    ("trên 2.5 bàn", 2.5, False, None),
    ("dưới 3.5 bàn có ăn ko", 3.5, True, None),
    ("xỉu 2.5", 2.5, True, None),
    ("đội nhà ghi mấy bàn", None, False, "home"),
    ("đội khách có giữ sạch lưới không", None, False, "away"),
    ("Arsenal ghi mấy bàn", None, False, "home"),
    ("chấp -1.5 qua không", -1.5, False, None),
])
def test_rut_dung_moc_va_doi(câu, mốc, dưới, bên):
    s = extract(câu, "Arsenal", "Leeds United", "ARS", "LEE")
    assert s.line == mốc and s.under is dưới and s.side == bên


def test_cau_nhac_ca_hai_doi_thi_khong_doan_bua():
    s = extract("arsenal gap leeds ai thang", "Arsenal", "Leeds United", "ARS", "LEE")
    assert s.side is None


# ---- Trả lời -------------------------------------------------------

async def test_bam_nut_khong_qua_bo_phan_loai(ctx):
    r = await reply(ctx, "vi", intent="corners")
    assert r.intent == "corners" and r.confidence == 1.0


async def test_cau_nhac_ten_doi_hoi_rieng_doi_do(ctx):
    """'santos ghi mấy bàn' phải hỏi riêng Santos, không phải tổng cả trận."""
    r = await reply(ctx, "vi", question="santos ghi may ban")
    assert r.intent == "team_goals"
    assert "SAN" in r.text


async def test_cau_lac_de_khong_xin_day(ctx):
    """Câu lạc đề hẳn thì không nhờ người dùng gán nhãn — gán nhãn cho
    nó chỉ làm bẩn dữ liệu huấn luyện."""
    r = await reply(ctx, "vi", question="xem truc tiep o dau")
    assert r.intent == "unknown"
    assert r.asking_back is False
    assert len(r.suggestions) == 3


async def test_moi_y_dinh_deu_tra_loi_duoc(ctx):
    from app.chat.intents import ALL_INTENTS
    for ý in ALL_INTENTS:
        r = await reply(ctx, "vi", intent=ý)
        assert r.text.strip(), f"ý định {ý} trả về câu rỗng"


async def test_khong_co_mo_hinh_thi_noi_that_chu_khong_bia():
    trống = MatchContext(home="A", away="B")
    r = await reply(trống, "vi", intent="outcome")
    assert "chưa" in r.text.lower()
    assert "%" not in r.text, "không được bịa ra con số khi chưa có mô hình"


async def test_chan_thuong_noi_khong_co_du_lieu(ctx):
    """Nguồn không công bố danh sách chấn thương. Bot phải nói thẳng là
    không có, tuyệt đối không suy từ đội hình trận trước."""
    r = await reply(ctx, "vi", intent="injuries")
    assert "không" in r.text.lower()
    assert r.action == "lineups"


async def test_ten_nguon_lay_tu_ngoai_vao_khong_viet_cung(ctx):
    r = await reply(ctx, "vi", intent="model_info")
    assert "TEST" in r.text, "tên nguồn phải theo ctx.source, không nhúng cứng"
