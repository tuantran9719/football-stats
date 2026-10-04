"""
Mô hình dữ liệu chuẩn, tương đương packages/types của bản Node trước đây.

Nguyên tắc giữ nguyên: mọi nguồn dữ liệu bên ngoài phải được adapter chuyển
về đúng các kiểu trong file này. Phần còn lại của backend không bao giờ
chạm vào JSON thô của nhà cung cấp.
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel

# Tên nguồn dữ liệu, ví dụ "espn" hay "demo". Cố ý để kiểu chuỗi tự do
# chứ không liệt kê sẵn: danh sách nguồn thuộc về providers/__init__.py,
# tầng mô hình dữ liệu không nên biết có những nguồn nào. Trước đây đây
# là Literal["espn"], và chỉ riêng dòng đó đã đủ chặn mọi nguồn khác.
Provider = str
TeamSide = Literal["home", "away"]
Period = Literal["first", "second", "et1", "et2"]
MatchStatus = Literal[
    "scheduled", "live", "halftime", "finished", "postponed", "cancelled"
]
MatchEventType = Literal[
    "goal", "own_goal", "penalty_goal", "penalty_missed",
    "yellow_card", "red_card", "second_yellow", "substitution",
    "corner", "period_start", "period_end", "other",
]
StatKey = Literal["goalsFor", "goalsAgainst", "corners", "yellowCards", "redCards"]


class ProviderRef(BaseModel):
    provider: Provider
    externalId: str


class Team(BaseModel):
    id: str
    name: str
    shortName: Optional[str] = None
    logoUrl: Optional[str] = None
    refs: list[ProviderRef]


class Score(BaseModel):
    home: int
    away: int


class Match(BaseModel):
    id: str
    leagueCode: str
    season: str
    kickoffUtc: str
    status: MatchStatus
    home: Team
    away: Team
    score: Optional[Score] = None
    refs: list[ProviderRef]
    # Đồng hồ trận đấu, chỉ có ý nghĩa khi trận đang diễn ra. ESPN trả sẵn
    # chuỗi đã định dạng ("67'", "90'+4'") nên giữ nguyên dạng chuỗi thay
    # vì tự dựng lại từ số giây, tránh lệch với cách ESPN làm tròn.
    clock: Optional[str] = None
    period: Optional[int] = None


class LiveMatch(BaseModel):
    """
    Bản rút gọn của Match chỉ gồm những trường thay đổi trong lúc trận
    đang đá. Dùng cho endpoint cập nhật liên tục: app gọi lại mỗi 25 giây
    nên payload phải nhỏ, không việc gì phải gửi lại tên đội và logo.
    """
    id: str
    status: MatchStatus
    score: Optional[Score] = None
    clock: Optional[str] = None
    period: Optional[int] = None


class LiveResponse(BaseModel):
    league: str
    matches: list[LiveMatch]
    """Số giây app nên chờ trước lần hỏi tiếp theo. Server tự quyết định
    để lúc không có trận nào đang đá thì app giãn ra, khỏi gọi vô ích."""
    pollAfterSeconds: int


class MatchEvent(BaseModel):
    matchId: str
    minute: int
    extraMinute: Optional[int] = None
    period: Period
    type: MatchEventType
    side: TeamSide
    playerName: Optional[str] = None
    # Người thứ hai liên quan: cầu thủ rời sân trong một lượt thay người.
    # Với bàn thắng ESPN không tách riêng người kiến tạo, chỉ nhắc trong
    # description, nên trường này chủ yếu dùng cho thay người.
    secondPlayerName: Optional[str] = None
    description: Optional[str] = None


class TeamMatchStats(BaseModel):
    corners: Optional[float] = None
    shots: Optional[float] = None
    shotsOnTarget: Optional[float] = None
    fouls: Optional[float] = None
    offsides: Optional[float] = None
    possessionPct: Optional[float] = None
    yellowCards: Optional[float] = None
    redCards: Optional[float] = None
    # Thêm khi làm bảng thống kê chi tiết. Không đưa vào phần tách theo
    # hiệp vì ESPN chỉ trả tổng cả trận cho mấy chỉ số này.
    saves: Optional[float] = None
    passPct: Optional[float] = None
    accuratePasses: Optional[float] = None
    totalPasses: Optional[float] = None
    tackles: Optional[float] = None
    interceptions: Optional[float] = None


class MatchStats(BaseModel):
    matchId: str
    home: TeamMatchStats
    away: TeamMatchStats


class SideValue(BaseModel):
    home: float
    away: float


class CardCount(BaseModel):
    yellow: int
    red: int


class SideCards(BaseModel):
    home: CardCount
    away: CardCount


class GoalsSplit(BaseModel):
    """first/second có thể None nghĩa là không có dữ liệu, khác 0."""
    first: Optional[SideValue] = None
    second: Optional[SideValue] = None
    full: SideValue


class CardsSplit(BaseModel):
    first: Optional[SideCards] = None
    second: Optional[SideCards] = None
    full: SideCards


class CornersSplit(BaseModel):
    first: Optional[SideValue] = None
    second: Optional[SideValue] = None
    full: SideValue


class MatchSplitStats(BaseModel):
    matchId: str
    goals: GoalsSplit
    cards: CardsSplit
    corners: CornersSplit


class MatchDetail(BaseModel):
    match: Match
    events: list[MatchEvent]
    stats: Optional[MatchStats] = None
    highlightUrl: Optional[str] = None
    refereeName: Optional[str] = None
    lineups: list["TeamLineup"] = []
    odds: Optional["MatchOdds"] = None


class LineupPlayer(BaseModel):
    name: str
    """Tên ngắn ("D. Petrovic") để vẽ dưới mỗi ô trên sân — tên đầy đủ
    dài quá, chồng lên nhau ở sơ đồ 4-2-3-1 trên màn hình điện thoại."""
    shortName: Optional[str] = None
    jersey: Optional[str] = None
    position: Optional[str] = None
    starter: bool
    # Ảnh cầu thủ. Có thể trống với cầu thủ trẻ chưa có ảnh.
    photoUrl: Optional[str] = None

    """
    Vị trí trong sơ đồ, do nguồn đánh số 1..11.

    Dùng để xếp cầu thủ lên sân đúng chỗ. Số 1 luôn là thủ môn; các số
    sau chạy từ hàng thủ lên hàng công, nhưng CÁCH ĐÁNH SỐ KHÔNG ĐỒNG
    NHẤT giữa các sơ đồ, nên phần vẽ sân còn phải đọc thêm hậu tố trái/
    phải trong `position` ("CD-L", "AM-R") mới xếp ngang được.
    """
    formationPlace: Optional[int] = None
    subbedIn: bool = False
    subbedOut: bool = False

    """Số liệu thô của trận. Chỉ có khi trận đã đá."""
    goals: int = 0
    assists: int = 0
    shots: int = 0
    shotsOnTarget: int = 0
    yellowCards: int = 0
    redCards: int = 0
    ownGoals: int = 0
    foulsCommitted: int = 0
    foulsSuffered: int = 0
    offsides: int = 0
    saves: int = 0
    goalsConceded: int = 0

    """
    Điểm số liệu 0-10, tự tính (xem app/rating.py). None khi trận chưa
    đá hoặc cầu thủ không ra sân.
    """
    rating: Optional[float] = None


class TeamLineup(BaseModel):
    side: TeamSide
    teamName: str
    formation: Optional[str] = None
    starters: list[LineupPlayer]
    bench: list[LineupPlayer]


class StandingRow(BaseModel):
    rank: int
    """Mã thô của nhà cung cấp, ví dụ "359"."""
    teamId: str
    """Cùng mã đó nhưng có tiền tố nguồn ("espn:359") — đúng dạng mà đội
    yêu thích lưu trên máy. Trước đây giao diện tự nối chuỗi "espn:" vào
    teamId, nên đổi nguồn là mục yêu thích ở bảng xếp hạng lặng lẽ hỏng
    mà không có lỗi nào hiện ra."""
    teamRef: Optional[str] = None
    teamName: str
    shortName: Optional[str] = None
    logoUrl: Optional[str] = None
    played: int
    wins: int
    draws: int
    losses: int
    goalsFor: int
    goalsAgainst: int
    goalDiff: int
    points: int


class StandingGroup(BaseModel):
    """Giải cúp châu Âu chia bảng nên bảng xếp hạng có thể gồm nhiều nhóm;
    giải quốc nội chỉ có đúng một nhóm."""
    name: str
    rows: list[StandingRow]


class StandingsFormResponse(BaseModel):
    """
    Phong độ 5 trận gần nhất của từng đội trong bảng xếp hạng.

    Tách khỏi /api/standings thành một lời gọi riêng, có chủ đích: bảng
    xếp hạng chỉ tốn ĐÚNG MỘT lời gọi ESPN, còn phong độ phải tra lịch
    của từng đội một (ESPN không trả kèm phong độ trong dữ liệu xếp
    hạng). Gộp chung thì bảng đang hiện gần như tức thì sẽ phải nằm chờ
    hai chục lời gọi mới vẽ được dòng đầu tiên.

    Khoá là mã đội của ESPN, giá trị là chuỗi 'W'/'D'/'L', TRẬN MỚI
    NHẤT ĐỨNG TRƯỚC.
    """
    league: str
    form: dict[str, list[str]]


class StandingsResponse(BaseModel):
    league: str
    season: Optional[str] = None
    groups: list[StandingGroup]
    logoUrl: Optional[str] = None


class AggregatedStats(BaseModel):
    sampleSize: int
    withData: int
    avgFirst: Optional[float] = None
    avgSecond: Optional[float] = None
    avgFull: float


# ------------------------------------------------ Hợp đồng API (frontend)

class LeagueDto(BaseModel):
    code: str
    name: str
    # Logo giải của ESPN, dùng làm biểu tượng nhỏ cạnh tên giải. None với
    # vài giải cúp mà ESPN không có logo.
    logoUrl: Optional[str] = None


class MatchListResponse(BaseModel):
    league: str
    matches: list[Match]


class UpcomingMatchesResponse(BaseModel):
    league: str
    matches: list[Match]


class NewsItem(BaseModel):
    id: str
    leagueCode: str
    headline: str
    description: Optional[str] = None
    imageUrl: Optional[str] = None
    publishedUtc: str
    # Trang bài viết gốc trên espn.com — không lấy nội dung đầy đủ về app,
    # cùng lý do với highlightUrl: tránh sao chép nội dung có bản quyền.
    webUrl: str


class NewsListResponse(BaseModel):
    league: str
    articles: list[NewsItem]


class TeamListResponse(BaseModel):
    league: str
    teams: list[Team]


class RefereeInfo(BaseModel):
    """
    Thống kê rút thẻ của trọng tài, tự tích lũy dần từ các trận app đã xem
    qua (xem service.get_match_detail + referee_store), KHÔNG phải số liệu
    trọn sự nghiệp trọng tài lấy từ nguồn ngoài — nên matchesTracked càng
    nhỏ thì độ tin cậy càng thấp, hiển thị rõ con số này cho người dùng biết.
    """
    name: str
    matchesTracked: int
    avgYellowCards: Optional[float] = None
    avgRedCards: Optional[float] = None


class AiPrediction(BaseModel):
    """
    Dự đoán tỷ số/phạt góc/thẻ vàng do AI suy luận từ trung bình phong độ
    gần đây của hai đội — một ước lượng thống kê, KHÔNG phải lời khuyên cá
    cược hay cam kết chính xác, nên luôn kèm "note" giải thích ngắn.
    """
    homeScore: int
    awayScore: int
    corners: int
    yellowCards: int
    note: str


class TeamTendency(BaseModel):
    """
    Thiên hướng của một đội qua N trận gần nhất, tính theo TỔNG hai đội
    trong mỗi trận chứ không riêng đội này.

    Lý do: người xem để bắt kèo tài/xỉu quan tâm tổng bàn, tổng góc, tổng
    thẻ của cả trận. "Đội A trung bình 3,2 bàn/trận" ở đây nghĩa là các
    trận có đội A thường có 3,2 bàn, không phải đội A ghi 3,2 bàn.
    """
    teamId: str
    teamName: str
    matches: int
    avgGoals: float
    avgCorners: float
    avgCards: float
    """Phần trăm số trận vượt mốc quen thuộc của nhà cái."""
    over25GoalsPct: float
    over95CornersPct: float
    over35CardsPct: float
    """Phần trăm số trận cả hai đội đều ghi bàn."""
    bttsPct: float
    """Phần trăm bàn thắng rơi vào hiệp một. None khi chưa có bàn nào."""
    firstHalfGoalPct: Optional[float] = None


class MatchOdds(BaseModel):
    """
    Vạch kèo thị trường do ESPN công bố, dùng làm MỐC ĐỐI CHIẾU cho phần
    thống kê bên cạnh: thị trường đặt vạch ở đâu so với con số kỳ vọng
    tính từ phong độ.

    Cố ý KHÔNG lấy các đường dẫn đặt cược mà ESPN kèm theo. Hiển thị vạch
    kèo như một dữ liệu thể thao là chuyện bình thường, nhưng dẫn thẳng
    sang nhà cái sẽ xếp app vào nhóm cờ bạc tiền thật trên App Store và
    Google Play, kéo theo cả một quy trình phê duyệt riêng.
    """
    provider: Optional[str] = None
    """Vạch tài/xỉu tổng bàn thắng, thường là 2.5."""
    overUnder: Optional[float] = None
    """Kèo chấp. Số âm nghĩa là đội nhà chấp."""
    spread: Optional[float] = None
    """Tóm tắt do ESPN viết sẵn, ví dụ "SAO +100"."""
    details: Optional[str] = None
    homeMoneyLine: Optional[int] = None
    awayMoneyLine: Optional[int] = None
    drawMoneyLine: Optional[int] = None


class BettingInsights(BaseModel):
    """
    Bảng tóm tắt cho trận CHƯA đá, gộp thiên hướng của hai đội.

    Các con số kỳ vọng chỉ là trung bình cộng hai đội — cố ý giữ đơn giản
    và dễ kiểm chứng bằng mắt, không phải mô hình xác suất. Người dùng
    nhìn thấy ngay hai cột nguồn nên tự đánh giá được độ tin cậy.
    """
    window: int
    home: TeamTendency
    away: TeamTendency
    expectedGoals: float
    expectedCorners: float
    expectedCards: float
    firstHalfGoalPct: Optional[float] = None


class MatchDetailResponse(BaseModel):
    match: Match
    split: MatchSplitStats
    eventCount: int
    # Trang xem clip trên espn.com, KHÔNG phải link video trực tiếp. Điều
    # khoản của ESPN/Disney cấm phát lại video của họ trong app bên thứ ba,
    # nên chỉ điều hướng người dùng sang xem trên nền tảng của ESPN.
    highlightUrl: Optional[str] = None
    referee: Optional[RefereeInfo] = None
    # Diễn biến trận theo phút (bàn thắng, thẻ, thay người). Trận đang đá
    # thì danh sách này dài dần ra theo mỗi lần làm mới.
    events: list[MatchEvent] = []
    # Số liệu thô cả trận của hai đội, dùng cho bảng so sánh chi tiết.
    # Khác với split ở chỗ split chỉ tách bàn/góc/thẻ theo hiệp.
    teamStats: Optional[MatchStats] = None
    # Đội hình ra sân. Trống khi ESPN chưa công bố (thường là trước giờ
    # bóng lăn khoảng một tiếng).
    lineups: list[TeamLineup] = []


class ChatRequest(BaseModel):
    """
    Một lượt hỏi trong khung hỏi đáp của trận.

    Hai cách hỏi, loại trừ nhau: `question` là câu người dùng gõ tay,
    `intent` là mã ý định khi người dùng bấm thẳng nút gợi ý. Bấm nút
    thì bỏ qua bộ phân loại — đã biết chắc rồi, cho nó đi qua chỗ có
    thể đoán sai là tự chuốc lỗi.
    """
    league: str
    question: Optional[str] = None
    intent: Optional[str] = None
    lang: str = "vi"
    """Lệch múi giờ tính bằng phút, để trả lời giờ thi đấu theo giờ máy."""
    tz: int = 0


class ChatResponse(BaseModel):
    intent: str
    confidence: float
    text: str
    """Tab nên mở khi dữ liệu người dùng hỏi nằm ở màn hình khác."""
    action: Optional[str] = None
    """Mã ý định cho các nút gợi ý. Nhãn hiển thị do giao diện tự dịch,
    backend không gửi chữ — nhờ vậy thêm ngôn ngữ không phải đụng API."""
    suggestions: list[str] = []
    """True khi bot không chắc và đang nhờ người dùng chọn giúp. Giao
    diện dùng cờ này để gửi lựa chọn về cho bot học."""
    askingBack: bool = False
    """True khi bot đã trả lời nhưng chưa chắc mình hiểu đúng — giao
    diện mời người dùng sửa bằng một chạm."""
    correctable: bool = False


class ChatTeachRequest(BaseModel):
    """Người dùng vừa chọn giúp ý định cho câu mình gõ — một nhãn huấn
    luyện, đến từ chính người viết câu đó."""
    question: str
    intent: str


class ChatTeachResponse(BaseModel):
    stored: bool


class FeedbackRequest(BaseModel):
    message: str
    # Loại góp ý, để phân loại lúc đọc: bug | idea | other.
    kind: str = "other"
    # Cách liên hệ lại, không bắt buộc.
    contact: Optional[str] = None
    lang: Optional[str] = None
    platform: Optional[str] = None


class FeedbackResponse(BaseModel):
    ok: bool
    # Đã gửi được email chưa. False vẫn là thành công: góp ý đã lưu
    # an toàn vào file, chỉ là máy chủ mail chưa cấu hình hoặc lỗi.
    emailed: bool = False


class CalendarResponse(BaseModel):
    """
    Những ngày THẬT SỰ có trận của một giải, dạng YYYYMMDD.

    Lấy từ trường calendar trong scoreboard của ESPN — đó là lịch toàn
    mùa, nên chỉ tốn một lượt gọi cho mỗi giải chứ không phải dò từng
    ngày. Dùng để dựng thanh chọn ngày: trước đây thanh này hiện cứng
    bảy ngày mỗi phía, bấm vào ngày trống chỉ nhận lại màn hình rỗng.
    """
    league: str
    dates: list[str]


class MatchInsightsResponse(BaseModel):
    """
    Phần "nặng" của màn hình chi tiết trận, tải sau và tải riêng.

    Mọi trường đều có thể trống: trận đã đá xong thì không có gì ở đây,
    còn nhà cung cấp AI hết hạn mức thì hai trường AI trống nhưng bảng
    soi kèo vẫn đầy đủ vì nó thuần thống kê, không cần AI.
    """
    insights: Optional[BettingInsights] = None
    odds: Optional[MatchOdds] = None
    aiAnalysis: Optional[str] = None
    aiPrediction: Optional[AiPrediction] = None


class MatchRow(BaseModel):
    """
    Một dòng trong bảng lịch sử theo trận (đối đầu hoặc phong độ riêng một đội).

    Số liệu là TỔNG của cả hai đội trong trận đó (bàn thắng, phạt góc, thẻ),
    đúng kiểu người xem cá cược cần để soi tài xỉu. Tỉ số và tỉ số hiệp một
    thì vẫn giữ tách home/away vì đó là con số cụ thể của trận, không phải
    một chỉ số để cộng dồn.
    """
    matchId: str
    date: str
    status: MatchStatus
    homeTeamId: str
    homeTeamName: str
    homeTeamShort: Optional[str] = None
    homeTeamLogo: Optional[str] = None
    awayTeamId: str
    awayTeamName: str
    awayTeamShort: Optional[str] = None
    awayTeamLogo: Optional[str] = None
    score: Optional[Score] = None
    htScore: Optional[Score] = None
    totalGoals: Optional[float] = None
    totalCorners: Optional[float] = None
    totalYellowCards: Optional[float] = None
    totalRedCards: Optional[float] = None
    # Giải của chính trận đó. Danh sách đối đầu gộp nhiều giải nên mỗi
    # dòng phải tự nói mình thuộc giải nào.
    leagueCode: Optional[str] = None
    # Tên hiển thị kèm theo, vì các giải cúp không nằm trong từ điển dịch
    # của app (đều là danh từ riêng, không dịch).
    leagueName: Optional[str] = None
    leagueLogoUrl: Optional[str] = None


class StatCardDto(BaseModel):
    key: StatKey
    label: str
    stats: AggregatedStats


class MatchPoint(BaseModel):
    matchId: str
    date: str
    opponent: str
    opponentShort: str
    isHome: bool
    scored: float
    conceded: float
    values: dict[StatKey, float]


class TeamFormResponse(BaseModel):
    teamId: str
    teamName: str
    window: int
    matchesUsed: int
    cards: list[StatCardDto]
    series: list[MatchPoint]
    rows: list[MatchRow] = []


class HeadToHeadResponse(BaseModel):
    teamA: dict[str, str]
    teamB: dict[str, str]
    window: int
    matchesUsed: int
    teamACards: list[StatCardDto]
    teamBCards: list[StatCardDto]


class HeadToHeadMatchesResponse(BaseModel):
    teamA: dict[str, str]
    teamB: dict[str, str]
    window: int
    matches: list[MatchRow]


# MatchDetail tham chiếu TeamLineup bằng chuỗi vì TeamLineup được khai báo
# sau nó trong file này. Gọi rebuild ở cuối module để Pydantic phân giải
# xong ngay lúc import, thay vì để lỗi nổ ra lần đầu dựng đối tượng.
MatchDetail.model_rebuild()
