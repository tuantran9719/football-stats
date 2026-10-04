/**
 * Mô hình dữ liệu và hợp đồng API.
 *
 * Trước đây nằm ở gói dùng chung @fb/types trong monorepo TypeScript.
 * Từ khi backend chuyển sang FastAPI (Python), hai bên không còn chia sẻ
 * mã nguồn được nữa, nên các kiểu này được khai báo lại ở đây, khớp đúng
 * hình dạng JSON mà backend/app/models.py (Pydantic) trả về.
 *
 * Nếu đổi hình dạng response ở backend, phải sửa cả hai nơi.
 */

export type TeamSide = 'home' | 'away';
export type Period = 'first' | 'second' | 'et1' | 'et2';
export type MatchStatus =
  | 'scheduled' | 'live' | 'halftime' | 'finished' | 'postponed' | 'cancelled';
export type Window = 5 | 10 | 20;
export type StatKey = 'goalsFor' | 'goalsAgainst' | 'corners' | 'yellowCards' | 'redCards';

export interface ProviderRef {
  provider: string;
  externalId: string;
}

export interface Team {
  id: string;
  name: string;
  shortName?: string;
  logoUrl?: string;
  refs: ProviderRef[];
}

export interface Score {
  home: number;
  away: number;
}

export interface Match {
  id: string;
  leagueCode: string;
  season: string;
  kickoffUtc: string;
  status: MatchStatus;
  home: Team;
  away: Team;
  /** Backend gửi tường minh null cho trận chưa đá, không chỉ bỏ trống. */
  score?: Score | null;
  refs: ProviderRef[];
  /** Đồng hồ trận đấu đã định dạng sẵn ("67'", "90'+4'"). Chỉ có khi
   *  trận đang diễn ra; trận đã đá xong backend chủ động bỏ trống. */
  clock?: string | null;
  period?: number | null;
}

/** Phần biến động của một trận, dùng cho cập nhật trực tiếp. */
export interface LiveMatch {
  id: string;
  status: MatchStatus;
  score?: Score | null;
  clock?: string | null;
  period?: number | null;
}

export interface LiveResponse {
  league: string;
  matches: LiveMatch[];
  /** Server gợi ý bao lâu nữa nên hỏi lại. Không có trận nào đang đá thì
   *  giãn ra để khỏi gọi vô ích. */
  pollAfterSeconds: number;
}

export interface SideValue {
  home: number;
  away: number;
}

export interface CardCount {
  yellow: number;
  red: number;
}

export interface SideCards {
  home: CardCount;
  away: CardCount;
}

export interface PeriodSplit<T> {
  first: T | null;
  second: T | null;
  full: T;
}

export interface MatchSplitStats {
  matchId: string;
  goals: PeriodSplit<SideValue>;
  cards: PeriodSplit<SideCards>;
  corners: PeriodSplit<SideValue>;
}

export interface AggregatedStats {
  sampleSize: number;
  withData: number;
  avgFirst: number | null;
  avgSecond: number | null;
  avgFull: number;
}

export interface StatCardDto {
  key: StatKey;
  label: string;
  stats: AggregatedStats;
}

export interface MatchPoint {
  matchId: string;
  date: string;
  opponent: string;
  opponentShort: string;
  isHome: boolean;
  scored: number;
  conceded: number;
  values: Record<StatKey, number>;
}

// ---------------------------------------------------------------- API

export interface LeagueDto {
  code: string;
  name: string;
  logoUrl?: string | null;
}

export interface MatchListResponse {
  league: string;
  matches: Match[];
}

export interface UpcomingMatchesResponse {
  league: string;
  matches: Match[];
}

export interface TeamListResponse {
  league: string;
  teams: Team[];
}

export interface NewsItem {
  id: string;
  leagueCode: string;
  headline: string;
  description?: string | null;
  imageUrl?: string | null;
  publishedUtc: string;
  /** Trang bài viết gốc trên espn.com, mở ngoài app. */
  webUrl: string;
}

export interface NewsListResponse {
  league: string;
  articles: NewsItem[];
}

export interface RefereeInfo {
  name: string;
  matchesTracked: number;
  avgYellowCards?: number | null;
  avgRedCards?: number | null;
}

export interface AiPrediction {
  homeScore: number;
  awayScore: number;
  corners: number;
  yellowCards: number;
  note: string;
}

export type MatchEventType =
  | 'goal' | 'own_goal' | 'penalty_goal' | 'penalty_missed'
  | 'yellow_card' | 'red_card' | 'second_yellow' | 'substitution'
  | 'period_start' | 'period_end' | 'other';

