/**
 * Từ điển đa ngôn ngữ.
 *
 * Nguyên tắc: tên đội, tên cầu thủ, tên sân là danh từ riêng lấy từ ESPN,
 * không dịch. Mọi chữ còn lại trên giao diện đều nằm trong thư mục
 * locales/, không viết chuỗi cứng trong file màn hình.
 *
 * Thêm ngôn ngữ mới: tạo locales/<mã>.ts theo đúng interface Dict, rồi
 * khai báo ở LANGUAGES và translations bên dưới. TypeScript sẽ báo lỗi
 * ngay nếu thiếu bất kỳ chuỗi nào, nên không sợ dịch sót.
 *
 * Chưa hỗ trợ ngôn ngữ viết từ phải sang trái (Ả Rập, Do Thái) vì cần đảo
 * toàn bộ bố cục (I18nManager), không chỉ dịch chữ.
 */
import { de } from './locales/de';
import { en } from './locales/en';
import { es } from './locales/es';
import { fr } from './locales/fr';
import { id } from './locales/id';
import { it } from './locales/it';
import { ja } from './locales/ja';
import { ko } from './locales/ko';
import { pt } from './locales/pt';
import { th } from './locales/th';
import { vi } from './locales/vi';
import { zh } from './locales/zh';

export type Lang =
  | 'vi' | 'en' | 'es' | 'pt' | 'fr' | 'de'
  | 'it' | 'id' | 'th' | 'ja' | 'ko' | 'zh';

/** Hình dạng chuẩn của từ điển. Mọi ngôn ngữ phải khớp đúng dạng này. */
export interface Dict {
  /**
   * Tên giải đấu — CHỈ khai những giải mà ngôn ngữ này gọi khác tên gốc.
   *
   * Phần lớn tên giải là danh từ riêng ("MLS", "Eredivisie", "J1
   * League") nên giữ nguyên ở mọi ngôn ngữ; tên nào không khai ở đây
   * thì app dùng tên backend gửi về. Nhờ vậy thêm một giải không kéo
   * theo 12 bản dịch cho một cái tên vốn không dịch.
   */
  league: {
    ALL: string;
    [code: string]: string;
  };
  menu: {
    title: string;
    close: string;
    settings: string;
    language: string;
    /** Công tắc hiện/ẩn phần vạch kèo thị trường. */
    showOdds: string;
    showOddsHint: string;
  };
  tab: { matches: string; compare: string; news: string; standings: string };
  news: {
    brand: string; sub: string; empty: string; readMore: string;
    justNow: string;
    minutesAgo: (n: number) => string;
    hoursAgo: (n: number) => string;
    daysAgo: (n: number) => string;
  };
  home: {
    brand: string; sub: string; upcoming: string; recent: string;
    matchCount: (n: number) => string;
    loadingLeague: (name: string) => string;
    emptyLeague: string; viewStats: string; pullToRefresh: string;
    upcomingError: (msg: string) => string;
    searchPlaceholder: string;
    noSearchResults: (query: string) => string;
    noFavoritesYet: string;
    noFavMatches: string;
    liveOnly: string;
    noLiveMatches: string;
    pickDate: string;
    /** Hôm nay không có trận nào trong giải đang chọn. */
    noMatchesToday: string;
    /** Nhãn mục cho ngày đang chọn khi đó không phải hôm nay. */
    matchesOn: (day: string) => string;
  };

