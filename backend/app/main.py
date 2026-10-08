"""
Backend FastAPI. Dùng chung cho app di động và web sau này.

Đường dẫn và hình dạng JSON giữ y hệt bản Node/Express trước đây, nên
frontend không phải sửa gì ngoài việc đổi địa chỉ base URL.
"""
from __future__ import annotations
import asyncio
import time
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import feedback_store, service
from .cache import cache_stats
from .models import (
    CalendarResponse, ChatRequest, ChatResponse, ChatTeachRequest, ChatTeachResponse,
    FeedbackRequest, FeedbackResponse, HeadToHeadMatchesResponse,
    HeadToHeadResponse, LeagueDto, LiveResponse,
    MatchDetailResponse, MatchInsightsResponse, MatchListResponse, NewsListResponse,
    StandingsFormResponse, StandingsResponse,
    TeamFormResponse, TeamListResponse, UpcomingMatchesResponse,
)
from .providers import get_provider, leagues_map, provider_name
from .providers.base import ProviderBusy

app = FastAPI(title="Football Stats API")

_warm_task: Optional[asyncio.Future] = None


@app.on_event("startup")
async def _warm_up() -> None:
    """
    Nạp trước cache lịch thi đấu ngay sau khi server lên.

    Chạy nền, KHÔNG chặn server nhận request: nếu ESPN chậm hay lỗi thì
    app vẫn phục vụ bình thường, chỉ là người mở đầu tiên phải chờ lâu
    hơn ở thanh chọn ngày.
    """
    global _warm_task

    async def calendar_loop() -> None:
        while True:
            try:
                done = await service.warm_calendar_cache()
                print(f"[warm] lịch: {done}/{len(leagues_map())} giải")
            except Exception as exc:
                print(f"[warm] lỗi nạp lịch: {exc}")
            # Lịch gần như không đổi; nạp lại trước khi cache 6 tiếng hết hạn.
            await asyncio.sleep(5 * 60 * 60)

    async def chat_warm_loop() -> None:
        """
        Học bộ phân loại câu hỏi ngay sau khi server lên.

        Lần học đầu mất vài giây. Để nó xảy ra lúc người dùng hỏi câu
        đầu tiên thì người đó phải ngồi chờ, nên làm trước ở đây. Lần
        khởi động sau đọc thẳng từ file, gần như tức thì.
        """
        from .chat import store as chat_store
        try:
            model = await chat_store.get_model()
            print(f"[chat] sẵn sàng: {len(model.intents)} ý định, "
                  f"{model.trained_on} câu mẫu, chính xác {model.accuracy:.0%}")
        except Exception as exc:
            print(f"[chat] lỗi khởi động: {exc}")

    async def predictor_loop() -> None:
        """
        Học lại mô hình dự đoán mỗi 6 tiếng.

        Chạy sau cùng và giãn cách rộng: nó cần lịch thi đấu của mọi đội
        qua bốn mùa, là phần nặng nhất trong các việc chạy nền. Học xong
        một lần là dùng được cả ngày, nên không việc gì phải vội.
        """
        await asyncio.sleep(90)
        while True:
            try:
                res = await service.train_predictor()
                if res:
                    avg = sum(r["brier"] for r in res) / len(res)
                    print(f"[predictor] học xong {len(res)} giải, Brier TB {avg:.4f}")
            except Exception as exc:
                print(f"[predictor] lỗi: {exc}")

            # Bộ phân loại câu hỏi học lại cùng nhịp. Nó rẻ hơn hẳn
            # (vài giây, không gọi mạng) nên đi ké chứ không cần vòng
            # lặp riêng; và chỉ có ý nghĩa khi đã có người dùng dạy
            # thêm câu, nên 6 tiếng một lần là quá đủ.
            try:
                res = await service.retrain_chat()
                if res["taught"]:
                    verdict = "nhận" if res["accepted"] else "bỏ"
                    print(f"[chat] học lại từ {res['taught']} câu người dùng dạy: "
                          f"{res['accuracy']:.0%} so với {res['previous']:.0%} — {verdict}")
            except Exception as exc:
                print(f"[chat] lỗi: {exc}")

            await asyncio.sleep(6 * 60 * 60)

    async def today_loop() -> None:
        """
        Giữ cho cửa sổ hôm nay luôn ấm.

        Mười phút một lần: đủ dày để bản cũ không bao giờ rơi ra ngoài
        thời gian ân hạn một tiếng, mà tính ra chỉ khoảng bốn lượt gọi
        ESPN mỗi phút — nhẹ hơn nhiều so với một người dùng đang lướt.
        """
        while True:
            await asyncio.sleep(10 * 60)
            try:
                done = await service.warm_today_window()
                print(f"[warm] hôm nay: {done} mục")
            except Exception as exc:
                print(f"[warm] lỗi nạp hôm nay: {exc}")

    async def run() -> None:
        # Nạp cửa sổ hôm nay TRƯỚC rồi mới tới lịch cả mùa.
        #
        # Hai việc này tranh nhau cùng một hạn mức gọi ESPN song song.
        # Lịch cả mùa nặng gấp nhiều lần (hơn 200 lượt gọi) nên nếu chạy
        # song song thì nó chiếm chỗ, khiến danh sách trận và mục "sắp
        # diễn ra" — thứ người dùng nhìn thấy ngay — phải chờ theo.
        # Thanh chọn ngày hiện muộn vài giây thì không ai để ý.
        await today_loop_once()
        await asyncio.gather(
            calendar_loop(), today_loop(), chat_warm_loop(), predictor_loop(),
        )

    async def today_loop_once() -> None:
        try:
            done = await service.warm_today_window()
            print(f"[warm] hôm nay (ưu tiên): {done} mục")
        except Exception as exc:
            print(f"[warm] lỗi nạp hôm nay: {exc}")

    _warm_task = asyncio.ensure_future(run())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _check_league(league: str) -> str:
    code = league.upper()
    if code not in leagues_map():
        raise HTTPException(400, f"Giải không hợp lệ: {league}")
    return code


