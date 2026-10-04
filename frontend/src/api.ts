/**
 * Kết nối tới backend FastAPI.
 *
 * Trước đây phần gọi API nằm ở gói dùng chung @fb/api-client. Từ khi
 * backend chuyển sang Python và tách thành thư mục riêng, không còn
 * workspace chung để chia sẻ mã nguồn nữa nên client này sống hẳn trong
 * frontend. Backend Python mặc định chạy ở cổng 4000, giống bản Node cũ,
 * nên không phải đổi gì khác ngoài file này.
 *
 * Địa chỉ được xác định theo thứ tự ưu tiên:
 *   1. Biến môi trường EXPO_PUBLIC_API_BASE nếu có đặt sẵn lúc chạy Expo.
 *      Dùng khi backend và Metro có hai địa chỉ công khai khác nhau, ví dụ
 *      khi chạy qua đường hầm (tunnel) để người ngoài mạng nội bộ test thử.
 *   2. Tự dò theo địa chỉ Metro đang chạy (cùng máy, cổng 4000). Đúng khi
 *      máy tính và điện thoại chung một mạng WiFi, không cần sửa gì tay.
 */
import Constants from 'expo-constants';
import type {
  CalendarResponse, ChatIntent, ChatRequest, ChatResponse,
  FeedbackRequest, FeedbackResponse, HeadToHeadMatchesResponse,
  HeadToHeadResponse, LeagueDto, LiveResponse,
  MatchDetailResponse, MatchInsightsResponse, MatchListResponse, NewsListResponse,
  StandingsFormResponse, StandingsResponse, TeamFormResponse, TeamListResponse, UpcomingMatchesResponse, Window,
} from './types';

const PORT = 4000;

/**
 * Số phút cộng vào UTC để ra giờ máy người dùng (Việt Nam = 420).
 *
 * Phải gửi kèm mọi chỗ liên quan tới "ngày", vì ESPN làm việc theo ngày
 * UTC còn người dùng đọc giờ theo máy mình. Chênh 7 tiếng là đủ lệch hẳn
 * một ngày: trận 21:30 UTC ngày 03/10 hiện trên app là 04:30 sáng 04/10.
 *
 * getTimezoneOffset() trả về UTC trừ giờ địa phương nên phải đảo dấu.
 */
export function tzOffsetMinutes(): number {
  return -new Date().getTimezoneOffset();
}

function detectHost(): string {
  const hostUri =
    Constants.expoConfig?.hostUri ??
    (Constants.expoGoConfig as { debuggerHost?: string } | undefined)?.debuggerHost;
  const host = hostUri?.split(':')[0];
  if (host && host.length > 0) return host;

  // Bản web tĩnh (expo export) không có hostUri. Lấy luôn host của trang
  // đang mở: vào bằng localhost thì gọi backend ở localhost, vào bằng IP
  // LAN từ điện thoại thì gọi đúng IP đó — khỏi phải build lại mỗi lần
  // router đổi IP máy.
  const pageHost = typeof window !== 'undefined' ? window.location?.hostname : undefined;
  if (pageHost && pageHost.length > 0) return pageHost;

  return 'localhost';
}

/**
 * Giá trị đặc biệt cho EXPO_PUBLIC_API_BASE: gọi API ngay trên gốc của
 * trang đang mở, thay vì một địa chỉ cố định.
 *
 * Dùng khi máy chủ web chuyển tiếp /api sang backend (xem serve.py).
 * Khi đó bundle không chứa địa chỉ nào cả, nên cùng một bản build chạy
 * đúng ở localhost, ở IP trong mạng LAN và qua đường hầm công khai —
 * đổi tên miền không phải build lại. Trước đây địa chỉ backend bị nhúng
 * cứng lúc build, đường hầm đổi URL là link gửi đi hỏng ngay.
 */
const SAME_ORIGIN = 'same-origin';

function resolveBase(): string {
  const override = process.env.EXPO_PUBLIC_API_BASE;
  if (override && override.length > 0) {
    if (override === SAME_ORIGIN) {
      const origin = typeof window !== 'undefined' ? window.location?.origin : undefined;
      // Bản chạy trên điện thoại (native) không có window.location, lúc
      // đó lùi về cách dò theo địa chỉ Metro như cũ.
      if (origin) return origin;
      return `http://${detectHost()}:${PORT}`;
    }
    return override.replace(/\/$/, '');
  }
  return `http://${detectHost()}:${PORT}`;
}

export const API_BASE = resolveBase();

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

async function call<T>(
  path: string, params: Record<string, string | number | undefined> = {},
  signal?: AbortSignal,
): Promise<T> {
  const url = new URL(path, API_BASE);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) url.searchParams.set(k, String(v));
  }

  // Bên gọi có thể tự hủy (ví dụ vòng lặp cập nhật trực tiếp khi người
  // dùng đổi giải), nhưng vẫn giữ nguyên mốc hết giờ chung cho mọi lượt.
  const ctrl = new AbortController();
  const onAbort = () => ctrl.abort();
  signal?.addEventListener('abort', onAbort);
  const timer = setTimeout(() => ctrl.abort(), 60000);
  try {
    const res = await fetch(url.toString(), {
      signal: ctrl.signal,
      // ngrok (gói miễn phí) chặn mọi request trông giống trình duyệt
      // bằng một trang cảnh báo HTML. Nếu lời gọi API dính trang đó thì
      // app nhận về HTML thay vì JSON và hỏng hoàn toàn. Header này bảo
      // ngrok cho đi thẳng; ở mọi môi trường khác nó chỉ là một header
      // thừa, không ảnh hưởng gì.
      headers: { 'ngrok-skip-browser-warning': '1' },
    });
    const body = await res.json();
    if (!res.ok) {
      throw new ApiError((body as { detail?: string }).detail ?? `HTTP ${res.status}`, res.status);
    }
    return body as T;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onAbort);
  }
}

