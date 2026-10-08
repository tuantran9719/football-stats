"""
Tầng nghiệp vụ. Cổng lại từ apps/api/src/service.ts.

Route chỉ lo nhận tham số và trả JSON, không chứa logic. Đây là nơi
duy nhất gọi tới provider và stats.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import ai_analysis as ai_analysis_module
from .chat import answer as chat_answer
from .chat import engine as chat_engine
from .chat import store as chat_store
from .predictor import describe as predictor_describe
from .predictor import results_store as predictor_results
from .predictor import store as predictor_store
from .predictor import trainer as predictor_trainer
from .predictor.model import predict as predictor_predict
from . import rating as rating_module
from . import referee_store
from .cache import TTL_LIVE, TTL_LONG, TTL_MEDIUM, TTL_SHORT, cached, cached_dynamic
from .models import (
    ChatResponse, ProviderRef, StandingsFormResponse, Team,
    AggregatedStats, AiPrediction, BettingInsights, CalendarResponse, HeadToHeadMatchesResponse,
    HeadToHeadResponse,
    LeagueDto, LiveMatch, LiveResponse, Match, MatchDetailResponse, MatchListResponse,
    MatchPoint, MatchRow, MatchSplitStats, RefereeInfo, Score, StandingsResponse,
    MatchInsightsResponse, StatCardDto, TeamFormResponse, TeamListResponse, TeamTendency,
    UpcomingMatchesResponse,
)
from .providers import get_provider, provider_name, team_ref
from .providers import (
    cup_leagues_map, league_display_name, league_logo_url, leagues_map,
)
from .stats import EXTRACTORS, aggregate, compute_match_split, last_n_matches, side_of

provider = get_provider()

async def _none():
    """Chỗ giữ chỗ để asyncio.gather nhận đều awaitable khi một nhánh
    không cần chạy (trận chưa xác định phong độ hai đội)."""
    return None


# Chờ AI tối đa chừng này rồi trả trang về, phần AI để trống.
AI_BUDGET_SECONDS = 2.5

# Giữ tham chiếu tới các lượt gọi AI còn chạy nền. Không giữ thì Python
# có thể thu gom giữa chừng và lượt gọi biến mất, cache không bao giờ
# được nạp và lần mở sau vẫn trống.
_bg_ai: set[asyncio.Task] = set()


async def _ai_within_budget(analysis_task, prediction_task):
    """
    Không để phần AI chặn cả trang.

    Trước đây mở một trận chưa đá mất 7-9 giây vì phải chờ nhà cung cấp AI
    trả lời xong mới dựng trang, trong khi mọi số liệu thống kê đã sẵn
    sàng từ lâu. Nay chờ tối đa AI_BUDGET_SECONDS rồi trả trang.

    Điểm mấu chốt là asyncio.shield: hết giờ thì thôi không chờ nữa nhưng
    KHÔNG hủy lượt gọi — nó chạy tiếp ở nền và ghi vào cache của
    ai_analysis, nên lần mở sau (hoặc kéo xuống làm mới) đã có sẵn. Hủy
    đi thì vừa mất câu trả lời vừa tốn một lượt trong hạn mức miễn phí.
    """
    task = asyncio.ensure_future(asyncio.gather(analysis_task, prediction_task))
    _bg_ai.add(task)
    task.add_done_callback(_bg_ai.discard)
    try:
        return await asyncio.wait_for(asyncio.shield(task), AI_BUDGET_SECONDS)
    except (TimeoutError, asyncio.TimeoutError):
        return None, None


LABELS = {
    "goalsFor": "Bàn thắng",
    "goalsAgainst": "Bàn thua",
    "corners": "Phạt góc",
    "yellowCards": "Thẻ vàng",
    "redCards": "Thẻ đỏ",
}


def list_leagues() -> list[LeagueDto]:
    return [
        LeagueDto(code=k, name=v, logoUrl=league_logo_url(k)) for k, v in leagues_map().items()
    ]


LIVE_STATUSES = ("live", "halftime")


def _has_live(matches: list[Match]) -> bool:
    return any(m.status in LIVE_STATUSES for m in matches)


def _ttl_for_matches(matches: list[Match], date: Optional[str] = None) -> int:
    """
    Giải đang có trận đá thì tỉ số đổi từng phút, giữ 15 giây. Giải không
    có trận nào thì 60 giây — đây là điểm mấu chốt để tính năng trực tiếp
    không kéo theo việc gọi ESPN dày hơn ở các giải đang không có gì.

    Nhưng NGÀY ĐÃ QUA thì kết quả không bao giờ đổi nữa, giữ 6 tiếng.
    Không có ngoại lệ này thì mỗi phút cache lại hết hạn và lần mở app
    tiếp theo phải tải lại toàn bộ — kể cả những ngày trống trơn.
    """
    if _has_live(matches):
        return TTL_LIVE
    if date:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        if date < today:
            return TTL_LONG
        if date > today:
            return TTL_MEDIUM
    return TTL_SHORT


# ---------------------------------------------------------------- múi giờ
#
# ESPN làm việc hoàn toàn theo ngày UTC: tham số dates=YYYYMMDD lọc theo
# ngày UTC, và trường calendar cũng là các ngày UTC. Nhưng người dùng đọc
# giờ bóng lăn theo múi giờ máy mình.
#
# Ở Việt Nam (UTC+7) chênh lệch này đủ để lệch hẳn một ngày: trận
# Brasileirão đá 21:30 UTC ngày 03/10 hiện trên app là 04:30 sáng 04/10.
# Thanh chọn ngày lấy từ lịch UTC nên hiện 03/10, còn thẻ trận ghi 04/10
# — hai thứ không bao giờ khớp, và bấm vào 04/10 thì không ra trận nào.
#
# Cách sửa: mọi chỗ liên quan tới "ngày" đều nhận thêm tham số tz (số
# phút cộng vào UTC để ra giờ địa phương, ví dụ Việt Nam là 420) và quy
# về NGÀY ĐỊA PHƯƠNG của người dùng.


def _local_date(kickoff_utc: str, tz_minutes: int) -> str:
    """Giờ bóng lăn (ISO, UTC) -> ngày địa phương dạng YYYYMMDD."""
    dt = datetime.fromisoformat(kickoff_utc.replace("Z", "+00:00"))
    return (dt + timedelta(minutes=tz_minutes)).strftime("%Y%m%d")


def _utc_days_for_local_day(date_code: str, tz_minutes: int) -> list[str]:
    """
    Những ngày UTC cần tải để phủ hết một ngày địa phương.

    Đúng HAI ngày, và chọn ngày nào thì tuỳ dấu của múi giờ:

      - Múi giờ dương (châu Á): nửa đêm địa phương rơi vào chiều hôm
        trước theo giờ UTC, nên ngày địa phương D nằm trên UTC D-1 và D.
      - Múi giờ âm (châu Mỹ): ngược lại, nằm trên UTC D và D+1.
      - Đúng UTC: chỉ cần D, nhưng vẫn lấy kèm một ngày cho đồng nhất.

    Trước đây lấy cả ba ngày cho "chắc ăn". Nghe thì vô hại vì đều dùng
    chung cache, nhưng ở chế độ tất cả các giải nó thành 36 lượt gọi ESPN
    thay vì 24 — đo được 11 giây cho lần mở app đầu tiên.
    """
    day = datetime.strptime(date_code, "%Y%m%d")
    offsets = (-1, 0) if tz_minutes >= 0 else (0, 1)
    return [(day + timedelta(days=o)).strftime("%Y%m%d") for o in offsets]


def _in_local_day(kickoff_utc: str, date_code: str, tz_minutes: int) -> bool:
    return _local_date(kickoff_utc, tz_minutes) == date_code


async def _matches_on_local_day(
    league: str, date_code: str, tz_minutes: int,
) -> list[Match]:
    """Trận của đúng một ngày theo giờ người dùng, không phải theo giờ UTC."""
    one = (lambda code: _gather_all_leagues(lambda lg: _matches_one(lg, code))) \
        if league == "ALL" else (lambda code: _matches_one(league, code))

    days = _utc_days_for_local_day(date_code, tz_minutes)
    results = await asyncio.gather(*[one(d) for d in days], return_exceptions=True)

    seen: set[str] = set()
    out: list[Match] = []
    for r in results:
        if isinstance(r, Exception):
            continue
        for m in r:
            if m.id in seen:
                continue
            if _in_local_day(m.kickoffUtc, date_code, tz_minutes):
                seen.add(m.id)
                out.append(m)
    out.sort(key=lambda m: m.kickoffUtc)
    return out


async def _matches_one(league: str, date: Optional[str]) -> list[Match]:
    return await cached_dynamic(
        f"matches:{league}:{date or 'now'}",
        lambda: provider.list_matches(league, date),
        lambda ms: _ttl_for_matches(ms, date),
    )


async def _upcoming_one(league: str) -> list[Match]:
    return await cached(
        f"upcoming:{league}", TTL_MEDIUM,
        lambda: provider.list_upcoming_matches(league),
    )


# Số lượt gọi nhà cung cấp chạy cùng lúc khi gộp nhiều giải.
#
# Trước đây app có 12 giải nên bắn hết một lúc vẫn ổn. Nay gần 50 giải:
# bắn cùng lúc là cách nhanh nhất để ăn 429 rồi bị phạt nguội cả phút,
# mà người dùng chỉ nhìn thấy "không tải được". Tám lượt một lúc vẫn
# nhanh (cache ấm thì gần như tức thì) mà không chọc giận nhà cung cấp.
LEAGUE_FANOUT = 8

# Giới hạn số trận trả về khi gộp TẤT CẢ các giải.
#
# 50 giải × 12 trận sắp đá = 600 dòng, vừa nặng cho điện thoại vẽ vừa
# vô dụng: không ai cuộn tới trận thứ 300. Cắt sau khi đã sắp theo giờ
# nên phần giữ lại luôn là những trận gần nhất.
ALL_LEAGUES_LIMIT = 150

# Những giải được nạp trước lúc khởi động và theo chu kỳ.
#
# KHÔNG nạp cả 49 giải: đó là gần 200 lượt gọi mỗi chu kỳ, đủ để nhà
# cung cấp chặn tần suất rồi app trắng trơn — đã xảy ra thật ngay khi
# vừa thêm giải. Chỉ nạp trước những giải người ta mở ngay khi bật app;
# các giải còn lại nạp khi có người thực sự chọn tới, chậm hơn đúng một
# lần rồi vào cache.
WARM_LEAGUES = ("EPL", "LALIGA", "SERIEA", "BUNDES", "LIGUE1", "UCL")


def _warm_codes() -> list[str]:
    """Giao của danh sách ưu tiên với những giải nguồn hiện có."""
    live = leagues_map()
    picked = [c for c in WARM_LEAGUES if c in live]
    return picked or list(live)[:6]


async def _bounded(jobs: list, limit: int = LEAGUE_FANOUT) -> list:
    """Chạy song song nhưng không quá `limit` lượt cùng lúc."""
    sem = asyncio.Semaphore(limit)

    async def guarded(job):
        async with sem:
            return await job

    return await asyncio.gather(*[guarded(j) for j in jobs], return_exceptions=True)


async def _gather_all_leagues(one, limit: Optional[int] = ALL_LEAGUES_LIMIT) -> list[Match]:
    """
    Gọi cho mọi giải, gộp lại và sắp theo giờ bóng lăn. Một giải lỗi
    (nhà cung cấp chập chờn) không được làm hỏng cả trang, nên bỏ qua
    lỗi của riêng giải đó thay vì để lỗi lan ra toàn bộ.
    """
    results = await _bounded([one(code) for code in leagues_map()])
    matches: list[Match] = []
    for r in results:
        if isinstance(r, BaseException):
            continue
        matches.extend(r)
    matches.sort(key=lambda m: m.kickoffUtc)
    return matches[:limit] if limit else matches


async def list_matches(
    league: str, date: Optional[str] = None, tz: Optional[int] = None,
) -> MatchListResponse:
    # Có ngày VÀ có múi giờ thì lọc theo ngày địa phương. Không có ngày
    # thì giữ nguyên hành vi cũ: ESPN trả về vòng đấu gần nhất, đó đúng
    # là thứ cần hiện khi mới mở app.
    if date and tz is not None:
        matches = await _matches_on_local_day(league, date, tz)
    elif league == "ALL":
        matches = await _gather_all_leagues(lambda code: _matches_one(code, date))
    else:
        matches = await _matches_one(league, date)
    return MatchListResponse(league=league, matches=matches)


async def list_upcoming_matches(league: str) -> UpcomingMatchesResponse:
    if league == "ALL":
        matches = await _gather_all_leagues(_upcoming_one)
    else:
        matches = await _upcoming_one(league)
    return UpcomingMatchesResponse(league=league, matches=matches)


async def get_live(league: str) -> LiveResponse:
    """
    Bản cập nhật gọn cho các trận trong ngày. App gọi lại đều đặn khi có
    trận đang đá nên chỉ trả về đúng những trường biến động; tên đội và
    logo app đã có sẵn từ lần tải danh sách đầu tiên.

    Dùng chung đúng cache với danh sách trận nên việc hỏi liên tục không
    sinh thêm một lượt gọi ESPN nào ngoài số đã tính ở _ttl_for_matches.
    """
    if league == "ALL":
        matches = await _gather_all_leagues(lambda code: _matches_one(code, None))
    else:
        matches = await _matches_one(league, None)

    return LiveResponse(
        league=league,
        matches=[
            LiveMatch(
                id=m.id, status=m.status, score=m.score,
                clock=m.clock, period=m.period,
            )
            for m in matches
        ],
        pollAfterSeconds=20 if _has_live(matches) else 60,
    )


async def _news_one(league: str) -> list["NewsItem"]:
    return await cached(f"news:{league}", TTL_MEDIUM, lambda: provider.list_news(league))


async def list_news(league: str) -> "NewsListResponse":
    from .models import NewsListResponse
    if league == "ALL":
        results = await _bounded([_news_one(code) for code in leagues_map()])
        # ESPN gắn cùng một bài (ví dụ tin chuyển nhượng chung) vào nhiều
        # giải cùng lúc — bỏ trùng theo id khi gộp, giữ bản xuất hiện trước.
        seen: set[str] = set()
        articles = []
        for r in results:
            if isinstance(r, Exception):
                continue
            for a in r:
                if a.id in seen:
                    continue
                seen.add(a.id)
                articles.append(a)
        articles.sort(key=lambda a: a.publishedUtc, reverse=True)
    else:
        articles = await _news_one(league)
    return NewsListResponse(league=league, articles=articles)


async def list_teams(league: str) -> TeamListResponse:
    teams = await cached(f"teams:{league}", TTL_LONG, lambda: provider.list_teams(league))
    teams = sorted(teams, key=lambda t: t.name)
    return TeamListResponse(league=league, teams=teams)


async def get_match_detail(league: str, external_id: str, lang: str = "vi") -> MatchDetailResponse:
    async def load_detail():
        return await provider.get_match_detail(league, external_id)

    # Trận đang đá thì diễn biến và tỉ số đổi liên tục, giữ 15 giây; trận
    # đã xong không đổi nữa nên giữ lâu. Trước đây mọi trận đều 10 phút,
    # nghĩa là mở một trận đang đá ra sẽ thấy diễn biến đứng im.
    detail = await cached_dynamic(
        f"detail:{league}:{external_id}", load_detail,
        lambda d: TTL_LIVE if d.match.status in LIVE_STATUSES
        else (TTL_LONG if d.match.status == "finished" else TTL_MEDIUM),
    )
    split = compute_match_split(detail.match, detail.events, detail.stats)

    referee = None
    if detail.refereeName:
        if detail.match.status == "finished":
            await referee_store.record_match(
                detail.refereeName, detail.match.id,
                yellow=split.cards.full.home.yellow + split.cards.full.away.yellow,
                red=split.cards.full.home.red + split.cards.full.away.red,
            )
        stats = await referee_store.get_stats(detail.refereeName)
        referee = RefereeInfo(
            name=detail.refereeName,
            matchesTracked=stats["matchesTracked"] if stats else 0,
            avgYellowCards=stats["avgYellowCards"] if stats else None,
            avgRedCards=stats["avgRedCards"] if stats else None,
        )

    # Chấm điểm số liệu từng cầu thủ. Làm ở đây chứ không ở lớp nguồn:
    # công thức là của app, không phải của nhà cung cấp, nên đổi nguồn
    # vẫn giữ nguyên cách tính.
    rating_module.apply_to(
        detail.lineups,
        detail.match.score.home if detail.match.score else None,
        detail.match.score.away if detail.match.score else None,
    )

    return MatchDetailResponse(
        match=detail.match, split=split, eventCount=len(detail.events),
        highlightUrl=detail.highlightUrl, referee=referee,
        # Sắp theo phút để giao diện dựng thẳng thành dòng thời gian, không
        # phải tự sắp lại; ESPN trả theo thứ tự ghi nhận chứ không đảm bảo.
        events=sorted(detail.events, key=lambda e: (e.minute, e.extraMinute or 0)),
        teamStats=detail.stats,
        lineups=detail.lineups,
    )


async def get_match_insights(
    league: str, external_id: str, lang: str = "vi",
) -> MatchInsightsResponse:
    """
    Phần nặng của màn hình chi tiết trận, tách ra một lời gọi riêng.

    Lý do tách: dựng được bảng soi kèo phải tải phong độ 10 trận gần nhất
    của CẢ HAI đội, mỗi trận là một lượt gọi ESPN — đo được 3,5 giây cho
    một đội khi cache nguội. Gộp chung vào /api/matches/{id} thì bảng tỉ
    số, diễn biến, đội hình đều đã sẵn sàng mà vẫn phải nằm chờ.

    Tách ra thì trang hiện gần như tức thì, riêng thẻ soi kèo quay bánh
    xe thêm vài giây. Trận đã đá xong trả về rỗng ngay: không có gì để
    dự đoán nữa.
    """
    async def load_detail():
        return await provider.get_match_detail(league, external_id)

    detail = await cached_dynamic(
        f"detail:{league}:{external_id}", load_detail,
        lambda d: TTL_LIVE if d.match.status in LIVE_STATUSES
        else (TTL_LONG if d.match.status == "finished" else TTL_MEDIUM),
    )
    if detail.match.status != "scheduled":
        return MatchInsightsResponse()

    split = compute_match_split(detail.match, detail.events, detail.stats)
    predict_window = 10
    home_form, away_form = await asyncio.gather(
        get_team_form(league, detail.match.home.refs[0].externalId, predict_window),
        get_team_form(league, detail.match.away.refs[0].externalId, predict_window),
    )

    insights = _build_insights(home_form, away_form, predict_window)

    # Dự đoán bằng mô hình Poisson tự huấn luyện, KHÔNG gọi AI.
    #
    # Giữ nguyên hai trường aiAnalysis/aiPrediction để giao diện không
    # phải đổi gì; chỉ có nguồn sinh ra chúng là khác. Đổi lại: không
    # tốn hạn mức, không có ngày "hết lượt" làm mục nhận định biến mất,
    # và câu chữ luôn khớp với con số vì cùng một nguồn.
    analysis_text, prediction = await _model_prediction(
        league, detail.match, insights, lang,
    )

    return MatchInsightsResponse(
        insights=insights,
        odds=detail.odds,
        aiAnalysis=analysis_text,
        aiPrediction=prediction,
    )


async def _model_prediction(
    league: str, match: Match, insights: Optional[BettingInsights], lang: str,
) -> tuple[Optional[str], Optional[AiPrediction]]:
    """
    Dựng nhận định và dự đoán từ mô hình đã học.

    Chưa học xong giải này, hoặc một trong hai đội mô hình chưa từng
    thấy, thì trả về rỗng — giao diện tự ẩn hai khối đó, giống hệt cách
    nó xử lý khi AI không trả lời được.

    Phạt góc và thẻ lấy từ trung bình phong độ (bảng soi kèo ngay bên
    trên) chứ không từ mô hình Poisson bàn thắng: hai chỉ số đó phụ
    thuộc lối chơi và trọng tài nhiều hơn là tương quan mạnh yếu, nên
    trung bình gần đây là ước lượng trung thực hơn.
    """
    ratings = await predictor_store.get_ratings(league)
    if ratings is None:
        return None, None
    if not (ratings.known(match.home.id) and ratings.known(match.away.id)):
        return None, None

    p = predictor_predict(ratings, match.home.id, match.away.id)
    home_goals, away_goals = p.top_score

    corners = round(insights.expectedCorners) if insights else 0
    cards = round(insights.expectedCards) if insights else 0

    text = predictor_describe.analysis(
        p, match.home.shortName or match.home.name,
        match.away.shortName or match.away.name, ratings.matches, lang,
    )
    pred = AiPrediction(
        homeScore=home_goals, awayScore=away_goals,
        corners=corners, yellowCards=cards,
        note=predictor_describe.note(p, ratings.matches, lang),
    )
    return text, pred


# Số giải được học lại trong MỖI chu kỳ huấn luyện.
#
# Học một giải phải tải lịch 4 mùa của từng đội — khoảng 80 lượt gọi.
# Nhân với 49 giải là gần 4.000 lượt mỗi 6 tiếng, chắc chắn bị chặn tần
# suất. Nên mỗi chu kỳ chỉ học một nhóm rồi xoay vòng sang nhóm kế.
#
# Hệ quả: mỗi giải được làm mới khoảng (39/4) × 6 tiếng ≈ hai ngày rưỡi.
# Chấp nhận được, vì trọng số của mô hình giảm theo thời gian rất chậm
# (xi từ 0,0035 đến 0,015 mỗi ngày) nên hệ số không kịp cũ đi trong
# ngần ấy thời gian.
TRAIN_BATCH = 4

# Nghỉ giữa hai giải khi huấn luyện. Học một giải là một cụm khoảng 80
# lượt gọi; nối liền nhau không nghỉ thì tổng lưu lượng trong một phút
# đủ để nhà cung cấp chặn, kéo theo người dùng đang mở app cũng hỏng
# theo. Vài giây nghỉ không làm ai sốt ruột vì đây là việc chạy nền.
TRAIN_PAUSE_SECONDS = 5

_train_cursor = 0


async def train_predictor() -> list[dict]:
    """
    Học lại mô hình cho một nhóm giải, xoay vòng qua các chu kỳ.

    Mỗi lần chạy nạp thêm các trận vừa đá xong và tự dò lại tham số, nên
    mô hình tự khá lên theo thời gian mà không cần ai can thiệp.
    """
    global _train_cursor
    codes = list(leagues_map())
    if not codes:
        return []

    batch = [codes[(_train_cursor + i) % len(codes)] for i in range(min(TRAIN_BATCH, len(codes)))]
    _train_cursor = (_train_cursor + len(batch)) % len(codes)

    out: list[dict] = []
    for i, code in enumerate(batch):
        if i:
            await asyncio.sleep(TRAIN_PAUSE_SECONDS)
        try:
            matches = await gather_results(code, seasons=4)
            res = await predictor_trainer.train_league(code, matches)
            if res:
                out.append(res)
        except Exception as exc:
            print(f"[predictor] {code}: {exc}")
    return out


def _tendency(team_id: str, team_name: str, rows: list[MatchRow]) -> TeamTendency:
    """
    Quy các trận gần nhất của một đội thành vài con số đọc được ngay.

    Chỉ dùng trận đã đá xong và có đủ số liệu. Trận thiếu dữ liệu bị loại
    khỏi mẫu chứ không tính là 0 — cùng quy ước với phần trung bình theo
    hiệp, vì coi "không biết" thành 0 sẽ kéo tụt mọi chỉ số.
    """
    played = [r for r in rows if r.status == "finished" and r.totalGoals is not None]
    n = len(played)
    if n == 0:
        return TeamTendency(
            teamId=team_id, teamName=team_name, matches=0,
            avgGoals=0.0, avgCorners=0.0, avgCards=0.0,
            over25GoalsPct=0.0, over95CornersPct=0.0, over35CardsPct=0.0,
            bttsPct=0.0, firstHalfGoalPct=None,
        )

    def mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    def pct(hits: int, total: int) -> float:
        return round(hits * 100 / total, 1) if total else 0.0

    goals = [float(r.totalGoals or 0) for r in played]
    corner_rows = [r for r in played if r.totalCorners is not None]
    corners = [float(r.totalCorners or 0) for r in corner_rows]
    cards = [float((r.totalYellowCards or 0) + (r.totalRedCards or 0)) for r in played]

    btts = sum(
        1 for r in played
        if r.score is not None and r.score.home > 0 and r.score.away > 0
    )

    # Tỉ lệ bàn thắng ở hiệp một tính trên TỔNG bàn, không phải trung bình
    # của từng trận: một trận 0-0 không có bàn nào thì không nói lên điều
    # gì về việc bàn thắng hay đến sớm hay muộn, để nó tham gia phép chia
    # sẽ làm loãng kết quả.
    ht_rows = [r for r in played if r.htScore is not None]
    ht_goals = sum(r.htScore.home + r.htScore.away for r in ht_rows)
    ht_total = sum(int(r.totalGoals or 0) for r in ht_rows)

    return TeamTendency(
        teamId=team_id, teamName=team_name, matches=n,
        avgGoals=mean(goals),
        avgCorners=mean(corners),
        avgCards=mean(cards),
        over25GoalsPct=pct(sum(1 for g in goals if g > 2.5), n),
        over95CornersPct=pct(sum(1 for c in corners if c > 9.5), len(corners)),
        over35CardsPct=pct(sum(1 for c in cards if c > 3.5), n),
        bttsPct=pct(btts, n),
        firstHalfGoalPct=(round(ht_goals * 100 / ht_total, 1) if ht_total > 0 else None),
    )


def _build_insights(
    home_form: TeamFormResponse, away_form: TeamFormResponse, window: int,
) -> Optional[BettingInsights]:
    home = _tendency(home_form.teamId, home_form.teamName, home_form.rows)
    away = _tendency(away_form.teamId, away_form.teamName, away_form.rows)
    if home.matches == 0 and away.matches == 0:
        return None

    def blend(a: float, b: float) -> float:
        """Trung bình cộng hai đội, bỏ qua đội không có dữ liệu."""
        vals = [v for v, m in ((a, home.matches), (b, away.matches)) if m > 0]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    fh = [v for v in (home.firstHalfGoalPct, away.firstHalfGoalPct) if v is not None]

    return BettingInsights(
        window=window,
        home=home, away=away,
        expectedGoals=blend(home.avgGoals, away.avgGoals),
        expectedCorners=blend(home.avgCorners, away.avgCorners),
        expectedCards=blend(home.avgCards, away.avgCards),
        firstHalfGoalPct=(round(sum(fh) / len(fh), 1) if fh else None),
    )


# Thanh chọn ngày chỉ hiện 7 ngày CÓ TRẬN mỗi phía, nên không việc gì
# phải quy đổi cả mùa.
#
# Giới hạn theo SỐ NGÀY THI ĐẤU chứ không theo khoảng lịch: giải đá dày
# hay thưa gì thì số lượt gọi cũng như nhau. Lấy 9 mỗi phía, dư 2 so với
# những gì hiển thị để phòng trường hợp quy đổi múi giờ gộp hai ngày UTC
# vào chung một ngày địa phương.
CALENDAR_DAYS_EACH_SIDE = 9


# Khoảng ngày tối đa chịu lấy theo kiểu "quét từng ngày" khi bổ sung.
# Gián đoạn dài hơn thế thì quét ngày tốn nhiều lượt gọi hơn là tải lại
# lịch từng đội, nên lùi về cách cũ cho gọn.
INCREMENTAL_MAX_DAYS = 30


def _record(m: Match) -> Optional[dict]:
    """Rút một trận về đúng những trường phần huấn luyện cần."""
    if m.status != "finished" or m.score is None:
        return None
    return {
        "id": m.id,
        "h": m.home.id, "a": m.away.id,
        "hn": m.home.name, "an": m.away.name,
        "hg": int(m.score.home), "ag": int(m.score.away),
        "d": m.kickoffUtc[:10].replace("-", ""),
        "k": m.kickoffUtc,
    }


def _to_match(r: dict, league: str) -> Match:
    """Dựng lại đối tượng trận từ bản ghi đã lưu, đủ cho phần huấn luyện."""
    def team(tid: str, name: str) -> Team:
        ext = tid.split(":", 1)[1] if ":" in tid else tid
        return Team(id=tid, name=name,
                    refs=[ProviderRef(provider=get_provider().prefix, externalId=ext)])

    return Match(
        id=r["id"], leagueCode=league, season=r["d"][:4],
        kickoffUtc=r["k"], status="finished",
        home=team(r["h"], r.get("hn") or r["h"]),
        away=team(r["a"], r.get("an") or r["a"]),
        score=Score(home=r["hg"], away=r["ag"]),
        refs=[ProviderRef(provider=get_provider().prefix,
                          externalId=r["id"].split(":", 1)[-1])],
    )


async def _bootstrap_results(league: str, seasons: int) -> list[dict]:
    """
    Lần đầu cho một giải: tải lịch 4 mùa của từng đội.

    Tốn khoảng 80 lượt gọi, nhưng CHỈ MỘT LẦN cho mỗi giải trong suốt
    vòng đời máy chủ. Từ lần sau chỉ bổ sung phần mới.
    """
    teams = await cached(f"teams:{league}", TTL_LONG, lambda: provider.list_teams(league))
    if not teams:
        return []

    year = datetime.now(timezone.utc).year
    years = [str(year - i) for i in range(seasons)]

    async def one(ext: str) -> list[Match]:
        return await cached(
            f"schedule_train:{league}:{ext}", TTL_LONG,
            lambda: provider.list_team_matches(league, ext, years),
        )

    exts = [t.refs[0].externalId for t in teams if t.refs]
    pages = await _bounded([one(e) for e in exts])

    out: list[dict] = []
    for page in pages:
        if isinstance(page, BaseException):
            continue
        for m in page:
            rec = _record(m)
            if rec:
                out.append(rec)
    return out


async def _recent_results(league: str, since: str) -> list[dict]:
    """
    Bổ sung: quét từng ngày thi đấu kể từ `since`.

    Một lượt gọi trả về MỌI trận của giải trong ngày đó, nên vài ngày
    chỉ tốn vài lượt — thay vì hai chục lượt khi đi theo lịch từng đội.
    """
    today = datetime.now(timezone.utc).date()
    start = datetime.strptime(since, "%Y%m%d").date()
    days = (today - start).days
    if days < 0:
        return []

    dates = [(start + timedelta(days=i)).strftime("%Y%m%d") for i in range(days + 1)]
    pages = await _bounded([_matches_one(league, d) for d in dates])

    out: list[dict] = []
    for page in pages:
        if isinstance(page, BaseException):
            continue
        for m in page:
            rec = _record(m)
            if rec:
                out.append(rec)
    return out


async def gather_results(league: str, seasons: int = 4) -> list[Match]:
    """
    Mọi trận đã đá của một giải, dùng để huấn luyện mô hình.

    Kết quả giữ VĨNH VIỄN trên đĩa (predictor/results_store.py). Trận
    đã đá xong thì tỉ số không bao giờ đổi, nên tải lại chúng mỗi 6
    tiếng là lãng phí thuần tuý — và chính là thứ khiến nhà cung cấp
    chặn tần suất.

    Lần đầu cho mỗi giải vẫn tốn một lượt tải đầy đủ. Từ đó về sau chỉ
    quét những ngày đã trôi qua kể từ lần cập nhật trước, thường là vài
    ngày, tức vài lượt gọi.
    """
    stored = await predictor_results.load(league)
    today = datetime.now(timezone.utc).date()

    # Mốc quét là ngày đã kiểm TỚI, không phải ngày trận mới nhất — nếu
    # không, giải đang nghỉ giữa mùa sẽ bị quét lại những ngày trống đó
    # ở mọi lượt huấn luyện.
    #
    # Lùi lại một ngày phòng trận kết thúc muộn sau lần quét trước.
    checked = await predictor_results.checked_through(league)
    since = checked or await predictor_results.last_date(league)
    if since:
        start = datetime.strptime(since, "%Y%m%d").date() - timedelta(days=1)
        since = start.strftime("%Y%m%d")

    if not stored or since is None:
        fresh = await _bootstrap_results(league, seasons)
    elif (today - datetime.strptime(since, "%Y%m%d").date()).days > INCREMENTAL_MAX_DAYS:
        fresh = await _bootstrap_results(league, seasons)
    else:
        fresh = await _recent_results(league, since)

    if fresh:
        await predictor_results.merge(league, fresh)
        stored = await predictor_results.load(league)
    await predictor_results.set_checked(league, today.strftime("%Y%m%d"))

    out: list[Match] = []
    for r in stored.values():
        try:
            out.append(_to_match(r, league))
        except Exception:
            continue
    out.sort(key=lambda m: m.kickoffUtc)
    return out


async def warm_calendar_cache() -> int:
    """
    Nạp trước scoreboard của các ngày thi đấu quanh hôm nay.

    Phần nặng của /api/calendar là tải scoreboard từng ngày để biết giờ
    bóng lăn thật; với chế độ "tất cả các giải" là 12 giải nhân mười mấy
    ngày, đo được 17 giây khi cache nguội. Chạy sẵn lúc khởi động thì
    người dùng đầu tiên không phải chờ.

    Múi giờ không ảnh hưởng tới việc tải — nó chỉ tham gia lúc quy đổi ra
    ngày địa phương — nên nạp một lần là mọi múi giờ đều dùng được.

    Trả về số giải đã nạp xong, để log.
    """
    results = await _bounded([_local_calendar_one(code, 0) for code in _warm_codes()])
    return sum(1 for r in results if not isinstance(r, Exception))


async def warm_today_window() -> int:
    """
    Nạp trước cửa sổ hôm qua / hôm nay / ngày mai cho các giải ưu tiên.

    Đây đúng là thứ trang chủ hỏi tới ngay khi mở, và nó KHÔNG nằm trong
    lịch thi đấu khi hôm nay không có trận — mà đúng lúc đó lần mở app
    đầu tiên lại chậm nhất, vì phải gọi hết 12 giải chỉ để nhận về danh
    sách rỗng.

    Chỉ nạp WARM_LEAGUES chứ không nạp hết: xem ghi chú ở đó.

    Gọi lặp lại theo chu kỳ ngắn để cache không bao giờ nguội hẳn: dữ
    liệu hôm nay chỉ giữ được 60 giây, nếu để nó rơi ra ngoài thời gian
    ân hạn thì người mở app tiếp theo phải chờ trọn vẹn.
    """
    now = datetime.now(timezone.utc)
    days = [(now + timedelta(days=d)).strftime("%Y%m%d") for d in (-1, 0, 1)]
    codes = _warm_codes()
    jobs = [_matches_one(code, day) for code in codes for day in days]
    jobs += [_upcoming_one(code) for code in codes]
    results = await _bounded(jobs)
    return sum(1 for r in results if not isinstance(r, Exception))


async def get_calendar(league: str, tz: Optional[int] = None) -> CalendarResponse:
    """
    Những ngày có trận, tính theo NGÀY ĐỊA PHƯƠNG của người dùng.

    Lịch mà ESPN công bố là ngày UTC, dùng thẳng thì thanh chọn ngày lệch
    hẳn một ngày so với giờ ghi trên thẻ trận (xem ghi chú ở phần múi giờ
    bên trên). Vì vậy ở đây lấy lịch UTC làm danh sách ứng viên, tải
    scoreboard của từng ngày đó rồi suy ra ngày địa phương thật từ giờ
    bóng lăn của từng trận.

    Chi phí: chỉ tải các ngày nằm trong cửa sổ hiển thị, và dùng chung
    đúng cache với /api/matches nên phần lớn lượt gọi là dùng lại.
    """
    if tz is None:
        # Không biết múi giờ thì trả thẳng lịch UTC như trước. Chỉ xảy ra
        # khi gọi API bằng tay, app luôn gửi kèm tz.
        if league == "ALL":
            results = await _bounded([_calendar_raw(code) for code in leagues_map()])
            dates: set[str] = set()
            for r in results:
                if not isinstance(r, Exception):
                    dates.update(r)
            return CalendarResponse(league=league, dates=sorted(dates))
        return CalendarResponse(league=league, dates=await _calendar_raw(league))

    codes = list(leagues_map()) if league == "ALL" else [league]
    results = await asyncio.gather(
        *[_local_calendar_one(code, tz) for code in codes], return_exceptions=True,
    )
    dates: set[str] = set()
    for r in results:
        if not isinstance(r, Exception):
            dates.update(r)
    return CalendarResponse(league=league, dates=sorted(dates))


async def _calendar_raw(league: str) -> list[str]:
    """
    Các ngày có trận của một giải, dạng YYYYMMDD theo giờ UTC.

    Giải quốc nội: ESPN gói sẵn danh sách ngày trong scoreboard, một lời
    gọi là xong.

    Cúp châu Âu: ESPN KHÔNG trả danh sách ngày mà trả các GIAI ĐOẠN
    (vòng bảng, play-off, tứ kết...) kèm khoảng thời gian — không rút ra
    được ngày thi đấu nào. Trước đây điều này làm thanh chọn ngày của
    UCL/UEL/UECL trống trơn. Nay lùi về lấy ngày từ chính các trận sắp
    đá, vốn đã nằm sẵn trong cache cho màn hình "Sắp diễn ra" nên không
    tốn thêm lời gọi nào.

    Hạn chế còn lại: cách lùi này chỉ thấy các vòng sắp tới, không thấy
    các vòng đã đá xong. Chấp nhận được — người xem cúp hầu như chỉ tra
    ngày của vòng kế tiếp.
    """
    dates = await cached(
        f"calendar:{league}", TTL_LONG, lambda: provider.list_calendar(league),
    )
    if dates:
        return dates

    try:
        upcoming = await _upcoming_one(league)
    except Exception:
        return []
    return sorted({m.kickoffUtc[:10].replace("-", "") for m in upcoming})


async def _local_calendar_one(league: str, tz_minutes: int) -> set[str]:
    raw = await _calendar_raw(league)

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    past = [d for d in raw if d < today][-CALENDAR_DAYS_EACH_SIDE:]
    future = [d for d in raw if d >= today][:CALENDAR_DAYS_EACH_SIDE]
    window = past + future
    if not window:
        return set()

    results = await asyncio.gather(
        *[_matches_one(league, d) for d in window], return_exceptions=True,
    )
    out: set[str] = set()
    for r in results:
        if isinstance(r, Exception):
            continue
        for m in r:
            out.add(_local_date(m.kickoffUtc, tz_minutes))
    return out


async def get_standings(league: str) -> StandingsResponse:
    """
    Bảng xếp hạng. Giữ 10 phút: chỉ đổi sau khi một trận kết thúc nên
    không cần tươi hơn thế, mà đây lại là trang dễ bị mở đi mở lại.
    """
    season, groups = await cached(
        f"standings:{league}", TTL_MEDIUM, lambda: provider.list_standings(league),
    )
    # Gắn mã có tiền tố nguồn tại ĐÚNG MỘT chỗ, thay vì để mỗi màn hình
    # tự nối chuỗi.
    for group in groups:
        for row in group.rows:
            row.teamRef = team_ref(row.teamId)

    return StandingsResponse(
        league=league, season=season, groups=groups, logoUrl=league_logo_url(league),
    )


def _recent_seasons() -> list[str]:
    """Dùng cho phong độ riêng một đội. Chỉ cần đủ cho cửa sổ tối đa 20 trận,
    nên hai mùa (mùa hiện tại còn dở dang + mùa trước) là đủ, tải nhanh."""
    y = datetime.now(timezone.utc).year
    return [str(y), str(y - 1)]


async def _leagues_with_both(team_a_ext: str, team_b_ext: str) -> list[str]:
    """
    Những giải trong danh sách hỗ trợ mà cả hai đội đều góp mặt.

    Trước đây phần đối đầu chỉ tra lịch của đúng giải đang mở, nên hai đội
    gặp nhau ở cúp quốc gia hay cúp châu Âu thì không bao giờ hiện ra.
    Mã đội của ESPN dùng chung giữa các giải (đã kiểm chứng: Arsenal id
    359 tra được cả ở uefa.champions), nên chỉ cần biết giải nào có cả hai
    đội là tra được lịch ở đó.

    Danh sách đội mỗi giải cache 6 tiếng nên bước này gần như miễn phí.

    Hạn chế đã biết: giải cúp chỉ liệt kê đội của mùa hiện tại, nên những
    lần gặp nhau ở mùa cũ mà năm nay một đội không dự thì vẫn sót.
    """
    async def has_both(code: str) -> Optional[str]:
        try:
            teams = await cached(
                f"teams:{code}", TTL_LONG, lambda: provider.list_teams(code),
            )
        except Exception:
            return None
        ids = {t.refs[0].externalId for t in teams if t.refs}
        return code if team_a_ext in ids and team_b_ext in ids else None

    # Quét cả giải vô địch lẫn cúp — cúp mới là chỗ hay gặp nhau.
    found = await _bounded([has_both(c) for c in (*leagues_map(), *cup_leagues_map())])
    return [c for c in found if c]


def _h2h_seasons() -> list[str]:
    """
    Dùng cho đối đầu. Hai đội có thể chỉ gặp nhau một hoặc hai lần mỗi mùa,
    nên phải nhìn xa hơn nhiều mới đủ cho cửa sổ 20 trận. Đã kiểm chứng thực
    tế ESPN có dữ liệu ổn định tới bảy mùa gần nhất; mùa nào một trong hai
    đội không thi đấu giải này (ví dụ xuống hạng) thì tự nhiên không đóng
    góp trận nào, không gây lỗi.
    """
    y = datetime.now(timezone.utc).year
    return [str(y - i) for i in range(7)]


async def _load_splits(league: str, matches: list[Match]):
    async def load_one(m: Match):
        ttl = TTL_LONG if m.status == "finished" else TTL_SHORT
        ext_id = m.refs[0].externalId
        # Dùng giải của CHÍNH trận đó, không phải giải đang xem: danh sách
        # đối đầu nay gộp nhiều giải nên hai thứ này khác nhau.
        lg = m.leagueCode or league

        async def fetch():
            return await provider.get_match_detail(lg, ext_id)

        detail = await cached(f"detail:{lg}:{ext_id}", ttl, fetch)
        return m, compute_match_split(detail.match, detail.events, detail.stats)

    sem = asyncio.Semaphore(4)

    async def guarded(m: Match):
        async with sem:
            return await load_one(m)

    return await asyncio.gather(*[guarded(m) for m in matches])


def _to_match_row(match: Match, split: MatchSplitStats) -> MatchRow:
    """
    Một dòng trong bảng lịch sử theo trận. Số bàn/góc/thẻ là TỔNG hai đội.
    Tỉ số hiệp một lấy từ goals.first, vốn luôn có (chỉ phạt góc mới không
    có dữ liệu theo hiệp), nên chỉ None khi trận chưa có sự kiện nào.
    """
    total_goals = split.goals.full.home + split.goals.full.away
    total_corners = split.corners.full.home + split.corners.full.away
    total_yellow = split.cards.full.home.yellow + split.cards.full.away.yellow
    total_red = split.cards.full.home.red + split.cards.full.away.red
    ht = None
    if split.goals.first is not None:
        ht = Score(home=int(split.goals.first.home), away=int(split.goals.first.away))
    return MatchRow(
        matchId=match.id, date=match.kickoffUtc, status=match.status,
        homeTeamId=match.home.id, homeTeamName=match.home.name,
        homeTeamShort=match.home.shortName, homeTeamLogo=match.home.logoUrl,
        awayTeamId=match.away.id, awayTeamName=match.away.name,
        awayTeamShort=match.away.shortName, awayTeamLogo=match.away.logoUrl,
        score=match.score, htScore=ht,
        totalGoals=total_goals, totalCorners=total_corners,
        totalYellowCards=total_yellow, totalRedCards=total_red,
        leagueCode=match.leagueCode,
        leagueName=league_display_name(match.leagueCode) if match.leagueCode else None,
        leagueLogoUrl=league_logo_url(match.leagueCode) if match.leagueCode else None,
    )


def _build_cards(rows: list[tuple]) -> list[StatCardDto]:
    out = []
    for key, extractor in EXTRACTORS.items():
        stats: AggregatedStats = aggregate(rows, extractor)
        out.append(StatCardDto(key=key, label=LABELS[key], stats=stats))
    return out


async def get_team_form(league: str, team_external_id: str, window: int) -> TeamFormResponse:
    async def load_all():
        return await provider.list_team_matches(league, team_external_id, _recent_seasons())

    all_matches = await cached(f"schedule:{league}:{team_external_id}", TTL_MEDIUM, load_all)
    team_id = team_ref(team_external_id)
    played = [m for m in all_matches if side_of(m, team_id) is not None]
    played = last_n_matches(played, window)

    loaded = await _load_splits(league, played)
    rows = [(split, side_of(m, team_id)) for m, split in loaded]

    name = team_external_id
    if played:
        first = played[0]
        name = first.home.name if side_of(first, team_id) == "home" else first.away.name

    series: list[MatchPoint] = []
    for m, split in loaded:
        side = side_of(m, team_id)
        other = "away" if side == "home" else "home"
        opp = m.away if side == "home" else m.home
        values = {key: EXTRACTORS[key](split, side)["full"] for key in EXTRACTORS}
        scored = getattr(split.goals.full, side)
        conceded = getattr(split.goals.full, other)
        series.append(MatchPoint(
            matchId=m.id, date=m.kickoffUtc, opponent=opp.name,
            opponentShort=(opp.shortName or opp.name[:3].upper()),
            isHome=(side == "home"), scored=scored, conceded=conceded, values=values,
        ))

    match_rows = [_to_match_row(m, split) for m, split in loaded]
    match_rows.sort(key=lambda r: r.date, reverse=True)

    return TeamFormResponse(
        teamId=team_id, teamName=name, window=window,
        matchesUsed=len(rows), cards=_build_cards(rows), series=series,
        rows=match_rows,
    )


async def _h2h_candidates(
    league: str, team_a_ext: str, team_b_ext: str,
) -> list[Match]:
    """
    Mọi lần hai đội gặp nhau, gộp từ TẤT CẢ các giải mà cả hai cùng dự.

    Giải đang mở luôn được tính, kể cả khi bước dò danh sách đội thất bại,
    để tính năng không bao giờ tệ hơn trước.
    """
    codes = await _leagues_with_both(team_a_ext, team_b_ext)
    if league not in codes:
        codes = [league, *codes]

    async def one(code: str) -> list[Match]:
        return await cached(
            f"schedule_h2h:{code}:{team_a_ext}", TTL_LONG,
            lambda: provider.list_team_matches(code, team_a_ext, _h2h_seasons()),
        )

    results = await asyncio.gather(*[one(c) for c in codes], return_exceptions=True)

    team_a_id = team_ref(team_a_ext)
    team_b_id = team_ref(team_b_ext)
    seen: set[str] = set()
    out: list[Match] = []
    for r in results:
        if isinstance(r, Exception):
            continue
        for m in r:
            if m.id in seen:
                continue
            if side_of(m, team_a_id) and side_of(m, team_b_id):
                seen.add(m.id)
                out.append(m)
    return out


async def get_head_to_head(
    league: str, team_a_ext: str, team_b_ext: str, window: int,
) -> HeadToHeadResponse:
    team_a_id = team_ref(team_a_ext)
    team_b_id = team_ref(team_b_ext)

    h2h = last_n_matches(await _h2h_candidates(league, team_a_ext, team_b_ext), window)

    loaded = await _load_splits(league, h2h)
    rows_a = [(split, side_of(m, team_a_id)) for m, split in loaded]
    rows_b = [(split, side_of(m, team_b_id)) for m, split in loaded]

    def name_of(team_id: str, fallback: str) -> str:
        if not h2h:
            return fallback
        first = h2h[0]
        return first.home.name if side_of(first, team_id) == "home" else first.away.name

    return HeadToHeadResponse(
        teamA={"id": team_a_id, "name": name_of(team_a_id, team_a_ext)},
        teamB={"id": team_b_id, "name": name_of(team_b_id, team_b_ext)},
        window=window, matchesUsed=len(loaded),
        teamACards=_build_cards(rows_a), teamBCards=_build_cards(rows_b),
    )


async def get_h2h_matches(
    league: str, team_a_ext: str, team_b_ext: str, window: int,
) -> HeadToHeadMatchesResponse:
    """
    Bảng lịch sử đúng nghĩa đối đầu: chỉ những lần hai đội này thực sự gặp
    nhau. Gặp bao nhiêu lần thì trả về bấy nhiêu, không ép đủ window bằng
    cách độn thêm trận không liên quan.
    """
    team_a_id = team_ref(team_a_ext)
    team_b_id = team_ref(team_b_ext)

    h2h = last_n_matches(await _h2h_candidates(league, team_a_ext, team_b_ext), window)

    loaded = await _load_splits(league, h2h)
    match_rows = [_to_match_row(m, split) for m, split in loaded]
    match_rows.sort(key=lambda r: r.date, reverse=True)

    def name_of(team_id: str, fallback: str) -> str:
        if not h2h:
            return fallback
        first = h2h[0]
        return first.home.name if side_of(first, team_id) == "home" else first.away.name

    return HeadToHeadMatchesResponse(
        teamA={"id": team_a_id, "name": name_of(team_a_id, team_a_ext)},
        teamB={"id": team_b_id, "name": name_of(team_b_id, team_b_ext)},
        window=window, matches=match_rows,
    )


# --------------------------------------------------------------------------
# Hỏi đáp theo trận
# --------------------------------------------------------------------------

def _form_letters(form: TeamFormResponse) -> list[str]:
    """
    Chuỗi thắng/hoà/thua, trận mới nhất đứng trước.

    `series` xếp theo thứ tự thời gian tăng dần nên phải đảo lại: người
    đọc muốn thấy phong độ hiện tại trước, không phải mười trận trước.
    """
    points = sorted(form.series, key=lambda p: p.date, reverse=True)
    out: list[str] = []
    for p in points:
        if p.scored > p.conceded:
            out.append("W")
        elif p.scored < p.conceded:
            out.append("L")
        else:
            out.append("D")
    return out


async def _chat_context(
    league: str, external_id: str, tz: int,
) -> Optional[chat_answer.MatchContext]:
    """
    Gom mọi dữ liệu một câu trả lời có thể cần.

    Gần như toàn bộ đều lấy từ cache: người dùng đang đứng trong màn
    hình trận này nên thẻ chỉ số trước trận đã tải xong rồi, nghĩa là
    phong độ hai đội và chi tiết trận đều đã nằm sẵn trong bộ nhớ. Nhờ
    vậy một lượt hỏi đáp gần như không tốn gì.
    """
    async def load_detail():
        return await provider.get_match_detail(league, external_id)

    detail = await cached_dynamic(
        f"detail:{league}:{external_id}", load_detail,
        lambda d: TTL_LIVE if d.match.status in LIVE_STATUSES
        else (TTL_LONG if d.match.status == "finished" else TTL_MEDIUM),
    )
    match = detail.match

    ctx = chat_answer.MatchContext(
        home=match.home.shortName or match.home.name,
        away=match.away.shortName or match.away.name,
        home_full=match.home.name,
        away_full=match.away.name,
        kickoff_utc=match.kickoffUtc,
        tz_minutes=tz,
        source=provider_name().upper(),
    )

    ratings = await predictor_store.get_ratings(league)
    if ratings is not None and ratings.known(match.home.id) and ratings.known(match.away.id):
        ctx.prediction = predictor_predict(ratings, match.home.id, match.away.id)
        ctx.learned_matches = ratings.matches

    # Phong độ chỉ có ý nghĩa với trận chưa đá; trận đã đá xong thì
    # người dùng hỏi gì cũng nên nhìn vào số liệu thật của trận đó.
    if match.status == "scheduled":
        window = 10
        home_form, away_form = await asyncio.gather(
            get_team_form(league, match.home.refs[0].externalId, window),
            get_team_form(league, match.away.refs[0].externalId, window),
        )
        ins = _build_insights(home_form, away_form, window)
        ctx.window = window
        ctx.expected_goals = ins.expectedGoals
        ctx.expected_corners = ins.expectedCorners
        ctx.expected_cards = ins.expectedCards
        ctx.first_half_pct = ins.firstHalfGoalPct
        ctx.home_corners = ins.home.avgCorners
        ctx.away_corners = ins.away.avgCorners
        ctx.home_cards = ins.home.avgCards
        ctx.away_cards = ins.away.avgCards
        ctx.home_over95_corners = ins.home.over95CornersPct
        ctx.away_over95_corners = ins.away.over95CornersPct
        ctx.home_over35_cards = ins.home.over35CardsPct
        ctx.away_over35_cards = ins.away.over35CardsPct
        ctx.home_form = _form_letters(home_form)
        ctx.away_form = _form_letters(away_form)

    return ctx


async def answer_match_question(
    league: str, external_id: str,
    question: Optional[str] = None, intent: Optional[str] = None,
    lang: str = "vi", tz: int = 0,
) -> ChatResponse:
    ctx = await _chat_context(league, external_id, tz)
    if ctx is None:
        raise ValueError("không tìm thấy trận")
    reply = await chat_engine.reply(ctx, lang=lang, question=question, intent=intent)
    return ChatResponse(
        intent=reply.intent, confidence=reply.confidence, text=reply.text,
        action=reply.action, suggestions=reply.suggestions,
        askingBack=reply.asking_back, correctable=reply.correctable,
    )


async def teach_chat(question: str, intent: str) -> bool:
    """Ghi nhận một nhãn huấn luyện do người dùng chọn."""
    return await chat_store.teach(question, intent)


async def retrain_chat() -> dict:
    """Học lại bộ phân loại từ câu mẫu cộng câu người dùng đã dạy."""
    return await chat_store.retrain()


# --------------------------------------------------------------------------
# Phong độ cho bảng xếp hạng
# --------------------------------------------------------------------------

# Số trận hiện ở cột phong độ. Năm là đủ để thấy xu hướng mà vẫn vừa
# một dòng bảng trên màn hình điện thoại.
_STANDINGS_FORM_WINDOW = 5


async def _recent_results_for(league: str, team_external_id: str) -> list[str]:
    """
    Chuỗi W/D/L gần nhất của một đội, trận mới nhất đứng trước.

    Dùng CHUNG khoá cache với màn hình phong độ riêng từng đội
    (`schedule:…`), nên ai đã xem phong độ một đội thì cột này gần như
    miễn phí, và ngược lại. Cố ý không gọi get_team_form: hàm đó còn
    tải thêm số liệu tách hiệp của từng trận, nặng hơn nhiều mà cột này
    không cần — chỉ cần tỉ số chung cuộc.
    """
    async def load_all():
        return await provider.list_team_matches(league, team_external_id, _recent_seasons())

    try:
        matches = await cached(f"schedule:{league}:{team_external_id}", TTL_MEDIUM, load_all)
    except Exception:
        return []

    team_id = team_ref(team_external_id)
    done = [
        m for m in matches
        if m.status == "finished" and m.score is not None and side_of(m, team_id) is not None
    ]
    done.sort(key=lambda m: m.kickoffUtc, reverse=True)

    out: list[str] = []
    for m in done[:_STANDINGS_FORM_WINDOW]:
        side = side_of(m, team_id)
        scored = m.score.home if side == "home" else m.score.away
        conceded = m.score.away if side == "home" else m.score.home
        out.append("W" if scored > conceded else "L" if scored < conceded else "D")
    return out


async def get_standings_form(league: str) -> StandingsFormResponse:
    """
    Phong độ gần đây của mọi đội trong bảng, gom thành một lời gọi.

    Giới hạn 4 lượt tải song song: mỗi đội là một lời gọi ESPN riêng và
    một bảng có thể tới 20 đội, bắn hết cùng lúc là cách nhanh nhất để
    ăn 429.
    """
    standings = await get_standings(league)
    ids = [r.teamId for g in standings.groups for r in g.rows]

    async def load() -> dict[str, list[str]]:
        sem = asyncio.Semaphore(4)

        async def one(ext: str) -> tuple[str, list[str]]:
            async with sem:
                return ext, await _recent_results_for(league, ext)

        pairs = await asyncio.gather(*[one(i) for i in ids], return_exceptions=True)
        out: dict[str, list[str]] = {}
        for item in pairs:
            if isinstance(item, BaseException):
                continue
            ext, letters = item
            if letters:
                out[ext] = letters
        return out

    form = await cached(f"standform:{league}", TTL_MEDIUM, load)
    return StandingsFormResponse(league=league, form=form)