export interface MatchEvent {
  matchId: string;
  minute: number;
  extraMinute?: number | null;
  period: Period;
  type: MatchEventType;
  side: TeamSide;
  playerName?: string | null;
  /** Người rời sân trong một lượt thay người. */
  secondPlayerName?: string | null;
  description?: string | null;
}

/** Số liệu cả trận của một đội. Mọi trường đều có thể trống vì ESPN
 *  không công bố đủ chỉ số cho mọi giải. */
export interface TeamMatchStats {
  corners?: number | null;
  shots?: number | null;
  shotsOnTarget?: number | null;
  fouls?: number | null;
  offsides?: number | null;
  possessionPct?: number | null;
  yellowCards?: number | null;
  redCards?: number | null;
  saves?: number | null;
  passPct?: number | null;
  accuratePasses?: number | null;
  totalPasses?: number | null;
  tackles?: number | null;
  interceptions?: number | null;
}

export interface MatchTeamStats {
  matchId: string;
  home: TeamMatchStats;
  away: TeamMatchStats;
}

export interface LineupPlayer {
  name: string;
  /** Tên ngắn ("D. Petrovic"), dùng khi vẽ trên sân cho khỏi chồng chữ. */
  shortName?: string | null;
  jersey?: string | null;
  position?: string | null;
  starter: boolean;
  photoUrl?: string | null;
  /** Số thứ tự trong sơ đồ do nguồn đánh. KHÔNG chạy theo hàng — xem
   *  ghi chú trong components/pitch.tsx trước khi dùng để xếp vị trí. */
  formationPlace?: number | null;
  subbedIn: boolean;
  subbedOut: boolean;
  goals: number;
  assists: number;
  shots: number;
  shotsOnTarget: number;
  yellowCards: number;
  redCards: number;
  ownGoals: number;
  foulsCommitted: number;
  foulsSuffered: number;
  offsides: number;
  saves: number;
  goalsConceded: number;
  /** Điểm số liệu 0-10 do app tự tính, null khi trận chưa đá. */
  rating?: number | null;
}

export interface TeamLineup {
  side: TeamSide;
  teamName: string;
  formation?: string | null;
  starters: LineupPlayer[];
  bench: LineupPlayer[];
}

export interface StandingRow {
  rank: number;
  teamId: string;
  /** Mã đội kèm tiền tố nguồn ("espn:359") — dùng cái này khi so với
   *  danh sách yêu thích, đừng tự nối tiền tố ở giao diện. */
  teamRef?: string | null;
  teamName: string;
  shortName?: string | null;
  logoUrl?: string | null;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDiff: number;
  points: number;
}

/** Cúp châu Âu chia bảng nên có thể nhiều nhóm; giải quốc nội chỉ một. */
export interface StandingGroup {
  name: string;
  rows: StandingRow[];
}

export interface StandingsResponse {
  league: string;
  season?: string | null;
  groups: StandingGroup[];
  logoUrl?: string | null;
}

/**
 * Thiên hướng của một đội qua N trận gần nhất. Mọi con số tính theo TỔNG
 * hai đội trong mỗi trận: "2.4 bàn/trận" nghĩa là các trận có đội này
 * thường có 2.4 bàn, không phải đội này ghi 2.4 bàn.
 */
export interface TeamTendency {
  teamId: string;
  teamName: string;
  matches: number;
  avgGoals: number;
  avgCorners: number;
  avgCards: number;
  over25GoalsPct: number;
  over95CornersPct: number;
  over35CardsPct: number;
  bttsPct: number;
  firstHalfGoalPct?: number | null;
}

export interface BettingInsights {
  window: number;
  home: TeamTendency;
  away: TeamTendency;
  expectedGoals: number;
  expectedCorners: number;
  expectedCards: number;
  firstHalfGoalPct?: number | null;
}

export interface MatchDetailResponse {
  match: Match;
  split: MatchSplitStats;
  eventCount: number;
  /** Trang xem clip trên espn.com, không phải link video trực tiếp. */
  highlightUrl?: string | null;
  referee?: RefereeInfo | null;
  /** Diễn biến theo phút, đã sắp sẵn từ backend. */
  events: MatchEvent[];
  teamStats?: MatchTeamStats | null;
  /** Rỗng khi ESPN chưa công bố đội hình. */
  lineups: TeamLineup[];
}

/**
 * Phần nặng của màn hình chi tiết trận, tải riêng sau khi trang đã hiện.
 * Mọi trường đều có thể trống: trận đã đá xong không có gì ở đây, còn
 * hết hạn mức AI thì hai trường AI trống nhưng bảng soi kèo vẫn đủ.
 */
/**
 * Vạch kèo thị trường, dùng làm mốc đối chiếu cho phần thống kê.
 * Cố ý không có đường dẫn sang nhà cái — xem ghi chú ở backend.
 */