export const api = {
  health: () => call<{ ok: boolean }>('/api/health'),

  /** Gửi góp ý của người dùng. Lỗi 429 nghĩa là gửi quá nhiều. */
  sendFeedback: async (body: FeedbackRequest): Promise<FeedbackResponse> => {
    const res = await fetch(new URL('/api/feedback', API_BASE).toString(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': '1',
      },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new ApiError((data as { detail?: string }).detail ?? `HTTP ${res.status}`, res.status);
    }
    return data as FeedbackResponse;
  },

  /**
   * Một lượt hỏi đáp về một trận.
   *
   * Chạy hoàn toàn bằng mô hình trong máy chủ, không gọi dịch vụ AI
   * nào, nên nhanh và không có hạn mức.
   */
  matchChat: async (matchExternalId: string, body: ChatRequest): Promise<ChatResponse> => {
    const res = await fetch(
      new URL(`/api/matches/${matchExternalId}/chat`, API_BASE).toString(),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': '1' },
        body: JSON.stringify(body),
      },
    );
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new ApiError((data as { detail?: string }).detail ?? `HTTP ${res.status}`, res.status);
    }
    return data as ChatResponse;
  },

  /**
   * Dạy cho bot biết câu vừa gõ thuộc nhóm nào.
   *
   * Gửi đi khi người dùng chọn một gợi ý sau lúc bot nói "ý bạn là
   * câu nào?". Lỗi thì nuốt luôn: dạy được thì tốt, không được cũng
   * không ảnh hưởng gì tới câu trả lời người dùng vừa nhận.
   */
  teachChat: async (question: string, intent: ChatIntent): Promise<void> => {
    try {
      await fetch(new URL('/api/chat/teach', API_BASE).toString(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': '1' },
        body: JSON.stringify({ question, intent }),
      });
    } catch {
      // Không làm gì: đây là việc phụ, không phải việc người dùng nhờ.
    }
  },

  leagues: () => call<LeagueDto[]>('/api/leagues'),

  matches: (league: string, date?: string) =>
    call<MatchListResponse>('/api/matches', {
      league, date, tz: date ? tzOffsetMinutes() : undefined,
    }),

  upcomingMatches: (league: string) =>
    call<UpcomingMatchesResponse>('/api/matches/upcoming', { league }),

  news: (league: string) =>
    call<NewsListResponse>('/api/news', { league }),

  /** Những ngày có trận, để thanh chọn ngày chỉ hiện ngày dùng được. */
  calendar: (league: string) =>
    call<CalendarResponse>('/api/calendar', { league, tz: tzOffsetMinutes() }),

  /** Bảng xếp hạng. Không nhận 'ALL' — gộp 12 bảng lại thì vô nghĩa. */
  standings: (league: string) =>
    call<StandingsResponse>('/api/standings', { league }),

  /** Phong độ 5 trận gần nhất cho cột cuối bảng xếp hạng. Tải riêng vì
   *  phải tra lịch từng đội; bảng vẽ xong trước, cột này điền sau. */
  standingsForm: (league: string, signal?: AbortSignal) =>
    call<StandingsFormResponse>('/api/standings/form', { league }, signal),

  /** Cập nhật tỉ số/đồng hồ, payload nhỏ, gọi lặp lại khi có trận đang đá. */
  live: (league: string, signal?: AbortSignal) =>
    call<LiveResponse>('/api/live', { league }, signal),

  matchDetail: (league: string, matchExternalId: string, lang?: string) =>
    call<MatchDetailResponse>(`/api/matches/${matchExternalId}`, { league, lang }),

  /** Bảng soi kèo + nhận định AI. Tách riêng vì phải tải phong độ hai
   *  đội, mất vài giây khi cache nguội — đừng để nó chặn cả trang. */
  matchInsights: (league: string, matchExternalId: string, lang?: string) =>
    call<MatchInsightsResponse>(`/api/matches/${matchExternalId}/insights`, { league, lang }),

  teams: (league: string) => call<TeamListResponse>('/api/teams', { league }),

  teamForm: (league: string, teamId: string, window: Window = 10) =>
    call<TeamFormResponse>(`/api/teams/${teamId}/form`, { league, window }),

  headToHead: (league: string, teamA: string, teamB: string, window: Window = 10) =>
    call<HeadToHeadResponse>('/api/h2h', { league, teamA, teamB, window }),

  h2hMatches: (league: string, teamA: string, teamB: string, window: Window = 10) =>
    call<HeadToHeadMatchesResponse>('/api/h2h/matches', { league, teamA, teamB, window }),
};