def _check_league_or_all(league: str) -> str:
    """
    Cho hai endpoint liệt kê trận: "ALL" nghĩa là gộp cả 12 giải, dùng cho
    trang chính. Các endpoint còn lại (chi tiết trận, đối đầu, phong độ)
    luôn cần đúng một giải cụ thể nên vẫn dùng _check_league như cũ.
    """
    code = league.upper()
    if code == "ALL":
        return code
    return _check_league(league)


@app.get("/api/predictor")
async def predictor_status():
    """Tình trạng mô hình dự đoán: đã học bao nhiêu trận, điểm Brier hiện
    tại so với mốc đoán theo tỉ lệ nền."""
    from .predictor import results_store as predictor_results
    from .predictor import store as predictor_store
    return {
        "leagues": await predictor_store.summary(),
        # Số trận đang giữ trên đĩa cho từng giải. Kho này là lý do
        # việc huấn luyện không còn phải tải lại lịch từ nhà cung cấp
        # mỗi chu kỳ — xem predictor/results_store.py.
        "stored": await predictor_results.summary(),
    }


@app.get("/api/standings/form", response_model=StandingsFormResponse)
async def standings_form(league: str):
    """
    Phong độ 5 trận gần nhất của từng đội trong bảng xếp hạng.

    Tách riêng khỏi /api/standings vì nó nặng hơn hẳn: ESPN không trả
    kèm phong độ trong dữ liệu xếp hạng nên phải tra lịch từng đội. Giao
    diện vẽ bảng trước, cột phong độ điền vào sau khi về.
    """
    return await service.get_standings_form(league)


@app.get("/api/chat")
async def chat_status():
    """Tình trạng bộ phân loại câu hỏi: độ chính xác, đã được dạy thêm
    bao nhiêu câu, và mỗi lần học lại có được nhận hay không."""
    from .chat import store as chat_store
    return await chat_store.summary()


# Hỏi đáp chạy hoàn toàn trong máy chủ này, không gọi ra ngoài, nên
# giới hạn chỉ để chặn kịch bản tự động quét chứ không phải để tiết
# kiệm chi phí — vì vậy đặt rộng tay.
_CHAT_PER_HOUR = 240
_chat_hits: dict[str, list[float]] = {}


