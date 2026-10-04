"""
Adapter cho nguồn ESPN.

Toàn bộ hiểu biết về cấu trúc JSON của ESPN chỉ nằm trong file này.
Đổi sang nguồn khác thì viết file tương tự, không đụng vào nơi nào khác.

Ba điều đã kiểm chứng thực tế, đừng đổi nếu không thử lại:
  1. ESPN trả 403 nếu User-Agent giả dạng trình duyệt (bắt đầu bằng
     Mozilla). Để trống hoặc dùng chuỗi khác thì được chấp nhận.
  2. Tỷ số của trận CHƯA đá là chuỗi "0", không phải để trống. Chỉ coi
     là có tỷ số thật khi trạng thái là live, halftime, hoặc finished.
  3. Không có tham số "N trận sắp tới". Cách lấy: gọi scoreboard một lần
     để đọc trường leagues[0].calendar, đây là lịch toàn mùa. Lọc ra các
     ngày sau hôm nay, lấy vài ngày gần nhất, rồi gọi scoreboard cho
     từng ngày đó.
"""
from __future__ import annotations
import asyncio
import random
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from ..models import (
    LineupPlayer, Match, MatchDetail, MatchEvent, MatchOdds, MatchStats, ProviderRef,
    StandingGroup, StandingRow, Team, TeamLineup, TeamMatchStats,
)
from .base import ProviderBusy
from .sources import ESPN_BASE, ESPN_LEAGUE_CODES, ESPN_V2_BASE

STATUS_MAP = {
    "STATUS_SCHEDULED": "scheduled",
    "STATUS_IN_PROGRESS": "live",
    "STATUS_FIRST_HALF": "live",
    "STATUS_SECOND_HALF": "live",
    "STATUS_HALFTIME": "halftime",
    "STATUS_FULL_TIME": "finished",
    "STATUS_FINAL": "finished",
    "STATUS_POSTPONED": "postponed",
    "STATUS_CANCELED": "cancelled",
}

EVENT_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"own goal", re.I), "own_goal"),
    (re.compile(r"penalty.*(scored|goal)", re.I), "penalty_goal"),
    (re.compile(r"penalty.*(missed|saved)", re.I), "penalty_missed"),
    (re.compile(r"goal", re.I), "goal"),
    (re.compile(r"second yellow|yellow.*red", re.I), "second_yellow"),
    (re.compile(r"yellow card", re.I), "yellow_card"),
    (re.compile(r"red card", re.I), "red_card"),
    (re.compile(r"substitut", re.I), "substitution"),
    (re.compile(r"kickoff|start", re.I), "period_start"),
    (re.compile(r"halftime|end", re.I), "period_end"),
]

STAT_KEYS = {
    "wonCorners": "corners",
    "totalShots": "shots",
    "shotsOnTarget": "shotsOnTarget",
    "foulsCommitted": "fouls",
    "offsides": "offsides",
    "possessionPct": "possessionPct",
    "yellowCards": "yellowCards",
    "redCards": "redCards",
    "saves": "saves",
    "passPct": "passPct",
    "accuratePasses": "accuratePasses",
    "totalPasses": "totalPasses",
    "totalTackles": "tackles",
    "interceptions": "interceptions",
}

# Tên chỉ số trong bảng xếp hạng của ESPN. Lưu ý "pointsFor"/"pointsAgainst"
# ở môn bóng đá chính là bàn thắng/bàn thua, không phải điểm số.
STANDING_KEYS = {
    "gamesPlayed": "played",
    "wins": "wins",
    "ties": "draws",
    "losses": "losses",
    "pointsFor": "goalsFor",
    "pointsAgainst": "goalsAgainst",
    "pointDifferential": "goalDiff",
    "points": "points",
    "rank": "rank",
}


def parse_clock(raw: Optional[str]) -> Optional[tuple[int, Optional[int]]]:
    """"45'+2'" -> (45, 2). Trả None nếu không đọc được."""
    if not raw:
        return None
    main, _, extra = raw.partition("+")
    digits = "".join(ch for ch in main if ch.isdigit())
    if not digits:
        return None
    minute = int(digits)
    extra_digits = "".join(ch for ch in extra if ch.isdigit())
    extra_minute = int(extra_digits) if extra_digits else None
    return minute, extra_minute


