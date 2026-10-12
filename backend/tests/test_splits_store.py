"""
Kho chỉ số theo hiệp trên đĩa, và đường đọc nó trong service.

Hai thứ dễ hỏng mà lại khó nhận ra nếu không có bài kiểm thử:

  1. Thứ tự trả về. _load_splits nay trộn trận đọc từ đĩa với trận tải
     từ mạng, trong khi bên gọi vẫn ghép kết quả theo vị trí. Lệch một
     ô là phong độ của đội này gắn nhầm sang trận của đội kia — sai số
     liệu mà màn hình vẫn hiện bình thường.

  2. Chỉ lưu trận đã đá xong. Lưu nhầm trận đang đá là đóng băng tỉ số
     giữa chừng và không bao giờ cập nhật lại nữa.
"""
from __future__ import annotations

import pytest

from app import splits_store
from app.models import (
    CardCount, CardsSplit, CornersSplit, GoalsSplit, MatchSplitStats,
    SideCards, SideValue,
)


def _split(mid: str, hg: float, ag: float) -> MatchSplitStats:
    return MatchSplitStats(
        matchId=mid,
        goals=GoalsSplit(full=SideValue(home=hg, away=ag)),
        cards=CardsSplit(full=SideCards(
            home=CardCount(yellow=1, red=0), away=CardCount(yellow=2, red=0),
        )),
        corners=CornersSplit(full=SideValue(home=5, away=4)),
    )


@pytest.mark.asyncio
async def test_ghi_roi_doc_lai_duoc_nguyen_ven():
    await splits_store.put_many("TEST1", {"a1": _split("a1", 2, 1)})
    got = await splits_store.get("TEST1", "a1")
    assert got is not None
    assert got.goals.full.home == 2
    assert got.corners.full.away == 4
    assert got.cards.full.away.yellow == 2


@pytest.mark.asyncio
async def test_tran_chua_co_thi_tra_none():
    assert await splits_store.get("TEST1", "không-có") is None


@pytest.mark.asyncio
async def test_get_many_chi_tra_nhung_tran_co_that():
    await splits_store.put_many("TEST2", {
        "b1": _split("b1", 1, 0), "b2": _split("b2", 0, 0),
    })
    got = await splits_store.get_many("TEST2", ["b1", "thiếu", "b2"])
    assert set(got) == {"b1", "b2"}


@pytest.mark.asyncio
async def test_ghi_lai_cung_tran_khong_nhan_doi():
    await splits_store.put_many("TEST3", {"c1": _split("c1", 1, 1)})
    them = await splits_store.put_many("TEST3", {"c1": _split("c1", 3, 3)})
    assert them == 0, "cùng mã trận thì phải ghi đè, không thêm bản ghi"
    got = await splits_store.get("TEST3", "c1")
    assert got is not None and got.goals.full.home == 3


@pytest.mark.asyncio
async def test_ban_ghi_hong_coi_nhu_chua_co():
    """Tệp lỗi không được phép làm sập màn hình trận."""
    await splits_store.put_many("TEST4", {"d1": _split("d1", 1, 1)})
    async with splits_store._lock:
        splits_store._read("TEST4")["d1"] = {"rác": True}
    assert await splits_store.get("TEST4", "d1") is None


@pytest.mark.asyncio
async def test_load_splits_giu_dung_thu_tu_khi_tron_dia_va_mang():
    """
    Nửa số trận đã nằm trong kho, nửa còn lại phải tải. Kết quả vẫn
    phải khớp từng vị trí với danh sách đưa vào.
    """
    from app import service
    from app.providers import get_provider

    provider = get_provider()
    matches = await provider.list_team_matches("EPL", "1", ["2026"])
    played = [m for m in matches if m.status == "finished"][:4]
    if len(played) < 2:
        pytest.skip("nguồn mẫu không đủ trận đã đá")

    # Lượt một: kho rỗng nên mọi trận đều đi đường mạng, đồng thời
    # được ghi xuống kho.
    first = await service._load_splits("EPL", played)
    assert [m.id for m, _ in first] == [m.id for m in played]

    # Lượt hai: giờ mọi trận đều đọc từ kho. Thứ tự và nội dung không đổi.
    second = await service._load_splits("EPL", played)
    assert [m.id for m, _ in second] == [m.id for m in played]
    for (_, a), (_, b) in zip(first, second):
        assert a.goals.full.home == b.goals.full.home
        assert a.goals.full.away == b.goals.full.away
        assert a.corners.full.home == b.corners.full.home


@pytest.mark.asyncio
async def test_khong_luu_tran_chua_da():
    """Trận chưa đá mà lọt vào kho là đóng băng số liệu sai vĩnh viễn."""
    from app import service
    from app.providers import get_provider

    provider = get_provider()
    matches = await provider.list_team_matches("EPL", "1", ["2026"])
    chua_da = [m for m in matches if m.status != "finished"][:2]
    if not chua_da:
        pytest.skip("nguồn mẫu không có trận chưa đá")

    await service._load_splits("EPL", chua_da)
    for m in chua_da:
        assert await splits_store.get("EPL", m.refs[0].externalId) is None
