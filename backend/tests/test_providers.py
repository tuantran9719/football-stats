"""
Ranh giới nguồn dữ liệu, và những hình dạng dữ liệu đã từng làm sập app.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.providers import get_provider, strip_ref, team_ref
from app.providers.base import FootballProvider, LeagueCatalogue
from app.providers.demo import DemoProvider
from app.providers.espn import EspnProvider

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("lớp", [EspnProvider, DemoProvider])
def test_moi_nguon_deu_thoa_hop_dong(lớp):
    """Giao diện chỉ có một bản cài đặt thì không phải giao diện."""
    assert isinstance(lớp(), FootballProvider)


@pytest.mark.parametrize("lớp", [EspnProvider, DemoProvider])
def test_moi_nguon_deu_khai_danh_muc_giai(lớp):
    cat = lớp().catalogue()
    assert isinstance(cat, LeagueCatalogue)
    assert cat.leagues, "nguồn phải phục vụ ít nhất một giải"
    mã = next(iter(cat.leagues))
    assert cat.knows(mã) and cat.display_name(mã)


@pytest.mark.parametrize("lớp", [EspnProvider, DemoProvider])
def test_moi_nguon_co_tien_to_rieng(lớp):
    """Mã đội hai nguồn không trùng nhau. Tiền tố khiến mã cũ không
    khớp nữa khi đổi nguồn — cố ý, vì khớp nhầm sang một đội khác còn
    tệ hơn mất."""
    p = lớp()
    assert p.prefix and ":" not in p.prefix


def test_ma_doi_luon_co_tien_to_nguon_dang_chay():
    mã = team_ref("359")
    assert mã == f"{get_provider().prefix}:359"
    assert strip_ref(mã) == "359"
    assert strip_ref("359") == "359", "mã không tiền tố thì giữ nguyên"


def test_khong_file_nao_ngoai_providers_nhac_ten_nguon():
    """Chốt chặn tự động cho ranh giới nguồn dữ liệu.

    Ranh giới kiểu này luôn mục dần: một lần ai đó viết nhanh
    f"espn:{id}" cho xong việc thì mọi thứ VẪN CHẠY ĐÚNG, vì đang dùng
    ESPN. Nó chỉ nổ vào đúng ngày phải đổi nguồn.
    """
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_provider_seam.py")],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert r.returncode == 0, r.stdout + r.stderr


# ---- Hình dạng dữ liệu đã từng làm sập app -------------------------

CUP_SCOREBOARD = {
    # Cúp châu Âu trả MỘT object mô tả các giai đoạn, không phải danh
    # sách chuỗi ngày như giải quốc nội. Mã cũ cắt chuỗi d[:10] trên
    # object này và ném KeyError, làm chết hẳn mục "Sắp diễn ra" của
    # Champions League, Europa League và Conference League.
    "leagues": [{"calendar": [{
        "label": "UEFA Champions League",
        "startDate": "2026-07-01T04:00Z",
        "entries": [{"label": "League Phase", "value": "1"}],
    }]}],
    "events": [],
}

LEAGUE_SCOREBOARD = {
    "leagues": [{"calendar": ["2026-10-13T00:00Z", "2026-10-14T00:00Z"]}],
    "events": [],
}


@pytest.mark.parametrize("payload,tên", [
    (CUP_SCOREBOARD, "giải cúp (lịch dạng giai đoạn)"),
    (LEAGUE_SCOREBOARD, "giải quốc nội (lịch dạng chuỗi ngày)"),
    ({"leagues": [{}], "events": []}, "không có lịch"),
    ({}, "phản hồi rỗng"),
])
async def test_lich_thi_dau_du_hinh_dang_nao_cung_khong_sap(monkeypatch, payload, tên):
    p = EspnProvider()

    async def giả_lập(self, path, **kw):
        return payload

    monkeypatch.setattr(EspnProvider, "_get", giả_lập)
    # Không được ném lỗi, dù trả về rỗng cũng chấp nhận được.
    assert isinstance(await p.list_upcoming_matches("UCL"), list)
    assert isinstance(await p.list_calendar("UCL"), list)