export interface MatchOdds {
  provider?: string | null;
  overUnder?: number | null;
  spread?: number | null;
  details?: string | null;
  homeMoneyLine?: number | null;
  awayMoneyLine?: number | null;
  drawMoneyLine?: number | null;
}

export interface FeedbackRequest {
  message: string;
  kind: 'bug' | 'idea' | 'other';
  contact?: string;
  lang?: string;
  platform?: string;
}

export interface FeedbackResponse {
  ok: boolean;
  /** Đã gửi email chưa. false vẫn là thành công — góp ý đã được lưu. */
  emailed: boolean;
}

/** Những ngày có trận, dạng YYYYMMDD. */
export interface CalendarResponse {
  league: string;
  dates: string[];
}

export interface MatchInsightsResponse {
  insights?: BettingInsights | null;
  odds?: MatchOdds | null;
  aiAnalysis?: string | null;
  aiPrediction?: AiPrediction | null;
}

/**
 * Một dòng trong bảng lịch sử theo trận (đối đầu hoặc phong độ riêng một đội).
 * Bàn thắng/phạt góc/thẻ là TỔNG của cả hai đội trong trận đó.
 */
export interface MatchRow {
  matchId: string;
  date: string;
  status: MatchStatus;
  homeTeamId: string;
  homeTeamName: string;
  homeTeamShort?: string;
  homeTeamLogo?: string;
  awayTeamId: string;
  awayTeamName: string;
  awayTeamShort?: string;
  awayTeamLogo?: string;
  score?: Score | null;
  htScore?: Score | null;
  totalGoals?: number | null;
  totalCorners?: number | null;
  totalYellowCards?: number | null;
  totalRedCards?: number | null;
  /** Giải của chính trận đó — danh sách đối đầu gộp nhiều giải. */
  leagueCode?: string | null;
  /** Tên hiển thị kèm theo. Các giải cúp không nằm trong từ điển dịch
   *  (đều là danh từ riêng) nên phải lấy tên từ backend. */
  leagueName?: string | null;
  leagueLogoUrl?: string | null;
}

export interface TeamFormResponse {
  teamId: string;
  teamName: string;
  window: Window;
  matchesUsed: number;
  cards: StatCardDto[];
  series: MatchPoint[];
  rows: MatchRow[];
}

export interface HeadToHeadResponse {
  teamA: { id: string; name: string };
  teamB: { id: string; name: string };
  window: Window;
  matchesUsed: number;
  teamACards: StatCardDto[];
  teamBCards: StatCardDto[];
}

export interface HeadToHeadMatchesResponse {
  teamA: { id: string; name: string };
  teamB: { id: string; name: string };
  window: Window;
  matches: MatchRow[];
}

/** Mã ý định mà bot hỏi đáp trả lời được. Trùng với app/chat/intents.py. */
export type ChatIntent =
  | 'outcome' | 'score' | 'total_goals' | 'over_under' | 'btts' | 'handicap'
  | 'team_goals' | 'clean_sheet' | 'corners' | 'cards' | 'halves' | 'form'
  | 'h2h' | 'standings' | 'kickoff' | 'injuries' | 'model_info';

/**
 * Phong độ gần đây của mọi đội trong một bảng xếp hạng.
 *
 * Khoá là mã đội của ESPN (trùng StandingRow.teamId), giá trị là chuỗi
 * 'W'/'D'/'L' với trận MỚI NHẤT ĐỨNG TRƯỚC.
 */
export interface StandingsFormResponse {
  league: string;
  form: Record<string, string[]>;
}

export interface ChatRequest {
  league: string;
  /** Câu người dùng gõ. Bỏ trống khi bấm thẳng nút gợi ý. */
  question?: string;
  /** Bấm nút gợi ý thì gửi mã ý định, khỏi qua bộ phân loại. */
  intent?: ChatIntent;
  lang: string;
  tz: number;
}

export interface ChatResponse {
  /** 'unknown' nghĩa là bot không hiểu hoặc câu nằm ngoài phạm vi. */
  intent: ChatIntent | 'unknown';
  confidence: number;
  text: string;
  /** Tab nên mở khi dữ liệu nằm ở màn hình khác. */
  action?: 'history' | 'lineups' | 'standings' | null;
  suggestions: ChatIntent[];
  /** True khi bot phân vân và nhờ người dùng chọn giúp — chọn xong thì
   *  gửi lựa chọn đó về cho bot học. */
  askingBack: boolean;
  /** True khi bot đã trả lời nhưng chưa chắc hiểu đúng; giao diện mời
   *  người dùng sửa bằng một chạm, và cú chạm đó là nhãn huấn luyện. */
  correctable: boolean;
}