def period_of(minute: int) -> str:
    if minute <= 45:
        return "first"
    if minute <= 90:
        return "second"
    if minute <= 105:
        return "et1"
    return "et2"


def map_event_type(text: Optional[str]) -> str:
    if not text:
        return "other"
    for pattern, kind in EVENT_MAP:
        if pattern.search(text):
            return kind
    return "other"


def _to_team(c: dict[str, Any]) -> Team:
    t = c["team"]
    return Team(
        id=f"espn:{t['id']}",
        name=t["displayName"],
        shortName=t.get("abbreviation"),
        logoUrl=t.get("logo") or (t.get("logos") or [{}])[0].get("href"),
        refs=[ProviderRef(provider="espn", externalId=t["id"])],
    )


def _num_score(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        v = v.get("value")
        return float(v) if v is not None else None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_team_stats(stats: list[dict[str, Any]]) -> TeamMatchStats:
    out: dict[str, float] = {}
    for s in stats or []:
        key = STAT_KEYS.get(s.get("name"))
        if not key:
            continue
        raw = str(s.get("displayValue", "")).replace("%", "")
        try:
            out[key] = float(raw)
        except ValueError:
            continue

    # ESPN không nhất quán: possessionPct trả về 46.2 (đã là phần trăm)
    # còn passPct trả về 0.8 (tỉ lệ). Quy hết về phần trăm ngay tại đây
    # để giao diện không phải biết chỗ nào nhân trăm, chỗ nào không.
    for pct_key in ("passPct",):
        v = out.get(pct_key)
        if v is not None and v <= 1:
            out[pct_key] = round(v * 100, 1)

    return TeamMatchStats(**out)


def _to_lineups(rosters: list[dict[str, Any]]) -> list[TeamLineup]:
    """
    Đội hình ra sân. ESPN chỉ công bố trước giờ bóng lăn chừng một tiếng,
    trước đó rosters rỗng hoặc thiếu cờ starter — khi đó trả về danh sách
    rỗng để giao diện ẩn hẳn mục này thay vì hiện một khung trống.
    """
    out: list[TeamLineup] = []
    for r in rosters or []:
        players = r.get("roster") or []
        if not players:
            continue
        starters: list[LineupPlayer] = []
        bench: list[LineupPlayer] = []
        for p in players:
            ath = p.get("athlete") or {}
            name = ath.get("displayName") or ath.get("shortName")
            if not name:
                continue
            headshot = (ath.get("headshot") or {}).get("href")
            pos = ((p.get("position") or {}).get("abbreviation")
                   or (ath.get("position") or {}).get("abbreviation"))

            # Số liệu từng cầu thủ nằm trong một danh sách {name, value}
            # chứ không phải các trường riêng, nên gom về từ điển trước.
            stats: dict[str, float] = {}
            for s in (p.get("stats") or []):
                key = s.get("name")
                raw = s.get("value", s.get("displayValue"))
                if not key:
                    continue
                try:
                    stats[key] = float(raw)
                except (TypeError, ValueError):
                    continue

            def n(key: str) -> int:
                return int(stats.get(key, 0) or 0)

            place = p.get("formationPlace")
            try:
                place_num = int(place) if place is not None else None
            except (TypeError, ValueError):
                place_num = None

            player = LineupPlayer(
                name=name,
                shortName=ath.get("shortName"),
                jersey=str(p["jersey"]) if p.get("jersey") else None,
                position=pos,
                starter=bool(p.get("starter")),
                photoUrl=headshot,
                formationPlace=place_num,
                subbedIn=bool(p.get("subbedIn")),
                subbedOut=bool(p.get("subbedOut")),
                goals=n("totalGoals"),
                assists=n("goalAssists"),
                shots=n("totalShots"),
                shotsOnTarget=n("shotsOnTarget"),
                yellowCards=n("yellowCards"),
                redCards=n("redCards"),
                ownGoals=n("ownGoals"),
                foulsCommitted=n("foulsCommitted"),
                foulsSuffered=n("foulsSuffered"),
                offsides=n("offsides"),
                saves=n("saves"),
                goalsConceded=n("goalsConceded"),
            )
            (starters if player.starter else bench).append(player)
        if not starters:
            continue
        out.append(TeamLineup(
            side="home" if r.get("homeAway") == "home" else "away",
            teamName=(r.get("team") or {}).get("displayName") or "",
            formation=r.get("formation"),
            starters=starters,
            bench=bench,
        ))
    return out


def _to_odds(raw: list[dict[str, Any]]) -> Optional[MatchOdds]:
    """
    Vạch kèo của nhà cung cấp đầu tiên ESPN liệt kê (đã sắp theo priority).

    Chỉ lấy các con số; mảng links dẫn sang nhà cái thì bỏ hẳn — xem ghi
    chú ở model MatchOdds.
    """
    if not raw:
        return None
    o = raw[0]

    def money(block: Optional[dict[str, Any]]) -> Optional[int]:
        v = (block or {}).get("moneyLine")
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    def num(v: Any) -> Optional[float]:
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    return MatchOdds(
        provider=((o.get("provider") or {}).get("name")),
        overUnder=num(o.get("overUnder")),
        spread=num(o.get("spread")),
        details=o.get("details"),
        homeMoneyLine=money(o.get("homeTeamOdds")),
        awayMoneyLine=money(o.get("awayTeamOdds")),
        drawMoneyLine=money(o.get("drawOdds")),
    )


class EspnRateLimited(ProviderBusy):
    """ESPN từ chối vì gọi quá dày. Tầng cache bắt lỗi này để lấy bản cũ."""


# Không quá ngần này lượt gọi ESPN cùng lúc cho toàn bộ tiến trình.
#
# Sáu chứ không phải bốn: bảng soi kèo cần 10 trận gần nhất của cả hai
# đội, mỗi trận một lượt gọi, nên mức bốn khiến lần tải nguội mất hơn
# mười giây. Sáu vẫn thấp hơn nhiều so với một trình duyệt bình thường
# mở trang ESPN, và cầu dao 429 bên dưới vẫn là lớp chặn cuối.
_GATE = asyncio.Semaphore(6)
_MAX_RETRY = 3
_COOLDOWN = 90.0
_cooldown_until = 0.0


def espn_health() -> dict:
    remaining = max(0.0, _cooldown_until - time.time())
    return {"rateLimited": remaining > 0, "cooldownSeconds": round(remaining, 1)}


class EspnProvider:
    name = "espn"
    # Tiền tố gắn vào mọi mã đội/trận sinh ra từ nguồn này. Xem
    # providers/base.py về lý do mỗi nguồn phải có tiền tố riêng.
    prefix = "espn"

    def health(self) -> dict:
        return espn_health()

    def catalogue(self) -> "LeagueCatalogue":
        from .base import LeagueCatalogue
        from .sources import CUP_LEAGUES, LEAGUES, league_logo_url
        return LeagueCatalogue(
            leagues=dict(LEAGUES),
            cups=dict(CUP_LEAGUES),
            logos={c: u for c in (*LEAGUES, *CUP_LEAGUES)
                   if (u := league_logo_url(c)) is not None},
        )

    def __init__(self) -> None:
        # ESPN chan User-Agent gia dang trinh duyet. De client mac dinh.
        self._client = httpx.AsyncClient(timeout=30.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _league(self, code: str) -> str:
        lg = ESPN_LEAGUE_CODES.get(code)
        if not lg:
            raise ValueError(f"[espn] chưa ánh xạ giải {code}")
        return lg

    async def _get(self, path: str, base: Optional[str] = None) -> dict[str, Any]:
        """
        Gọi ESPN kèm ba lớp tự bảo vệ, vì đây là API không chính thức và
        không có hạn mức công bố: bị coi là gọi quá dày thì Cloudflare
        trước ESPN trả 429 hoặc 403 tạm thời cho cả IP.

          - Chặn số lượt gọi song song (_GATE). Trang "tất cả các giải"
            bắn 12 lượt cùng lúc; đi thành từng nhóm nhỏ trông giống người
            dùng thật hơn nhiều so với một chùm 12 request cùng một giây.
          - Cầu dao. Dính 429 một lần là nghỉ hẳn _COOLDOWN giây, mọi lượt
            gọi trong lúc đó bị từ chối ngay tại chỗ để tầng cache lấy bản
            cũ ra dùng, thay vì tiếp tục đâm vào tường.
          - Thử lại có giãn cách với nhiễu ngẫu nhiên, chỉ cho lỗi tạm
            thời (429, 5xx, đứt mạng). Lỗi 4xx khác là sai đường dẫn,
            thử lại bao nhiêu lần cũng vậy nên trả lỗi luôn.
        """
        global _cooldown_until
        if time.time() < _cooldown_until:
            raise EspnRateLimited(
                f"[espn] đang tạm nghỉ {int(_cooldown_until - time.time())}s sau khi bị 429"
            )

        url = f"{base or ESPN_BASE}{path}"
        last: Optional[Exception] = None
        for attempt in range(_MAX_RETRY):
            try:
                async with _GATE:
                    res = await self._client.get(url)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last = exc
            else:
                if res.status_code == 429 or res.status_code == 403:
                    _cooldown_until = time.time() + _COOLDOWN
                    raise EspnRateLimited(f"[espn] {res.status_code} cho {path}")
                if res.status_code < 500:
                    res.raise_for_status()
                    return res.json()
                last = httpx.HTTPStatusError(
                    f"[espn] {res.status_code}", request=res.request, response=res,
                )

            if attempt < _MAX_RETRY - 1:
                # Giãn cách gấp đôi mỗi lần, cộng nhiễu để nhiều tiến
                # trình cùng lỗi không thử lại trùng nhau.
                await asyncio.sleep(0.4 * (2 ** attempt) + random.random() * 0.3)

        assert last is not None
        raise last

    def _to_match(self, e: dict[str, Any], league: str) -> Match:
        comp = (e.get("competitions") or [{}])[0]
        comps = comp.get("competitors") or []
        home = next((c for c in comps if c.get("homeAway") == "home"), None)
        away = next((c for c in comps if c.get("homeAway") == "away"), None)
        if not home or not away:
            raise ValueError(f"[espn] thiếu đội trong trận {e.get('id')}")

        status_name = (comp.get("status") or {}).get("type", {}).get("name") \
            or (e.get("status") or {}).get("type", {}).get("name") or ""
        kickoff = comp.get("date") or e.get("date") or datetime.now(timezone.utc).isoformat()
        status = STATUS_MAP.get(status_name, "scheduled")

        # Trận chưa diễn ra: ESPN trả score="0" dạng chuỗi thay vì để trống.
        has_started = status in ("live", "halftime", "finished")
        hs = _num_score(home.get("score"))
        as_ = _num_score(away.get("score"))
        score = None
        if has_started and hs is not None and as_ is not None:
            from ..models import Score
            score = Score(home=int(hs), away=int(as_))

        # displayClock vẫn còn giá trị sau khi trận kết thúc ("90'+5'"),
        # hiển thị ra thì người xem tưởng trận đang đá. Chỉ lấy khi trận
        # thật sự đang diễn ra.
        st = comp.get("status") or e.get("status") or {}
        clock = None
        period = None
        if status in ("live", "halftime"):
            raw_clock = st.get("displayClock")
            clock = str(raw_clock) if raw_clock else None
            raw_period = st.get("period")
            period = int(raw_period) if isinstance(raw_period, (int, float)) else None

        season = e.get("season", {}).get("year") or int(kickoff[:4])
        return Match(
            id=f"espn:{e['id']}",
            leagueCode=league,
            season=str(season),
            kickoffUtc=kickoff,
            status=status,
            home=_to_team(home),
            away=_to_team(away),
            score=score,
            clock=clock,
            period=period,
            refs=[ProviderRef(provider="espn", externalId=str(e["id"]))],
        )

    async def list_matches(self, league: str, date: Optional[str] = None) -> list[Match]:
        lg = self._league(league)
        path = f"/{lg}/scoreboard" + (f"?dates={date}" if date else "")
        data = await self._get(path)
        out = []
        for e in data.get("events", []):
            try:
                out.append(self._to_match(e, league))
            except Exception:
                continue
        return out

    async def list_standings(self, league: str) -> tuple[Optional[str], list[StandingGroup]]:
        """
        Bảng xếp hạng. Cúp châu Âu chia bảng nên children có thể gồm nhiều
        nhóm; giải quốc nội chỉ có một. Giữ nguyên thứ tự ESPN trả về,
        chỉ sắp lại theo rank để chắc chắn đúng thứ hạng.
        """
        lg = self._league(league)
        data = await self._get(f"/{lg}/standings", base=ESPN_V2_BASE)
        season = None
        groups: list[StandingGroup] = []

        for child in data.get("children") or []:
            st = child.get("standings") or {}
            if season is None and st.get("season"):
                season = str(st["season"])
            rows: list[StandingRow] = []
            for entry in st.get("entries") or []:
                team = entry.get("team") or {}
                vals: dict[str, int] = {}
                for stat in entry.get("stats") or []:
                    key = STANDING_KEYS.get(stat.get("name"))
                    if not key:
                        continue
                    raw = str(stat.get("displayValue", "")).replace("+", "").strip()
                    try:
                        vals[key] = int(float(raw))
                    except ValueError:
                        continue
                if "points" not in vals:
                    continue
                logos = team.get("logos") or []
                rows.append(StandingRow(
                    rank=vals.get("rank", len(rows) + 1),
                    teamId=str(team.get("id")),
                    teamName=team.get("displayName") or team.get("name") or "",
                    shortName=team.get("shortDisplayName"),
                    logoUrl=logos[0].get("href") if logos else None,
                    played=vals.get("played", 0),
                    wins=vals.get("wins", 0),
                    draws=vals.get("draws", 0),
                    losses=vals.get("losses", 0),
                    goalsFor=vals.get("goalsFor", 0),
                    goalsAgainst=vals.get("goalsAgainst", 0),
                    goalDiff=vals.get("goalDiff", 0),
                    points=vals.get("points", 0),
                ))
            if rows:
                rows.sort(key=lambda r: r.rank)
                groups.append(StandingGroup(
                    name=child.get("name") or child.get("abbreviation") or "", rows=rows,
                ))
        return season, groups

    async def list_news(self, league: str, limit: int = 20) -> list["NewsItem"]:
        from ..models import NewsItem
        lg = self._league(league)
        data = await self._get(f"/{lg}/news")
        out: list[NewsItem] = []
        for a in data.get("articles", [])[:limit]:
            web = ((a.get("links") or {}).get("web") or {}).get("href")
            if not web:
                continue
            image = None
            images = a.get("images") or []
            if images:
                image = images[0].get("url")
            out.append(NewsItem(
                id=str(a["id"]),
                leagueCode=league,
                headline=a.get("headline") or "",
                description=a.get("description"),
                imageUrl=image,
                publishedUtc=a.get("published") or a.get("lastModified") or "",
                webUrl=web,
            ))
        return out

    async def list_teams(self, league: str) -> list[Team]:
        lg = self._league(league)
        data = await self._get(f"/{lg}/teams")
        raw = (data.get("sports") or [{}])[0].get("leagues", [{}])[0].get("teams", [])
        out = []
        for entry in raw:
            t = entry["team"]
            out.append(Team(
                id=f"espn:{t['id']}",
                name=t["displayName"],
                shortName=t.get("abbreviation"),
                logoUrl=(t.get("logos") or [{}])[0].get("href"),
                refs=[ProviderRef(provider="espn", externalId=t["id"])],
            ))
        return out

    async def list_calendar(self, league: str) -> list[str]:
        """
        Các ngày có trận trong cả mùa, dạng YYYYMMDD.

        ESPN gói sẵn lịch này trong scoreboard nên chỉ tốn một lượt gọi.
        Mỗi mục là một chuỗi ISO, có thể lặp lại nên phải lọc trùng.
        """
        lg = self._league(league)
        data = await self._get(f"/{lg}/scoreboard")
        calendar = (data.get("leagues") or [{}])[0].get("calendar") or []
        seen: set[str] = set()
        for entry in calendar:
            if not isinstance(entry, str):
                continue
            code = entry[:10].replace("-", "")
            if len(code) == 8 and code.isdigit():
                seen.add(code)
        return sorted(seen)

    async def list_upcoming_matches(self, league: str, limit: int = 12) -> list[Match]:
        lg = self._league(league)
        today = await self._get(f"/{lg}/scoreboard")
        calendar = (today.get("leagues") or [{}])[0].get("calendar") or []

        now = datetime.now(timezone.utc)
        seen: set[str] = set()
        future_dates: list[str] = []
        for d in calendar:
            # Giải quốc nội trả lịch là danh sách chuỗi ngày. Cúp châu Âu
            # trả MỘT object mô tả các giai đoạn (vòng bảng, play-off...)
            # chứ không phải ngày thi đấu — bỏ qua ở đây, có nhánh riêng
            # bên dưới lo. Trước khi có dòng này, d[:10] trên dict ném
            # KeyError và cả màn hình "Sắp diễn ra" của giải đó trắng
            # trơn kèm lỗi JSON.
            if not isinstance(d, str):
                continue
            code = d[:10].replace("-", "")
            if code in seen:
                continue
            try:
                dt = datetime.strptime(code, "%Y%m%d").replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc
                )
            except ValueError:
                continue
            if dt >= now:
                seen.add(code)
                future_dates.append(code)
            if len(future_dates) >= 4:
                break

        if not future_dates:
            # Không rút được ngày nào — gần như luôn là giải cúp châu Âu.
            # May là chính lượt gọi scoreboard vừa rồi đã kèm sẵn các
            # trận của vòng kế tiếp, nên lấy luôn từ đó, không tốn thêm
            # lời gọi nào.
            return self._scheduled_from(today.get("events", []), league, limit)

        import asyncio
        pages = await asyncio.gather(
            *[self._get(f"/{lg}/scoreboard?dates={d}") for d in future_dates]
        )

        events = [e for page in pages for e in page.get("events", [])]
        return self._scheduled_from(events, league, limit)

    def _scheduled_from(self, events: list, league: str, limit: int) -> list[Match]:
        """Lọc ra các trận CHƯA đá từ danh sách sự kiện thô của ESPN."""
        matches: list[Match] = []
        for e in events:
            try:
                matches.append(self._to_match(e, league))
            except Exception:
                continue

        matches = [m for m in matches if m.status == "scheduled"]
        matches.sort(key=lambda m: m.kickoffUtc)
        return matches[:limit]

    async def get_match_detail(self, league: str, external_id: str) -> MatchDetail:
        lg = self._league(league)
        data = await self._get(f"/{lg}/summary?event={external_id}")
        header = data.get("header")
        if not header:
            raise ValueError(f"[espn] thiếu header cho trận {external_id}")
        match = self._to_match(header, league)

        box_teams = (data.get("boxscore") or {}).get("teams") or []
        stats = None
        if len(box_teams) == 2:
            by_id = {t["team"]["id"]: _to_team_stats(t.get("statistics", [])) for t in box_teams}
            home_ext = match.home.refs[0].externalId
            away_ext = match.away.refs[0].externalId
            stats = MatchStats(
                matchId=match.id,
                home=by_id.get(home_ext, TeamMatchStats()),
                away=by_id.get(away_ext, TeamMatchStats()),
            )

        events: list[MatchEvent] = []
        for ke in data.get("keyEvents", []):
            clock = parse_clock((ke.get("clock") or {}).get("displayValue"))
            if not clock:
                continue
            minute, extra = clock
            kind = map_event_type((ke.get("type") or {}).get("text"))
            if kind in ("other", "period_start", "period_end"):
                continue
            team_id = (ke.get("team") or {}).get("id")
            side = "home" if team_id == match.home.refs[0].externalId else "away"

            # ESPN đã đổi tên trường này: trước là athletesInvolved, nay là
            # participants với cầu thủ nằm lồng trong khóa athlete. Đọc cả
            # hai dạng để không phụ thuộc vào việc họ có đổi lại hay không —
            # trước khi sửa, mọi diễn biến đều không có tên cầu thủ.
            people = [
                (a.get("athlete") or a).get("displayName")
                for a in (ke.get("participants") or ke.get("athletesInvolved") or [])
            ]
            people = [n for n in people if n]

            events.append(MatchEvent(
                matchId=match.id,
                minute=minute,
                extraMinute=extra,
                period=period_of(minute),
                type=kind,
                side=side,
                playerName=people[0] if people else None,
                # Thay người: người thứ hai là người rời sân.
                secondPlayerName=people[1] if len(people) > 1 else None,
                description=ke.get("text"),
            ))

        # Phạt góc KHÔNG nằm trong keyEvents mà nằm trong commentary, dưới
        # dạng play.type.type == "corner-awarded", và ở đó mới có mốc phút
        # lẫn số hiệp. Trước đây phần tách theo hiệp bỏ trống ô phạt góc vì
        # chỉ nhìn vào keyEvents và boxscore (boxscore chỉ có tổng cả trận).
        #
        # Đã đối chiếu: đếm từ commentary ra đúng bằng wonCorners của
        # boxscore, nên nguồn này tin được.
        #
        # Lưu ý: commentary chỉ cho tên đội (displayName), không cho mã đội
        # như keyEvents, nên phải so theo tên.
        home_name = (match.home.name or "").strip().lower()
        away_name = (match.away.name or "").strip().lower()
        for item in data.get("commentary") or []:
            play = item.get("play") or {}
            if (play.get("type") or {}).get("type") != "corner-awarded":
                continue
            clock = parse_clock((play.get("clock") or item.get("time") or {}).get("displayValue"))
            if not clock:
                continue
            minute, extra = clock
            team_name = ((play.get("team") or {}).get("displayName") or "").strip().lower()
            if team_name == home_name:
                side = "home"
            elif team_name == away_name:
                side = "away"
            else:
                # Không khớp được đội thì bỏ qua hẳn: đoán bừa sẽ làm lệch
                # số liệu theo hiệp, tệ hơn là thiếu một quả phạt góc.
                continue
            events.append(MatchEvent(
                matchId=match.id,
                minute=minute,
                extraMinute=extra,
                period=period_of(minute),
                type="corner",
                side=side,
                description=play.get("text") or item.get("text"),
            ))

        # Trang trận đấu chính thức trên espn.com, KHÔNG phải link video trực
        # tiếp — phát lại video của ESPN trong app bên thứ ba vi phạm điều
        # khoản của họ, nên chỉ điều hướng sang web của ESPN. Không lấy trực
        # tiếp từ videos[] vì mảng đó có thể chứa clip không liên quan (ví
        # dụ tin HLV từ chức) thay vì highlight bàn thắng của đúng trận này;
        # trang trận đấu do ESPN tự chọn nội dung nên luôn đúng ngữ cảnh.
        # Chỉ có ý nghĩa khi trận đã đá xong, vì trận chưa diễn ra chưa có
        # highlight nào để xem.
        highlight_url = (
            f"https://www.espn.com/soccer/match/_/gameId/{external_id}"
            if match.status == "finished" else None
        )

        referee_name = None
        for official in (data.get("gameInfo") or {}).get("officials", []):
            if (official.get("position") or {}).get("name") == "Referee":
                referee_name = official.get("displayName") or official.get("fullName")
                break

        return MatchDetail(
            match=match, events=events, stats=stats, highlightUrl=highlight_url,
            refereeName=referee_name, lineups=_to_lineups(data.get("rosters") or []),
            odds=_to_odds(data.get("odds") or []),
        )

    async def list_team_matches(self, league: str, team_external_id: str, seasons: list[str]) -> list[Match]:
        import asyncio
        lg = self._league(league)

        async def fetch(season: Optional[str]) -> list[Match]:
            path = f"/{lg}/teams/{team_external_id}/schedule"
            if season:
                path += f"?season={season}"
            try:
                data = await self._get(path)
            except Exception:
                return []
            out = []
            for e in data.get("events", []):
                try:
                    out.append(self._to_match(e, league))
                except Exception:
                    continue
            return out

        pages = await asyncio.gather(*[fetch(s) for s in (seasons or [None])])
        seen: set[str] = set()
        result: list[Match] = []
        for page in pages:
            for m in page:
                if m.id not in seen:
                    seen.add(m.id)
                    result.append(m)
        return result


_provider: Optional[EspnProvider] = None


def get_provider() -> EspnProvider:
    """
    Giữ lại cho mã cũ. KHÔNG dùng trong mã mới — hãy gọi
    `from .providers import get_provider`, bản đó tôn trọng biến môi
    trường DATA_PROVIDER nên đổi nguồn không phải sửa mã.
    """
    from . import get_provider as _registry
    return _registry()