def _rate_limited(bucket: dict[str, list[float]], ip: str, limit: int) -> bool:
    now = time.time()
    hits = [t for t in bucket.get(ip, []) if now - t < 3600]
    if len(hits) >= limit:
        bucket[ip] = hits
        return True
    hits.append(now)
    bucket[ip] = hits
    return False


@app.post("/api/matches/{external_id}/chat", response_model=ChatResponse)
async def match_chat(external_id: str, body: ChatRequest, request: Request):
    """
    Một lượt hỏi đáp về đúng trận này.

    Mọi con số đều đọc từ mô hình Poisson và bảng phong độ đã nạp sẵn
    cho màn hình trận, nên lượt hỏi gần như không tốn gì và không phụ
    thuộc dịch vụ bên ngoài nào.
    """
    ip = request.client.host if request.client else "?"
    if _rate_limited(_chat_hits, ip, _CHAT_PER_HOUR):
        raise HTTPException(429, "Bạn hỏi hơi nhanh, thử lại sau một lát nhé")

    question = (body.question or "").strip()[:200]
    try:
        return await service.answer_match_question(
            body.league, external_id,
            question=question or None, intent=body.intent,
            lang=body.lang, tz=body.tz,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@app.post("/api/chat/teach", response_model=ChatTeachResponse)
async def chat_teach(body: ChatTeachRequest, request: Request):
    """
    Người dùng vừa chọn giúp ý định cho câu mình gõ.

    Không học lại ngay: học lại mất vài giây và chỉ có ý nghĩa khi gom
    đủ một ít câu, nên chỉ ghi lại, còn học thì để vòng chạy nền.
    """
    ip = request.client.host if request.client else "?"
    if _rate_limited(_chat_hits, ip, _CHAT_PER_HOUR):
        raise HTTPException(429, "Thử lại sau một lát nhé")
    stored = await service.teach_chat(body.question, body.intent)
    return ChatTeachResponse(stored=stored)


@app.get("/api/health")
async def health():
    """Giữ nguyên trường ok để frontend cũ không hỏng, phần còn lại thêm
    vào để soi được cache đang đỡ được bao nhiêu và ESPN có đang chặn
    mình không mà không cần vào xem log."""
    return {
        "ok": True,
        "cache": cache_stats(),
        # Nguồn dữ liệu đang chạy tự khai tình trạng của mình. Trước đây
        # khoá này tên cứng là "espn" — đổi nguồn thì cái tên nói dối.
        "provider": provider_name(),
        "source": get_provider().health(),
    }


# Chống spam đơn giản: mỗi địa chỉ IP gửi tối đa ngần này góp ý mỗi giờ.
# Link app là công khai nên không thể để ngỏ, nhưng cũng đừng siết tới
# mức người dùng thật gửi hai ý kiến liền là bị chặn.
_FEEDBACK_PER_HOUR = 5
_feedback_hits: dict[str, list[float]] = {}


@app.post("/api/feedback", response_model=FeedbackResponse)
async def feedback(body: FeedbackRequest, request: Request):
    text = (body.message or "").strip()
    if len(text) < 5:
        raise HTTPException(400, "Nội dung góp ý quá ngắn")

    now = time.time()
    ip = request.client.host if request.client else "?"
    hits = [t for t in _feedback_hits.get(ip, []) if now - t < 3600]
    if len(hits) >= _FEEDBACK_PER_HOUR:
        raise HTTPException(429, "Bạn đã gửi khá nhiều góp ý, thử lại sau nhé")
    hits.append(now)
    _feedback_hits[ip] = hits

    kind = body.kind if body.kind in ("bug", "idea", "other") else "other"
    res = await feedback_store.add(
        text, kind, body.contact, body.lang, body.platform,
    )
    return FeedbackResponse(ok=True, emailed=res["emailed"])


@app.exception_handler(ProviderBusy)
async def _provider_busy(request: Request, exc: ProviderBusy):
    """
    Nguồn dữ liệu đang nghỉ hồi sau khi bị chặn tần suất.

    Trả 503 kèm câu giải thích thay vì để lỗi thành 500 trống: app đọc
    thân phản hồi dạng JSON, gặp chữ "Internal Server Error" sẽ báo lỗi
    phân tích JSON khó hiểu thay vì nói thật là đang bận.
    """
    return JSONResponse(
        status_code=503,
        content={"detail": "Nguồn dữ liệu đang bận, thử lại sau một lát."},
    )


@app.get("/api/leagues", response_model=list[LeagueDto])
async def leagues():
    return service.list_leagues()


@app.get("/api/matches", response_model=MatchListResponse)
async def matches(league: str, date: Optional[str] = None, tz: Optional[int] = None):
    """tz là số phút cộng vào UTC để ra giờ địa phương của người dùng
    (Việt Nam = 420). Có tz thì `date` được hiểu là ngày địa phương chứ
    không phải ngày UTC — xem ghi chú về múi giờ trong service.py."""
    return await service.list_matches(_check_league_or_all(league), date, tz)


@app.get("/api/matches/upcoming", response_model=UpcomingMatchesResponse)
async def upcoming_matches(league: str):
    return await service.list_upcoming_matches(_check_league_or_all(league))


@app.get("/api/live", response_model=LiveResponse)
async def live(league: str):
    """Cập nhật tỉ số và đồng hồ trận đang đá. Payload nhỏ, gọi lại đều
    đặn; dùng chung cache với /api/matches nên không sinh thêm tải ESPN."""
    return await service.get_live(_check_league_or_all(league))


@app.get("/api/calendar", response_model=CalendarResponse)
async def calendar(league: str, tz: Optional[int] = None):
    """Những ngày có trận, tính theo ngày địa phương của người dùng."""
    return await service.get_calendar(_check_league_or_all(league), tz)


@app.get("/api/standings", response_model=StandingsResponse)
async def standings(league: str):
    """Bảng xếp hạng một giải. Không nhận ALL: gộp 12 bảng khác nhau lại
    thành một danh sách không có ý nghĩa gì."""
    return await service.get_standings(_check_league(league))


@app.get("/api/news", response_model=NewsListResponse)
async def news(league: str):
    return await service.list_news(_check_league_or_all(league))


@app.get("/api/matches/{external_id}/insights", response_model=MatchInsightsResponse)
async def match_insights(external_id: str, league: str, lang: str = "vi"):
    """Bảng soi kèo và nhận định AI. Tách khỏi /api/matches/{id} vì phải
    tải phong độ hai đội, mất vài giây khi cache nguội."""
    try:
        return await service.get_match_insights(_check_league(league), external_id, lang)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/api/matches/{external_id}", response_model=MatchDetailResponse)
async def match_detail(external_id: str, league: str, lang: str = "vi"):
    try:
        return await service.get_match_detail(_check_league(league), external_id, lang)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/api/teams", response_model=TeamListResponse)
async def teams(league: str):
    return await service.list_teams(_check_league(league))


@app.get("/api/teams/{external_id}/form", response_model=TeamFormResponse)
async def team_form(external_id: str, league: str, window: int = Query(10)):
    if window not in (5, 10, 20):
        raise HTTPException(400, "window chỉ nhận 5, 10 hoặc 20")
    return await service.get_team_form(_check_league(league), external_id, window)


@app.get("/api/h2h", response_model=HeadToHeadResponse)
async def head_to_head(league: str, teamA: str, teamB: str, window: int = Query(10)):
    if window not in (5, 10, 20):
        raise HTTPException(400, "window chỉ nhận 5, 10 hoặc 20")
    return await service.get_head_to_head(_check_league(league), teamA, teamB, window)


@app.get("/api/h2h/matches", response_model=HeadToHeadMatchesResponse)
async def h2h_matches(league: str, teamA: str, teamB: str, window: int = Query(10)):
    if window not in (5, 10, 20):
        raise HTTPException(400, "window chỉ nhận 5, 10 hoặc 20")
    return await service.get_h2h_matches(_check_league(league), teamA, teamB, window)
