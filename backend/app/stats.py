"""
Tính toán thống kê theo hiệp và tổng hợp qua N trận gần nhất.

Đây là lõi nghiệp vụ. Cổng lại nguyên vẹn logic từ packages/core-stats
của bản Node trước đây, giữ đúng các quy ước quan trọng:
  - Phạt góc: nếu có sự kiện phạt góc kèm mốc phút thì tách được theo
    hiệp như bàn thắng và thẻ; không có thì first/second để None (KHÔNG
    phải 0 — None nghĩa là "không biết", 0 nghĩa là "có biết, bằng 0").
  - Khi tính trung bình, trận thiếu dữ liệu bị loại khỏi phép chia chứ
    không tính là 0, tránh kéo lệch kết quả.
"""
from __future__ import annotations
from typing import Callable, Optional

from .models import (
    CardCount, CardsSplit, GoalsSplit, Match, MatchEvent, MatchSplitStats,
    MatchStats, SideCards, SideValue,
)

GOAL_TYPES = {"goal", "penalty_goal"}


def _empty_side() -> SideValue:
    return SideValue(home=0, away=0)


def _empty_cards() -> SideCards:
    return SideCards(
        home=CardCount(yellow=0, red=0),
        away=CardCount(yellow=0, red=0),
    )


def compute_match_split(
    match: Match, events: list[MatchEvent], stats: Optional[MatchStats] = None,
) -> MatchSplitStats:
    goals = {"first": _empty_side(), "second": _empty_side(), "full": _empty_side()}
    cards = {"first": _empty_cards(), "second": _empty_cards(), "full": _empty_cards()}
    corners = {"first": _empty_side(), "second": _empty_side(), "full": _empty_side()}
    has_corner_events = False

    for ev in events:
        slot = "first" if ev.period == "first" else "second"

        if ev.type in GOAL_TYPES:
            setattr(goals[slot], ev.side, getattr(goals[slot], ev.side) + 1)
            setattr(goals["full"], ev.side, getattr(goals["full"], ev.side) + 1)
        elif ev.type == "own_goal":
            other = "away" if ev.side == "home" else "home"
            setattr(goals[slot], other, getattr(goals[slot], other) + 1)
            setattr(goals["full"], other, getattr(goals["full"], other) + 1)
        elif ev.type == "yellow_card":
            side_cards = getattr(cards[slot], ev.side)
            side_cards.yellow += 1
            getattr(cards["full"], ev.side).yellow += 1
        elif ev.type in ("red_card", "second_yellow"):
            side_cards = getattr(cards[slot], ev.side)
            side_cards.red += 1
            getattr(cards["full"], ev.side).red += 1
        elif ev.type == "corner":
            has_corner_events = True
            setattr(corners[slot], ev.side, getattr(corners[slot], ev.side) + 1)
            setattr(corners["full"], ev.side, getattr(corners["full"], ev.side) + 1)

    return MatchSplitStats(
        matchId=match.id,
        goals=GoalsSplit(first=goals["first"], second=goals["second"], full=goals["full"]),
        cards=CardsSplit(first=cards["first"], second=cards["second"], full=cards["full"]),
        corners=_corners_split(corners, has_corner_events, stats),
    )


def _corners_split(corners: dict, has_events: bool, stats: Optional[MatchStats]):
    """
    Ưu tiên đếm từ sự kiện phạt góc vì chỉ cách đó mới tách được theo hiệp.
    Không có sự kiện nào (trận cũ, giải nhỏ, ESPN không viết tường thuật)
    thì lùi về tổng cả trận của boxscore và để hai hiệp là None.

    Tổng cả trận vẫn lấy từ boxscore khi có: đó là con số chính thức, còn
    đếm từ tường thuật có thể sót nếu ESPN ghi thiếu một dòng.
    """
    from .models import CornersSplit

    box_full = None
    if stats and (stats.home.corners is not None or stats.away.corners is not None):
        box_full = SideValue(
            home=int(stats.home.corners or 0),
            away=int(stats.away.corners or 0),
        )

    if not has_events:
        return CornersSplit(first=None, second=None, full=box_full or _empty_side())

    return CornersSplit(
        first=corners["first"],
        second=corners["second"],
        full=box_full or corners["full"],
    )


def last_n_matches(matches: list[Match], n: int) -> list[Match]:
    finished = [m for m in matches if m.status == "finished"]
    finished.sort(key=lambda m: m.kickoffUtc, reverse=True)
    return finished[:n]


def side_of(match: Match, team_id: str) -> Optional[str]:
    if match.home.id == team_id:
        return "home"
    if match.away.id == team_id:
        return "away"
    return None


Extractor = Callable[[MatchSplitStats, str], dict]


def _goals_for(s: MatchSplitStats, side: str) -> dict:
    return {
        "first": getattr(s.goals.first, side) if s.goals.first else None,
        "second": getattr(s.goals.second, side) if s.goals.second else None,
        "full": getattr(s.goals.full, side),
    }


def _goals_against(s: MatchSplitStats, side: str) -> dict:
    other = "away" if side == "home" else "home"
    return {
        "first": getattr(s.goals.first, other) if s.goals.first else None,
        "second": getattr(s.goals.second, other) if s.goals.second else None,
        "full": getattr(s.goals.full, other),
    }


def _corners(s: MatchSplitStats, side: str) -> dict:
    return {
        "first": getattr(s.corners.first, side) if s.corners.first else None,
        "second": getattr(s.corners.second, side) if s.corners.second else None,
        "full": getattr(s.corners.full, side),
    }


def _yellow_cards(s: MatchSplitStats, side: str) -> dict:
    return {
        "first": getattr(s.cards.first, side).yellow if s.cards.first else None,
        "second": getattr(s.cards.second, side).yellow if s.cards.second else None,
        "full": getattr(s.cards.full, side).yellow,
    }


def _red_cards(s: MatchSplitStats, side: str) -> dict:
    return {
        "first": getattr(s.cards.first, side).red if s.cards.first else None,
        "second": getattr(s.cards.second, side).red if s.cards.second else None,
        "full": getattr(s.cards.full, side).red,
    }


EXTRACTORS: dict[str, Extractor] = {
    "goalsFor": _goals_for,
    "goalsAgainst": _goals_against,
    "corners": _corners,
    "yellowCards": _yellow_cards,
    "redCards": _red_cards,
}


def aggregate(rows: list[tuple[MatchSplitStats, str]], extract: Extractor):
    from .models import AggregatedStats

    sum_first = n_first = 0
    sum_second = n_second = 0
    sum_full = n_full = 0

    for split, side in rows:
        v = extract(split, side)
        if v["first"] is not None:
            sum_first += v["first"]
            n_first += 1
        if v["second"] is not None:
            sum_second += v["second"]
            n_second += 1
        sum_full += v["full"]
        n_full += 1

    def avg(total, n):
        return round(total / n, 2) if n else None

    return AggregatedStats(
        sampleSize=len(rows),
        withData=n_full,
        avgFirst=avg(sum_first, n_first),
        avgSecond=avg(sum_second, n_second),
        avgFull=avg(sum_full, n_full) or 0,
    )