  standings: {
    brand: string; sub: string; empty: string; team: string;
    /** Nhãn cột viết tắt: đã đá, thắng, hòa, thua, hiệu số, điểm. */
    played: string; win: string; draw: string; loss: string;
    /** Tiêu đề cột phong độ 5 trận gần nhất. */
    form: string;
    goalDiff: string; points: string;
  };
  status: {
    live: string; halftime: string; finished: string;
    postponed: string; cancelled: string; scheduled: string;
  };
  day: { today: string; tomorrow: string; yesterday: string; weekday: string[] };
  stat: {
    goalsFor: string; goalsAgainst: string; corners: string;
    yellowCards: string; redCards: string;
  };
  period: { first: string; second: string; full: string };
  window: { n5: string; n10: string; n20: string };
  matchDetail: {
    back: string; home: string; away: string; hint: string; loading: string;
    statsOf: (period: string) => string; cornerHint: string;
    basedOnEvents: (n: number) => string;
    tabThis: string; tabHistory: string;
    watchHighlights: string;
    referee: string;
    refereeAvg: (yellow: number, red: number, n: number) => string;
    refereeLowData: (n: number) => string;
    aiAnalysis: string;
    aiPrediction: string;
    aiPredictionDisclaimer: string;
    tabTimeline: string;
    tabLineups: string;
    timelineEmpty: string;
    lineupsEmpty: string;
    /** Giải thích điểm số liệu dưới sơ đồ sân — bắt buộc hiện kèm,
     *  xem backend/app/rating.py về lý do. */
    ratingNote: string;
    bench: string;
    statsTitle: string;
    statsEmpty: string;
    possession: string;
    shots: string;
    shotsOnTarget: string;
    fouls: string;
    offsides: string;
    passAccuracy: string;
    saves: string;
    tackles: string;
    interceptions: string;
    substitutionOf: (onName: string, offName: string) => string;
    event: {
      goal: string; ownGoal: string; penaltyGoal: string; penaltyMissed: string;
      secondYellow: string; substitution: string;
    };
  };
  teamForm: {
    loadingWindow: (n: number) => string; basedOn: (n: number) => string;
    perMatch: string; noHalfData: string; trendTitle: string;
    resultWin: string; resultDraw: string; resultLoss: string;
    tabForm: string; tabRecent: string;
  };
  matchTable: {
    goals: string; corners: string; yellow: string; red: string;
    /** Bộ lọc giải trong bảng đối đầu. */
    allCompetitions: string;
    competition: string;
    /** Nhãn trên dòng ứng với chính trận đang mở, dòng đó không bấm được. */
    viewing: string;
    ht: (h: number, a: number) => string;
    metTimes: (n: number) => string;
    noRows: string;
    loading: string;
  };
  insights: {
    title: string;
    basedOn: (n: number) => string;
    expected: string;
    cards: string;
    over25: string;
    over95Corners: string;
    over35Cards: string;
    btts: string;
    halfSplit: string;
    disclaimer: string;
    notEnough: string;
    marketLine: string;
    ouLine: string;
    handicap: string;
  };

  compare: {
    brand: string; sub: string; chooseFirst: string; chooseSecond: string;
    tapToRemove: string; ctaReady: string; ctaNotReady: string;
    loadingTeams: string; longPressTip: string;
  };
  h2h: {
    teamA: string; teamB: string; loading: string; empty: string;
    basedOn: (n: number) => string; legend: (a: string, b: string) => string;
  };
  share: {
    button: string;
    title: string;
    story: string;
    square: string;
    save: string;
    doShare: string;
    saved: string;
    failed: string;
    expected: string;
  };

  feedback: {
    open: string;
    title: string;
    sub: string;
    kindBug: string;
    kindIdea: string;
    kindOther: string;
    messagePlaceholder: string;
    contactLabel: string;
    contactPlaceholder: string;
    send: string;
    sending: string;
    thanks: string;
    tooShort: string;
    failed: string;
    tooMany: string;
  };
  /**
   * Khung hỏi đáp của từng trận.
   *
   * Nhãn các nút gợi ý nằm ở đây chứ không phải ở backend: backend chỉ
   * gửi về mã ý định ("corners"), còn chữ hiển thị do giao diện tự
   * dịch. Nhờ vậy thêm một thứ tiếng không phải đụng tới API, và một
   * câu trả lời đã lưu không bao giờ bị kẹt ở ngôn ngữ cũ.
   */
  chat: {
    title: string;
    sub: string;
    placeholder: string;
    send: string;
    thinking: string;
    failed: string;
    askBack: string;
    wrong: string;
    taught: string;
    openTab: string;
    clear: string;
    intents: {
      outcome: string; score: string; total_goals: string; over_under: string;
      btts: string; handicap: string; team_goals: string; clean_sheet: string;
      corners: string; cards: string; halves: string; form: string;
      h2h: string; standings: string; kickoff: string; injuries: string;
      model_info: string;
    };
  };
  common: { retry: string; loading: string; loadFailed: string; noData: string };
}

/**
 * Tên ngôn ngữ viết bằng chính ngôn ngữ đó (endonym) — người dùng nhận ra
 * tiếng mẹ đẻ của mình nhanh hơn nhiều so với tên đã dịch.
 */
export const LANGUAGES: ReadonlyArray<{ code: Lang; label: string; short: string }> = [
  { code: 'vi', label: 'Tiếng Việt', short: 'VI' },
  { code: 'en', label: 'English', short: 'EN' },
  { code: 'es', label: 'Español', short: 'ES' },
  { code: 'pt', label: 'Português', short: 'PT' },
  { code: 'fr', label: 'Français', short: 'FR' },
  { code: 'de', label: 'Deutsch', short: 'DE' },
  { code: 'it', label: 'Italiano', short: 'IT' },
  { code: 'id', label: 'Bahasa Indonesia', short: 'ID' },
  { code: 'th', label: 'ไทย', short: 'TH' },
  { code: 'ja', label: '日本語', short: 'JA' },
  { code: 'ko', label: '한국어', short: 'KO' },
  { code: 'zh', label: '中文', short: 'ZH' },
];

export const translations: Record<Lang, Dict> = {
  vi, en, es, pt, fr, de, it, id, th, ja, ko, zh,
};
