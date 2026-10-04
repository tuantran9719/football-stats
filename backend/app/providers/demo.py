"""
Nguồn dữ liệu đóng gói sẵn. Không gọi mạng, không phụ thuộc ai.

Đây KHÔNG phải đồ chơi. Nó có ba việc thật:

  1. CHỨNG MINH ranh giới trong base.py là có thật. Một giao diện chỉ có
     đúng một bản cài đặt thì không phải giao diện, nó là cái tên khác
     của bản cài đặt đó. Chỉ khi chạy được app bằng nguồn thứ hai mới
     biết chắc không còn chỗ nào bám cứng vào ESPN.

  2. ĐƯỜNG LÙI khi nguồn chính bị chặn. Đặt DATA_PROVIDER=demo thì app
     vẫn mở được, vẫn vào được mọi màn hình — chỉ là dữ liệu cũ. Hơn
     hẳn một màn hình trắng kèm thông báo lỗi.

  3. Chạy thử và quay video giới thiệu cho cửa hàng ứng dụng mà không
     phụ thuộc mạng hay việc hôm đó có trận hay không.

Dữ liệu bên dưới là hai đội và vài trận bịa, cố ý đặt tên rõ ràng là
hàng mẫu để không ai nhầm với số liệu thật.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from .base import LeagueCatalogue
from ..models import (
    GoalsSplit, CardsSplit, CornersSplit, Match, MatchDetail, MatchStats,
    MatchSplitStats, NewsItem, ProviderRef, Score, SideValue, StandingGroup,
    StandingRow, Team, TeamMatchStats,
)

PREFIX = "demo"


def _team(num: int, name: str, short: str) -> Team:
    return Team(
        id=f"{PREFIX}:{num}", name=name, shortName=short, logoUrl=None,
        refs=[ProviderRef(provider=PREFIX, externalId=str(num))],
    )


_TEAMS = [
    _team(1, "Đội Mẫu A", "MAU"), _team(2, "Đội Mẫu B", "MAB"),
    _team(3, "Đội Mẫu C", "MAC"), _team(4, "Đội Mẫu D", "MAD"),
]


def _match(idx: int, home: Team, away: Team, days: int, league: str,
           score: Optional[tuple[int, int]]) -> Match:
    when = datetime.now(timezone.utc) + timedelta(days=days)
    return Match(
        id=f"{PREFIX}:{idx}",
        leagueCode=league,
        season="2026",
        kickoffUtc=when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        status="finished" if score else "scheduled",
        home=home, away=away,
        score=Score(home=score[0], away=score[1]) if score else None,
        refs=[ProviderRef(provider=PREFIX, externalId=str(idx))],
    )


def _season() -> list[Match]:
    """Vài trận đã đá và vài trận sắp đá, đủ cho mọi màn hình có dữ liệu."""
    a, b, c, d = _TEAMS
    past = [
        (a, b, -21, (2, 1)), (c, d, -18, (0, 0)), (b, c, -14, (1, 3)),
        (d, a, -11, (2, 2)), (a, c, -7, (3, 0)), (b, d, -4, (1, 1)),
    ]
    future = [(a, b, 2), (c, d, 3), (b, c, 6), (d, a, 9)]
    out = [_match(100 + i, h, g, dd, "DEMO", s) for i, (h, g, dd, s) in enumerate(past)]
    out += [_match(200 + i, h, g, dd, "DEMO", None) for i, (h, g, dd) in enumerate(future)]
    return out


class DemoProvider:
    name = "demo"
    prefix = PREFIX

    def health(self) -> dict:
        return {"offline": True, "note": "nguồn mẫu, không gọi mạng"}

    def catalogue(self) -> LeagueCatalogue:
        return LeagueCatalogue(leagues={"DEMO": "Giải Mẫu"}, cups={}, logos={})

    async def aclose(self) -> None:
        return None

    async def list_matches(self, league: str, date: Optional[str] = None) -> list[Match]:
        games = _season()
        if not date:
            return games
        return [m for m in games if m.kickoffUtc[:10].replace("-", "") == date]

    async def list_upcoming_matches(self, league: str, limit: int = 12) -> list[Match]:
        return [m for m in _season() if m.status == "scheduled"][:limit]

    async def list_calendar(self, league: str) -> list[str]:
        return sorted({m.kickoffUtc[:10].replace("-", "") for m in _season()})

    async def list_teams(self, league: str) -> list[Team]:
        return list(_TEAMS)

    async def list_team_matches(
        self, league: str, team_external_id: str, seasons: list[str],
    ) -> list[Match]:
        want = f"{PREFIX}:{team_external_id}"
        return [m for m in _season() if want in (m.home.id, m.away.id)]

    async def list_standings(
        self, league: str,
    ) -> tuple[Optional[str], list[StandingGroup]]:
        rows = []
        for i, t in enumerate(_TEAMS):
            played, wins, draws = 6, 4 - i, 1
            losses = played - wins - draws
            gf, ga = 12 - i * 2, 5 + i
            rows.append(StandingRow(
                rank=i + 1, teamId=str(i + 1), teamName=t.name, shortName=t.shortName,
                logoUrl=None, played=played, wins=wins, draws=draws, losses=losses,
                goalsFor=gf, goalsAgainst=ga, goalDiff=gf - ga,
                points=wins * 3 + draws,
            ))
        return "2026", [StandingGroup(name="Bảng mẫu", rows=rows)]

    async def list_news(self, league: str, limit: int = 20) -> list[NewsItem]:
        return []

    async def get_match_detail(self, league: str, external_id: str) -> MatchDetail:
        wanted = f"{PREFIX}:{external_id}"
        match = next((m for m in _season() if m.id == wanted), None)
        if match is None:
            raise ValueError(f"[demo] không có trận {external_id}")

        stats = None
        if match.score is not None:
            stats = MatchStats(
                matchId=match.id,
                home=TeamMatchStats(corners=6, yellowCards=2),
                away=TeamMatchStats(corners=4, yellowCards=3),
            )
        return MatchDetail(match=match, events=[], stats=stats, odds=None, referee=None)
