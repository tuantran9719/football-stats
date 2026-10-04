/**
 * Màn hình chính: chọn giải và xem danh sách trận.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  FlatList, Pressable, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { LiveMatch, Match } from '../types';
import { api } from '../api';
import { isLiveStatus, mergeLive, useLiveScores } from '../useLiveScores';
import { colors, font, radius, shadow, space } from '../theme';
import {
  Empty, ErrorBox, HeaderGlow, LangSwitch, Pill, PressScale, Reveal, TeamLogo,
} from '../components/ui';
import { HamburgerButton, LeagueMenu } from '../components/leagueMenu';
import { BrandLockup } from '../components/brand';
import { FeedbackButton, FeedbackSheet } from '../components/feedback';
import { useLeagueLogos } from '../leagueLogos';
import { MatchListSkeleton } from '../components/skeleton';
import { useFavorites } from '../favorites';
import { useLeagues } from '../leagueLogos';
import { useI18n } from '../i18n';
import type { Dict } from '../i18n/translations';

/**
 * Danh sách tối thiểu, chỉ dùng trong lúc chờ backend trả về danh sách
 * thật. KHÔNG phải danh sách đầy đủ — backend đang phục vụ gần 40 giải.
 */
export const LEAGUE_CODES = [
  'EPL', 'LALIGA', 'SERIEA', 'BUNDES', 'LIGUE1',
  'UCL', 'UEL', 'UECL', 'EFLCHAMP', 'EREDIV', 'PRIMEIRA', 'BRASILEIRAO',
] as const;

/**
 * Mã giải là chuỗi tự do chứ không phải danh sách đóng.
 *
 * Trước đây đây là union của 12 mã nhúng cứng, nên backend thêm giải
 * mới thì app không hiện ra cho tới khi người dùng cập nhật qua cửa
 * hàng — đúng thứ cần tránh.
 */
export type LeagueValue = string;

/**
 * Tên hiển thị của một mã giải.
 *
 * Một chỗ duy nhất quyết định "bản dịch nếu có, không thì tên backend",
 * để ba màn hình dùng tên giải không trôi mỗi nơi một kiểu.
 */
export function useLeagueName(): (code: string) => string {
  const { t } = useI18n();
  const leagues = useLeagues();
  const dict = t.league as Record<string, string | undefined>;
  return (code: string) => {
    if (dict[code]) return dict[code] as string;
    return leagues.find((l) => l.code === code)?.name ?? code;
  };
}

/** Trang chính lọc theo một giải cụ thể, hoặc 'ALL' để gộp tất cả. */
export type HomeFilter = 'ALL' | LeagueValue;

/** Giải mở sẵn khi vào app. */
export const DEFAULT_LEAGUE: LeagueValue = 'EPL';

/**
 * Danh sách giải cho menu.
 *
 * Tên lấy theo thứ tự: bản dịch trong app nếu có (chỉ vài giải thật sự
 * đổi tên theo ngôn ngữ, như "Ngoại hạng Anh"), còn lại dùng tên
 * backend gửi về. Nhờ vậy thêm giải không phải viết 12 bản dịch cho
 * một cái tên vốn là danh từ riêng ("J1 League", "MLS", "Eredivisie").
 */
export function useLeagueOptions(): Array<{ value: LeagueValue; label: string }> {
  const leagues = useLeagues();
  const name = useLeagueName();

  if (leagues.length === 0) {
    return LEAGUE_CODES.map((v) => ({ value: v as LeagueValue, label: name(v) }));
  }
  return leagues.map((l) => ({ value: l.code, label: name(l.code) }));
}

/** So khớp không phân biệt hoa/thường và bỏ dấu, để gõ "mu" vẫn ra "Manchester United". */
function normalize(s: string) {
  return s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim();
}

function matchesQuery(m: Match, query: string) {
  const q = normalize(query);
  if (!q) return true;
  return normalize(m.home.name).includes(q) || normalize(m.away.name).includes(q);
}

function fmtDate(iso: string) {
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`;
}
function fmtTime(iso: string) {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function StatusBadge({ m, t }: { m: Match; t: Dict }) {
  // Trận đang đá thì hiện phút thi đấu thay cho chữ "Trực tiếp": người
  // xem cần biết trận tới phút bao nhiêu hơn là biết nó đang diễn ra,
  // chấm đỏ nhấp nháy của Pill đã nói lên điều đó rồi.
  if (m.status === 'live') return <Pill text={m.clock || t.status.live} tone="live" />;
  if (m.status === 'halftime') return <Pill text={t.status.halftime} tone="live" />;
  if (m.status === 'finished') return <Pill text={t.status.finished} tone="done" />;
  if (m.status === 'postponed') return <Pill text={t.status.postponed} />;
  if (m.status === 'cancelled') return <Pill text={t.status.cancelled} />;
  return <Pill text={t.status.scheduled} tone="accent" />;
}

/** Nhãn ngày dễ đọc: Hôm nay, Ngày mai, hoặc thứ trong tuần. */
/** ESPN nhận tham số ngày ở dạng YYYYMMDD, không phải ISO. */
function toApiDate(d: Date) {
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
}

function addDays(d: Date, n: number) {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

/**
 * Số ngày CÓ TRẬN hiện mỗi phía quanh hôm nay.
 *
 * Thanh ngày dựng từ lịch thật của giải chứ không phải dải ngày liên
 * tiếp. Bóng đá châu Âu đá theo vòng, giữa hai vòng có thể trống cả
 * tuần; trước đây thanh này hiện cứng bảy ngày mỗi phía nên phần lớn ô
 * bấm vào chỉ nhận lại màn hình rỗng.
 */
const DATE_SPAN = 7;

/** Bề rộng một ô ngày cộng khoảng cách, dùng để canh cuộn về hôm nay. */
const DATE_CHIP_W = 58 + 6;

/** "20260927" -> Date lúc nửa đêm giờ máy. */
function fromApiDate(code: string): Date {
  return new Date(
    Number(code.slice(0, 4)), Number(code.slice(4, 6)) - 1, Number(code.slice(6, 8)),
  );
}

/**
 * Chọn các ngày để hiện trên thanh: lấy từ lịch thật, cắt lấy vài ngày
 * mỗi phía quanh hôm nay.
 *
 * Hôm nay LUÔN có mặt kể cả khi không có trận nào, vì đó là mốc để người
 * dùng định vị mình đang ở đâu, và cũng là chế độ mặc định (không kèm
 * ngày thì ESPN trả về vòng đấu gần nhất).
 */
function pickDays(calendar: string[] | null, todayCode: string): Date[] {
  if (!calendar || calendar.length === 0) return [fromApiDate(todayCode)];
  const before = calendar.filter((d) => d < todayCode).slice(-DATE_SPAN);
  const after = calendar.filter((d) => d > todayCode).slice(0, DATE_SPAN);
  const codes = [...before, todayCode, ...after];
  return codes.map(fromApiDate);
}

/**
 * Gom theo giải, giữ nguyên thứ tự xuất hiện. Nhờ danh sách đã được đẩy
 * trận của đội yêu thích lên trước, giải chứa đội yêu thích tự khắc nằm
 * đầu mà không cần xử lý riêng.
 */
function groupByLeague(list: Match[]): Array<{ code: string; matches: Match[] }> {
  const map = new Map<string, Match[]>();
  for (const m of list) {
    const arr = map.get(m.leagueCode);
    if (arr) arr.push(m);
    else map.set(m.leagueCode, [m]);
  }
  return [...map.entries()].map(([code, matches]) => ({ code, matches }));
}

function fmtDayLabel(iso: string, t: Dict) {
  const d = new Date(iso);
  const today = new Date();
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diffDays = Math.round((startOf(d) - startOf(today)) / 86400000);
  if (diffDays === 0) return t.day.today;
  if (diffDays === 1) return t.day.tomorrow;
  return `${t.day.weekday[d.getDay()]}, ${fmtDate(iso)}`;
}

function TeamRow({
  name, logo, score, won, played, isFav, onToggleFav,
}: {
  name: string; logo?: string; score?: number; won: boolean; played: boolean;
  isFav: boolean; onToggleFav: () => void;
}) {
  return (
    <View style={s.teamRow}>
      <Pressable onPress={onToggleFav} hitSlop={8} style={s.favBtn}>
        <Ionicons name={isFav ? 'star' : 'star-outline'} size={15} color={isFav ? colors.away : colors.textFaint} />
      </Pressable>
      <TeamLogo uri={logo} size={30} />
      <Text
        style={[s.teamName, played && !won && s.teamNameDim]}
        numberOfLines={1}
      >
        {name}
      </Text>
      <Text style={[s.teamScore, played && !won && s.teamScoreDim]}>
        {score === undefined ? '–' : score}
      </Text>
    </View>
  );
}

/**
 * Thẻ trận. Bọc React.memo vì vòng lặp tỉ số trực tiếp chạy lại mỗi 20
 * giây: không có memo thì cả trăm thẻ vẽ lại chỉ vì một trận đổi tỉ số.
 * Để memo có tác dụng, onPress phải nhận trận làm tham số thay vì đóng
 * gói sẵn — nhờ vậy màn hình truyền xuống được một hàm cố định.
 */
const MatchCard = React.memo(function MatchCard({
  m, onPress, showDay, showLeague, t,
}: { m: Match; onPress: (m: Match) => void; showDay?: boolean; showLeague?: boolean; t: Dict }) {
  // Backend Python (Pydantic) gửi tường minh "score": null cho trận chưa
  // đá, khác với bản Node cũ vốn bỏ hẳn trường này khi rỗng. Phải loại cả
  // null lẫn undefined, không chỉ so sánh với undefined.
  const played = m.score !== undefined && m.score !== null;
  const homeWon = played && m.score!.home > m.score!.away;
  const awayWon = played && m.score!.away > m.score!.home;
  const draw = played && m.score!.home === m.score!.away;
  const { isFavorite, toggleFavorite } = useFavorites();

  return (
    <PressScale onPress={() => onPress(m)} style={s.card}>
      <View style={s.cardTop}>
        <View style={{ flex: 1, gap: 3 }}>
          {showLeague && (
            <Text style={s.cardLeague} numberOfLines={1}>
              {t.league[m.leagueCode as keyof typeof t.league] ?? m.leagueCode}
            </Text>
          )}
          <Text style={s.cardDate}>
            {showDay ? fmtDayLabel(m.kickoffUtc, t) : fmtDate(m.kickoffUtc)} · {fmtTime(m.kickoffUtc)}
          </Text>
        </View>
        <StatusBadge m={m} t={t} />
      </View>

      <View style={s.teams}>
        <TeamRow
          name={m.home.name} logo={m.home.logoUrl}
          score={m.score?.home} won={homeWon || draw} played={played}
          isFav={isFavorite(m.home.id)}
          onToggleFav={() => toggleFavorite({ id: m.home.id, name: m.home.name, logoUrl: m.home.logoUrl })}
        />
        <TeamRow
          name={m.away.name} logo={m.away.logoUrl}
          score={m.score?.away} won={awayWon || draw} played={played}
          isFav={isFavorite(m.away.id)}
          onToggleFav={() => toggleFavorite({ id: m.away.id, name: m.away.name, logoUrl: m.away.logoUrl })}
        />
      </View>

      <View style={s.cardFoot}>
        <Text style={s.cardCta}>{t.home.viewStats}</Text>
        <Text style={s.chevron}>›</Text>
      </View>
    </PressScale>
  );
});

/**
 * Dải ngày cuộn ngang, kiểu lịch thi đấu. Hôm nay luôn nằm giữa và được
 * chọn sẵn; chọn ngày khác thì danh sách chuyển hẳn sang lịch ngày đó.
 */
function DateStrip({
  days, value, today, onChange, t,
}: {
  days: Date[]; value: string; today: string;
  onChange: (apiDate: string) => void; t: Dict;
}) {
  // So khớp bằng chính chuỗi YYYYMMDD chứ không tính hiệu số thời gian:
  // new Date('2026-09-26') được hiểu là nửa đêm giờ UTC còn các ngày
  // trong dải là nửa đêm giờ máy, nên ở múi giờ lệch UTC thì hiệu số ra
  // 1,29 ngày và làm tròn sai — đúng lỗi đã gặp: nhãn "Hôm qua" nhảy
  // sang ngày kế trước.
  const now = new Date();
  const yesterdayKey = toApiDate(addDays(now, -1));
  const tomorrowKey = toApiDate(addDays(now, 1));

  const label = (d: Date) => {
    const key = toApiDate(d);
    if (key === today) return t.day.today;
    if (key === tomorrowKey) return t.day.tomorrow;
    if (key === yesterdayKey) return t.day.yesterday;
    return t.day.weekday[d.getDay()]!;
  };

  // Hôm nay nằm giữa dải nên mặc định bị đẩy ra ngoài khung nhìn. Cuộn
  // sẵn về đúng đó ngay khi dựng, không chờ người dùng tự tìm. Vị trí
  // tính theo chỉ số thật của hôm nay trong danh sách, vì số ngày mỗi
  // phía không cố định — lịch giải có thể thiếu ngày ở một bên.
  const ref = useRef<ScrollView>(null);
  const todayIndex = days.findIndex((d) => toApiDate(d) === today);
  useEffect(() => {
    if (todayIndex < 0) return undefined;
    const x = Math.max(0, todayIndex * DATE_CHIP_W - 120);
    const id = setTimeout(() => ref.current?.scrollTo({ x, animated: false }), 0);
    return () => clearTimeout(id);
  }, [todayIndex]);

  return (
    <ScrollView
      ref={ref}
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={s.dateStrip}
    >
      {days.map((d) => {
        const key = toApiDate(d);
        const active = key === value;
        const isToday = key === today;
        return (
          <Pressable
            key={key}
            onPress={() => onChange(key)}
            style={[s.dateChip, isToday && !active && s.dateChipToday, active && s.dateChipActive]}
          >
            <Text style={[s.dateChipTop, active && s.dateChipTopActive]} numberOfLines={1}>
              {label(d)}
            </Text>
            <Text style={[s.dateChipDay, active && s.dateChipDayActive]}>
              {String(d.getDate()).padStart(2, '0')}/{String(d.getMonth() + 1).padStart(2, '0')}
            </Text>
            {/* Chấm đánh dấu hôm nay. Tách riêng khỏi trạng thái "đang
                chọn": chọn ngày khác rồi vẫn phải nhìn ra hôm nay ở đâu. */}
            <View style={[s.dateDot, isToday && s.dateDotToday]} />
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

/**
 * Một dòng trong danh sách phẳng của màn hình chính: hoặc là thẻ trận
 * (được ảo hóa, memo hóa), hoặc là một mẩu giao diện dựng sẵn như tiêu
 * đề mục hay thông báo rỗng.
 */
type Row =
  | { kind: 'node'; key: string; node: React.ReactNode }
  | { kind: 'league'; key: string; code: string; count: number }
  | { kind: 'match'; key: string; m: Match; showDay: boolean; idx: number };

const keyOfRow = (r: Row) => r.key;
const RowGap = () => <View style={{ height: space.md }} />;

export function HomeScreen({
  onOpenMatch,
}: {
  onOpenMatch: (league: LeagueValue, match: Match) => void;
}) {
  const { t } = useI18n();
  const leagueOptions = useLeagueOptions();
  // Mở sẵn một giải chứ không gộp tất cả: gộp gần 40 giải là mấy chục
  // lượt gọi chỉ để vẽ màn hình đầu tiên, và danh sách dài tới mức
  // không ai đọc hết. Người dùng vẫn chọn "Tất cả các giải" được.
  const [filter, setFilter] = useState<HomeFilter>(DEFAULT_LEAGUE);
  const [menuOpen, setMenuOpen] = useState(false);
  const [matches, setMatches] = useState<Match[] | null>(null);
  const [upcoming, setUpcoming] = useState<Match[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [upcomingError, setUpcomingError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery] = useState('');
  const [favOnly, setFavOnly] = useState(false);
  const [liveOnly, setLiveOnly] = useState(false);
  const { favorites, isFavorite } = useFavorites();
  const leagueLogos = useLeagueLogos();
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  const today = useMemo(() => toApiDate(new Date()), []);
  const [date, setDate] = useState(today);
  const isToday = date === today;

  // Lịch thi đấu của giải: dùng để thanh ngày chỉ hiện ngày thật sự có
  // trận. Chưa tải xong thì pickDays trả về mỗi hôm nay, nên thanh ngày
  // không nhảy loạn giữa chừng.
  const [calendar, setCalendar] = useState<string[] | null>(null);
  useEffect(() => {
    let alive = true;
    setCalendar(null);
    void (async () => {
      try {
        const res = await api.calendar(filter);
        if (alive) setCalendar(res.dates);
      } catch {
        // Hỏng thì thanh ngày chỉ còn hôm nay — vẫn dùng được, không
        // cần báo lỗi ra màn hình vì đây là phần phụ trợ.
        if (alive) setCalendar([]);
      }
    })();
    return () => { alive = false; };
  }, [filter]);

  const days = useMemo(() => pickDays(calendar, today), [calendar, today]);

  // Đổi giải mà ngày đang chọn không còn trong lịch giải mới thì kéo về
  // hôm nay, thay vì để người dùng đứng ở một ngày trống.
  useEffect(() => {
    if (!calendar || date === today) return;
    if (!calendar.includes(date)) setDate(today);
  }, [calendar, date, today]);

  // Gộp hai danh sách lại chỉ để vòng lặp trực tiếp biết có nên chạy
  // hay không. Không dùng cho việc hiển thị.
  const watchList = useMemo(
    () => [...(matches ?? []), ...(upcoming ?? [])],
    [matches, upcoming],
  );

  const applyLive = useCallback((updates: Map<string, LiveMatch>) => {
    // mergeLive trả về đúng mảng cũ khi không có gì đổi, nên setState
    // trong trường hợp đó không kéo theo lần vẽ lại nào.
    setMatches((prev) => mergeLive(prev, updates));
    setUpcoming((prev) => mergeLive(prev, updates));
  }, []);

  useLiveScores(filter, watchList, applyLive);

  const load = useCallback(async (lg: HomeFilter, day: string, dayIsToday: boolean) => {
    setError(null); setMatches(null);
    setUpcomingError(null); setUpcoming(null);
    try {
      // LUÔN lọc theo ngày đang chọn, kể cả hôm nay.
      //
      // Trước đây hôm nay là trường hợp riêng: gọi không kèm ngày, và
      // ESPN trả về "vòng đấu gần nhất" — có thể là trận của hai tuần
      // trước. Cộng thêm mục "Sắp diễn ra" nằm trên cùng, mở app ngày
      // 28/09 lại thấy toàn trận 03/10, không có gì nói rằng hôm nay
      // đơn giản là không có trận.
      setMatches((await api.matches(lg, day)).matches);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
    // "Sắp diễn ra" là lịch các vòng tới, chỉ có nghĩa khi đang xem hôm
    // nay. Đang xem một ngày cụ thể thì danh sách của ngày đó là tất cả.
    if (!dayIsToday) {
      setUpcoming([]);
      return;
    }
    try {
      setUpcoming((await api.upcomingMatches(lg)).matches);
    } catch (e) {
      setUpcomingError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => { void load(filter, date, isToday); }, [filter, date, isToday, load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true); await load(filter, date, isToday); setRefreshing(false);
  }, [filter, date, isToday, load]);

  const showLeague = filter === 'ALL';
  const openMatch = useCallback(
    (m: Match) => onOpenMatch(m.leagueCode as LeagueValue, m),
    [onOpenMatch],
  );
  const leagueName = useLeagueName();
  const filterLabel = filter === 'ALL' ? t.league.ALL : leagueName(filter);

  const isFavMatch = useCallback(
    (m: Match) => isFavorite(m.home.id) || isFavorite(m.away.id),
    [isFavorite],
  );

  // Không lọc: trận của đội yêu thích được đẩy lên đầu (giữ nguyên thứ tự
  // giờ đấu trong từng nhóm) để dễ thấy ngay mà không cần bật chế độ lọc.
  const applyFavorites = useCallback((list: Match[]) => {
    if (favOnly) return list.filter(isFavMatch);
    const favs = list.filter(isFavMatch);
    if (favs.length === 0) return list;
    const rest = list.filter((m) => !isFavMatch(m));
    return [...favs, ...rest];
  }, [favOnly, isFavMatch]);

  const applyAll = useCallback((list: Match[]) => {
    const byQuery = list.filter((m) => matchesQuery(m, query));
    const byLive = liveOnly ? byQuery.filter((m) => isLiveStatus(m.status)) : byQuery;
    return applyFavorites(byLive);
  }, [query, liveOnly, applyFavorites]);

  const filteredUpcoming = useMemo(
    () => (upcoming ? applyAll(upcoming) : upcoming),
    [upcoming, applyAll],
  );
  const filteredMatches = useMemo(
    () => (matches ? applyAll(matches) : matches),
    [matches, applyAll],
  );
  const liveCount = useMemo(
    () => (matches ? matches.filter((m) => isLiveStatus(m.status)).length : 0),
    [matches],
  );
  const searching = query.trim().length > 0;
  const filtering = searching || favOnly || liveOnly;
  const noFilterResults = filtering
    && !!matches && !!upcoming
    && filteredMatches!.length === 0 && filteredUpcoming!.length === 0;
  const noFavoritesYet = favOnly && favorites.length === 0;

  /**
   * Trộn tiêu đề mục, khung chờ, thông báo rỗng và thẻ trận thành một
   * danh sách phẳng để FlatList ảo hóa được. Trước đây tất cả nằm trong
   * ScrollView nên gần trăm thẻ đều bị dựng thật ngay từ đầu.
   */
  const rows = useMemo<Row[]>(() => {
    const out: Row[] = [];
    const node = (key: string, n: React.ReactNode) => out.push({ kind: 'node', key, node: n });

    // Gom theo giải khi đang xem tất cả các giải: xếp xen kẽ mười hai
    // giải vào một danh sách phẳng thì không đọc nổi. Xem đúng một giải
    // thì tiêu đề nhóm chỉ lặp lại vô ích nên bỏ.
    const pushMatches = (list: Match[], prefix: string, showDay: boolean) => {
      if (!showLeague) {
        list.forEach((m, i) => out.push({
          kind: 'match', key: `${prefix}-${m.id}`, m, showDay, idx: i,
        }));
        return;
      }
      for (const g of groupByLeague(list)) {
        out.push({
          kind: 'league', key: `${prefix}-lg-${g.code}`, code: g.code, count: g.matches.length,
        });
        g.matches.forEach((m, i) => out.push({
          kind: 'match', key: `${prefix}-${m.id}`, m, showDay, idx: i,
        }));
      }
    };

    // ---- Mục 1: trận của đúng ngày đang chọn, luôn đứng đầu.
    //
    // Thứ tự này quan trọng. Trước đây "Sắp diễn ra" nằm trên cùng nên
    // mở app ngày 28/09 là thấy ngay loạt trận 03/10, còn việc hôm nay
    // không có trận thì không chỗ nào nói.
    const dayLabel = isToday
      ? t.day.today
      : fmtDayLabel(`${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}T12:00:00Z`, t);
    const hasDayMatches = !!filteredMatches && filteredMatches.length > 0;
    // Hiện tiêu đề ngày cả khi ngày đó trống, để dòng "hôm nay không có
    // trận nào" có chỗ bám vào thay vì trôi lơ lửng giữa trang.
    const showDayHead = !noFavoritesYet && !noFilterResults;

    if (showDayHead) {
      node('day-head', (
        <View style={s.sectionHead}>
          <Text style={s.sectionTitle}>{dayLabel}</Text>
          {hasDayMatches && (
            <Text style={s.sectionCount}>{t.home.matchCount(filteredMatches!.length)}</Text>
          )}
        </View>
      ));
    }
    if (error) node('err', <ErrorBox message={error} onRetry={() => void load(filter, date, isToday)} />);
    if (!error && matches === null) node('m-skel', <MatchListSkeleton count={2} />);
    if (hasDayMatches) pushMatches(filteredMatches!, 'd', false);

    // Không có trận ở ngày đang chọn thì nói thẳng ra, thay vì để trống
    // rồi đẩy mục khác lên cho người dùng hiểu nhầm.
    if (!error && matches !== null && !hasDayMatches && !filtering) {
      node('no-day', <Empty text={isToday ? t.home.noMatchesToday : t.home.emptyLeague} />);
    }

    // ---- Các thông báo của bộ lọc
    if (noFavoritesYet) node('no-fav', <Empty text={t.home.noFavoritesYet} />);
    if (!noFavoritesYet && searching && noFilterResults) {
      node('no-query', <Empty text={t.home.noSearchResults(query.trim())} />);
    }
    if (!noFavoritesYet && !searching && favOnly && !liveOnly && noFilterResults) {
      node('no-fav-match', <Empty text={t.home.noFavMatches} />);
    }
    if (!noFavoritesYet && liveOnly && noFilterResults) {
      node('no-live', <Empty text={t.home.noLiveMatches} />);
    }

    // ---- Mục 2: các vòng đấu sắp tới, chỉ hiện khi đang ở hôm nay.
    if (isToday && upcoming === null && !error) {
      node('upc-skel', (
        <View>
          <View style={s.sectionHead}>
            <Text style={s.sectionTitle}>{t.home.upcoming}</Text>
          </View>
          <MatchListSkeleton count={2} />
        </View>
      ));
    }
    if (filteredUpcoming && filteredUpcoming.length > 0) {
      node('upc-head', (
        <View style={s.sectionHead}>
          <Text style={s.sectionTitle}>{t.home.upcoming}</Text>
          <Text style={s.sectionCount}>{t.home.matchCount(filteredUpcoming.length)}</Text>
        </View>
      ));
      pushMatches(filteredUpcoming, 'u', true);
    }
    if (upcomingError) {
      node('upc-err', <Text style={s.upcomingErr}>{t.home.upcomingError(upcomingError)}</Text>);
    }

    if ((filteredMatches?.length ?? 0) > 0 || (filteredUpcoming?.length ?? 0) > 0) {
      node('foot', <Text style={s.foot}>{t.home.pullToRefresh}</Text>);
    }
    return out;
  }, [
    upcoming, matches, filteredUpcoming, filteredMatches, error, upcomingError,
    noFavoritesYet, noFilterResults, searching, favOnly, filtering, query, t, load, filter,
  ]);

  const renderRow = useCallback(({ item }: { item: Row }) => {
    if (item.kind === 'node') return <>{item.node}</>;
    if (item.kind === 'league') {
      return (
        <View style={s.leagueHead}>
          {leagueLogos[item.code]
            ? <TeamLogo uri={leagueLogos[item.code]} size={20} />
            : <View style={s.leagueDot} />}
          <Text style={s.leagueName} numberOfLines={1}>
            {t.league[item.code as keyof typeof t.league] ?? item.code}
          </Text>
          <Text style={s.leagueCount}>{item.count}</Text>
        </View>
      );
    }
    return (
      <Reveal index={item.idx}>
        {/* Nhãn giải trên thẻ chỉ cần khi danh sách phẳng; đã có tiêu đề
            nhóm thì lặp lại thành thừa. */}
        <MatchCard m={item.m} showDay={item.showDay} t={t} onPress={openMatch} />
      </Reveal>
    );
  }, [t, openMatch, leagueLogos]);

  return (
    <View style={s.root}>
      <HeaderGlow />
      <View style={s.header}>
        <View style={s.headRow}>
          <HamburgerButton onPress={() => setMenuOpen(true)} />
          <View style={{ flex: 1 }}>
            {/* Chữ hiệu thay cho icon quả bóng chung chung + tiêu đề
                dịch: tên sản phẩm giữ nguyên ở mọi ngôn ngữ mới nhận ra
                được, phần mô tả bên dưới vẫn dịch bình thường. */}
            <BrandLockup size={32} />
            <Text style={s.sub}>{t.home.sub}</Text>
          </View>
          {/* Nút góp ý nằm ngay cạnh nút ngôn ngữ trên thanh tiêu đề —
              chỗ dễ thấy nhất, không phải mở menu mới tìm ra. */}
          <FeedbackButton onPress={() => setFeedbackOpen(true)} />
          <LangSwitch />
        </View>
        <View style={s.controlsRow}>
          <PressScale onPress={() => setMenuOpen(true)} style={s.filterBar}>
            <Text style={s.filterText} numberOfLines={1}>{filterLabel}</Text>
            <Text style={s.filterChevron}>▾</Text>
          </PressScale>

          <PressScale
            onPress={() => setFavOnly((v) => !v)}
            style={[s.favToggle, favOnly && s.favToggleActive]}
          >
            <Ionicons name={favOnly ? 'star' : 'star-outline'} size={15} color={favOnly ? '#00230F' : colors.away} />
          </PressScale>

          {/* Lọc chỉ trận đang đá. Con số bên cạnh cho biết có đáng bấm
              hay không, khỏi phải bấm vào rồi thấy trống. */}
          <PressScale
            onPress={() => setLiveOnly((v) => !v)}
            style={[s.liveToggle, liveOnly && s.liveToggleActive]}
          >
            <View style={[s.liveDot, liveOnly && s.liveDotActive]} />
            <Text style={[s.liveText, liveOnly && s.liveTextActive]}>
              {liveCount > 0 ? liveCount : t.home.liveOnly}
            </Text>
          </PressScale>

          <View style={s.searchBox}>
            <Ionicons name="search" size={14} color={colors.textFaint} />
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder={t.home.searchPlaceholder}
              placeholderTextColor={colors.textFaint}
              style={s.searchInput}
              autoCorrect={false}
              autoCapitalize="none"
              returnKeyType="search"
            />
            {query.length > 0 && (
              <Pressable onPress={() => setQuery('')} hitSlop={8}>
                <Ionicons name="close-circle" size={15} color={colors.textFaint} />
              </Pressable>
            )}
          </View>
        </View>

        <DateStrip days={days} value={date} today={today} onChange={setDate} t={t} />
      </View>

      <FeedbackSheet visible={feedbackOpen} onClose={() => setFeedbackOpen(false)} />

      <LeagueMenu
        visible={menuOpen}
        onClose={() => setMenuOpen(false)}
        options={leagueOptions}
        value={filter}
        onChange={setFilter}
        showAll
      />

      <FlatList
        data={rows}
        keyExtractor={keyOfRow}
        renderItem={renderRow}
        ItemSeparatorComponent={RowGap}
        contentContainerStyle={s.list}
        showsVerticalScrollIndicator={false}
        // Mặc định FlatList dựng sẵn hơn hai chục màn hình nội dung; ở
        // chế độ "tất cả các giải" có gần trăm trận nên phải siết lại,
        // nếu không lần mở đầu tiên đứng hình một nhịp thấy rõ.
        initialNumToRender={8}
        maxToRenderPerBatch={8}
        updateCellsBatchingPeriod={60}
        windowSize={7}
        removeClippedSubviews={false}
        keyboardShouldPersistTaps="handled"
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
        }
      />
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, position: 'relative', backgroundColor: colors.bg },
  header: { paddingHorizontal: space.lg, paddingTop: space.md, paddingBottom: space.sm },
  headRow: { flexDirection: 'row', alignItems: 'flex-start', gap: space.sm },
  sub: { ...font.small, color: colors.textDim, marginTop: 5 },

  controlsRow: {
    flexDirection: 'row', alignItems: 'center', gap: space.sm,
    marginTop: space.md,
  },
  filterBar: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    alignSelf: 'flex-start',
    paddingHorizontal: space.md, paddingVertical: 8,
    borderRadius: radius.pill,
    backgroundColor: colors.accentSoft,
    borderWidth: 1, borderColor: colors.accentLine,
    flexShrink: 0,
  },
  filterText: { ...font.small, color: colors.accent, fontWeight: '800' },
  filterChevron: { color: colors.accent, fontSize: 11, marginTop: 1 },

  favToggle: {
    width: 34, height: 34,
    alignItems: 'center', justifyContent: 'center',
    borderRadius: radius.pill,
    backgroundColor: colors.card,
    borderWidth: 1, borderColor: colors.hairline,
    flexShrink: 0,
  },
  favToggleActive: { backgroundColor: colors.away, borderColor: colors.away },

  liveToggle: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 10, height: 34,
    borderRadius: radius.pill,
    backgroundColor: colors.card,
    borderWidth: 1, borderColor: colors.hairline,
    flexShrink: 0,
  },
  liveToggleActive: { backgroundColor: colors.liveSoft, borderColor: colors.live },
  liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.textFaint },
  liveDotActive: { backgroundColor: colors.live },
  liveText: { ...font.tiny, color: colors.textDim, fontWeight: '800' },
  liveTextActive: { color: colors.live },

  dateStrip: { gap: 6, paddingTop: space.md, paddingRight: space.lg },
  dateChip: {
    minWidth: 58, alignItems: 'center',
    paddingHorizontal: 10, paddingVertical: 6,
    borderRadius: radius.md,
    backgroundColor: colors.card,
    borderWidth: 1, borderColor: colors.hairline,
  },
  dateChipActive: { backgroundColor: colors.accentSoft, borderColor: colors.accentLine },
  // Hôm nay nhưng KHÔNG phải ngày đang chọn: chỉ viền nhạt, để không
  // tranh chấp với ô đang chọn.
  dateChipToday: { borderColor: colors.borderBright },
  dateDot: { width: 4, height: 4, borderRadius: 2, marginTop: 3, backgroundColor: 'transparent' },
  dateDotToday: { backgroundColor: colors.accent },
  dateChipTop: { ...font.tiny, color: colors.textDim, fontSize: 10 },
  dateChipTopActive: { color: colors.accent, fontWeight: '800' },
  dateChipDay: { ...font.small, color: colors.textSoft, fontWeight: '700', marginTop: 1 },
  dateChipDayActive: { color: colors.text },

  leagueHead: {
    flexDirection: 'row', alignItems: 'center', gap: space.sm,
    paddingTop: space.xs,
  },
  leagueDot: { width: 3, height: 13, borderRadius: 2, backgroundColor: colors.accent },
  leagueName: {
    ...font.label, color: colors.textSoft, flex: 1,
    textTransform: 'uppercase', letterSpacing: 0.6,
  },
  leagueCount: { ...font.tiny, color: colors.textFaint },

  searchBox: {
    flex: 1,
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: space.md, paddingVertical: 8,
    borderRadius: radius.pill,
    backgroundColor: colors.card,
    borderWidth: 1, borderColor: colors.hairline,
    minWidth: 0,
  },
  searchInput: {
    flex: 1,
    ...font.small,
    color: colors.text,
    padding: 0,
    minWidth: 0,
  },

  // Khoảng cách giữa các dòng do ItemSeparatorComponent lo, không dùng
  // gap ở đây nữa: FlatList dựng mỗi dòng trong một ô riêng nên gap của
  // container không còn áp dụng đều như hồi dùng ScrollView.
  list: { padding: space.lg, paddingTop: space.xs, paddingBottom: space.xxl },

  card: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    overflow: 'hidden',
    ...shadow.card,
  },
  cardPressed: { backgroundColor: colors.cardPressed, borderColor: colors.border },
  cardTop: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: space.lg, paddingTop: space.md, paddingBottom: space.sm,
  },
  cardDate: { ...font.tiny, color: colors.textFaint },
  cardLeague: { ...font.tiny, color: colors.accent, fontWeight: '800', fontSize: 10 },

  teams: { paddingHorizontal: space.lg, paddingBottom: space.md, gap: space.md },
  teamRow: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  favBtn: { padding: 2, marginRight: -4 },
  teamName: { ...font.h2, color: colors.text, flex: 1, fontSize: 15.5 },
  teamNameDim: { color: colors.textDim, fontWeight: '600' },
  teamScore: { ...font.score, color: colors.text, minWidth: 30, textAlign: 'right' },
  teamScoreDim: { color: colors.textFaint },

  cardFoot: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: space.lg, paddingVertical: space.md,
    borderTopWidth: 1, borderTopColor: colors.hairline,
    backgroundColor: 'rgba(255,255,255,0.016)',
  },
  cardCta: { ...font.small, color: colors.accent },
  chevron: { color: colors.accent, fontSize: 22, marginTop: -3, fontWeight: '700' },

  foot: { ...font.tiny, color: colors.textFaint, textAlign: 'center', marginTop: space.sm },

  sectionHead: {
    flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between',
    marginTop: space.xs, marginBottom: space.xs,
  },
  sectionTitle: { ...font.h2, color: colors.text, fontSize: 15.5 },
  sectionCount: { ...font.tiny, color: colors.textFaint },
  upcomingErr: { ...font.tiny, color: colors.textFaint, textAlign: 'center' },
});
