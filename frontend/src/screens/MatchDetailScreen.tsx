/**
 * Chi tiết một trận, tách số liệu theo hiệp.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Animated, Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type {
  BettingInsights, HeadToHeadMatchesResponse, LineupPlayer, LiveMatch, Match,
  MatchDetailResponse, MatchEvent, MatchInsightsResponse, MatchOdds, TeamMatchStats, Window,
} from '../types';
import { api } from '../api';
import { colors, font, radius, shadow, space } from '../theme';
import {
  Card, CompareRow, ErrorBox, HeaderGlow, NoData, Pill, PressScale, Segmented, TabBar,
  TeamLogo,
} from '../components/ui';
import { isLiveStatus, mergeLive, useLiveScores } from '../useLiveScores';
import { MatchRowListSkeleton, StatListSkeleton } from '../components/skeleton';
import { MatchHistoryList } from '../components/matchHistory';
import { MatchChat } from '../components/matchChat';
import { buildRows, LineupPitch } from '../components/pitch';
import { useI18n } from '../i18n';
import { useSettings } from '../settings';
import { useLeagueLogos } from '../leagueLogos';
import { CAN_SHARE_IMAGE, ShareSheet } from '../share/ShareSheet';
import type { ShareCardData } from '../share/drawCard';

type Period = 'first' | 'second' | 'full';
type Tab = 'this' | 'timeline' | 'lineups' | 'history';

/** Nội dung tab "Trận này": so sánh đúng trận vừa bấm, tách theo hiệp. */
function ThisMatchTab({
  match, data, error, onRetry, t,
}: {
  match: Match; data: MatchDetailResponse | null; error: string | null;
  onRetry: () => void; t: ReturnType<typeof useI18n>['t'];
}) {
  const [period, setPeriod] = useState<Period>('full');
  const PERIODS = [
    { value: 'first' as const, label: t.period.first },
    { value: 'second' as const, label: t.period.second },
    { value: 'full' as const, label: t.period.full },
  ];

  const split = data?.split;
  const pick = <T,>(p: { first: T | null; second: T | null; full: T }): T | null =>
    period === 'full' ? p.full : period === 'first' ? p.first : p.second;

  const goals = split ? pick(split.goals) : null;
  const cards = split ? pick(split.cards) : null;
  const corners = split ? pick(split.corners) : null;
  const periodName = period === 'full' ? t.period.full : period === 'first' ? t.period.first : t.period.second;

  return (
    <View style={{ gap: space.md }}>
      {error && <ErrorBox message={error} onRetry={onRetry} />}
      {!error && !data && <StatListSkeleton count={1} />}

      {data && (
        <>
          <Segmented options={PERIODS} value={period} onChange={setPeriod} />

          <Card style={s.statCard}>
            <View style={s.legend}>
              <View style={s.legendItem}>
                <View style={[s.legendDot, { backgroundColor: colors.home }]} />
                <Text style={s.legendText} numberOfLines={1}>{match.home.shortName ?? match.home.name}</Text>
              </View>
              <Text style={s.legendPeriod} numberOfLines={1}>
                {t.matchDetail.statsOf(periodName)}
              </Text>
              <View style={[s.legendItem, { justifyContent: 'flex-end' }]}>
                <Text style={s.legendText} numberOfLines={1}>{match.away.shortName ?? match.away.name}</Text>
                <View style={[s.legendDot, { backgroundColor: colors.away }]} />
              </View>
            </View>

            <View style={s.divider} />

            {goals
              ? <CompareRow label={t.stat.goalsFor} home={goals.home} away={goals.away} />
              : <NoData />}

            {cards ? (
              <>
                <CompareRow label={t.stat.yellowCards} home={cards.home.yellow} away={cards.away.yellow} />
                <CompareRow label={t.stat.redCards} home={cards.home.red} away={cards.away.red} />
              </>
            ) : <NoData />}

            {corners ? (
              <CompareRow label={t.stat.corners} home={corners.home} away={corners.away} />
            ) : (
              <View>
                <Text style={s.cornerLabel}>{t.stat.corners}</Text>
                <NoData hint={t.matchDetail.cornerHint} />
              </View>
            )}
          </Card>

          {data.teamStats && (
            <MatchStatsCard home={data.teamStats.home} away={data.teamStats.away} t={t} />
          )}

          <Text style={s.meta}>{t.matchDetail.basedOnEvents(data.eventCount)}</Text>
        </>
      )}
    </View>
  );
}

/**
 * Thẻ "Chỉ số trước trận" cho trận CHƯA đá.
 *
 * Chủ đích thiết kế: ba con số lớn trả lời ngay ba câu hỏi hay gặp nhất
 * (trận này nhiều bàn không, nhiều góc không, nhiều thẻ không), rồi mới
 * tới phần tỉ lệ chi tiết cho người muốn đào sâu. Không nhồi thêm chỉ
 * số nào nữa — thêm nữa là thành bảng số liệu, mất luôn tác dụng liếc
 * một cái là hiểu.
 *
 * Mọi con số đều là TỔNG hai đội trong mỗi trận, không phải riêng đội
 * đang xét, vì các vạch Trên/Dưới đều tính theo tổng.
 *
 * Gập được, và trạng thái gập lưu lại giữa các trận: đây là thẻ dài
 * nhất trang, người chỉ muốn xem đội hình hoặc lịch sử đối đầu không
 * phải cuộn qua nó mỗi lần mở một trận mới.
 */
function PctRow({
  label, home, away, homeName, awayName,
}: {
  label: string; home: number; away: number; homeName: string; awayName: string;
}) {
  const cell = (v: number, name: string, tone: string) => (
    <View style={s.insCell}>
      <Text style={[s.insPct, { color: tone }]}>{Math.round(v)}%</Text>
      <View style={s.insTrack}>
        <View style={[s.insFill, { width: `${Math.max(2, Math.min(100, v))}%`, backgroundColor: tone }]} />
      </View>
      <Text style={s.insTeam} numberOfLines={1}>{name}</Text>
    </View>
  );
  return (
    <View style={s.insRow}>
      <Text style={s.insLabel} numberOfLines={2}>{label}</Text>
      <View style={s.insCells}>
        {cell(home, homeName, colors.home)}
        {cell(away, awayName, colors.away)}
      </View>
    </View>
  );
}

function InsightsCard({
  insights, odds, match, t,
}: {
  insights: BettingInsights; odds?: MatchOdds | null; match: Match;
  t: ReturnType<typeof useI18n>['t'];
}) {
  // Vạch thị trường là phần DUY NHẤT trong thẻ này đến từ nhà cái; mọi
  // con số còn lại đều tự tính từ phong độ nên luôn hiện. Xem ghi chú ở
  // src/settings.tsx về lý do mặc định tắt.
  const { showOdds, insightsOpen, setInsightsOpen } = useSettings();
  const { home, away } = insights;
  if (home.matches === 0 && away.matches === 0) {
    return (
      <Card style={s.statCard}>
        <Text style={s.blockTitle}>{t.insights.title}</Text>
        <View style={s.divider} />
        <NoData hint={t.insights.notEnough} />
      </Card>
    );
  }

  const hName = match.home.shortName ?? match.home.name;
  const aName = match.away.shortName ?? match.away.name;
  const fh = insights.firstHalfGoalPct;

  const big = (value: number, label: string, tone: string) => (
    <View key={label} style={s.insBig}>
      <Text style={[s.insBigValue, { color: tone }]}>{value.toFixed(1)}</Text>
      <Text style={s.insBigLabel} numberOfLines={2}>{label}</Text>
    </View>
  );

  return (
    <Card style={s.statCard}>
      <Pressable
        onPress={() => setInsightsOpen(!insightsOpen)}
        hitSlop={6}
        accessibilityRole="button"
        accessibilityState={{ expanded: insightsOpen }}
        style={({ pressed }) => [s.lnHead, pressed && { opacity: 0.6 }]}
      >
        <Ionicons name="analytics" size={16} color={colors.accent} />
        <Text style={s.blockTitle}>{t.insights.title}</Text>
        <Text style={s.insWindow}>{t.insights.basedOn(insights.window)}</Text>
        <Ionicons
          name={insightsOpen ? 'chevron-up' : 'chevron-down'}
          size={16} color={colors.textFaint}
        />
      </Pressable>

      {!insightsOpen ? null : (
        <>
        <View style={s.divider} />

        <Text style={s.insSection}>{t.insights.expected}</Text>
        <View style={s.insBigRow}>
          {big(insights.expectedGoals, t.matchTable.goals, colors.text)}
          {big(insights.expectedCorners, t.stat.corners, colors.accent)}
          {big(insights.expectedCards, t.insights.cards, colors.card_yellow)}
        </View>

        {/* Vạch thị trường đặt ngay dưới con số kỳ vọng để so sánh được
            bằng mắt: vạch 2.5 mà thống kê kỳ vọng 3.1 thì đã nói lên điều
            gì đó. Chỉ hiện con số, không có đường dẫn sang nhà cái. */}
        {showOdds && !!odds && (odds.overUnder != null || odds.spread != null) && (
          <>
            <Text style={s.insSection}>{t.insights.marketLine}</Text>
            <View style={s.oddsRow}>
              {odds.overUnder != null && (
                <View style={s.oddsChip}>
                  <Text style={s.oddsLabel}>{t.insights.ouLine}</Text>
                  <Text style={s.oddsValue}>{odds.overUnder}</Text>
                </View>
              )}
              {odds.spread != null && (
                <View style={s.oddsChip}>
                  <Text style={s.oddsLabel}>{t.insights.handicap}</Text>
                  <Text style={s.oddsValue}>
                    {odds.spread > 0 ? `+${odds.spread}` : odds.spread}
                  </Text>
                </View>
              )}
              {/* Cố tình KHÔNG hiện tên nhà cái mà ESPN trả về. Ghi nguồn
                  chung là đủ, còn nêu đích danh một hãng cá cược trên màn
                  hình thì vừa là quảng cáo không chủ ý vừa dễ bị soi khi
                  duyệt store. */}
              <Text style={s.oddsProvider}>ESPN</Text>
            </View>
        </>
      )}

      {fh != null && (
        <>
          <Text style={s.insSection}>{t.insights.halfSplit}</Text>
          <View style={s.halfTrack}>
            <View style={[s.halfFirst, { width: `${fh}%` }]}>
              <Text style={s.halfText} numberOfLines={1}>{Math.round(fh)}%</Text>
            </View>
            <View style={[s.halfSecond, { width: `${100 - fh}%` }]}>
              <Text style={s.halfText} numberOfLines={1}>{Math.round(100 - fh)}%</Text>
            </View>
          </View>
          <View style={s.halfLegend}>
            <Text style={s.insBigLabel}>{t.period.first}</Text>
            <Text style={s.insBigLabel}>{t.period.second}</Text>
          </View>
        </>
      )}

      <View style={s.divider} />
      <PctRow
        label={t.insights.over25} home={home.over25GoalsPct} away={away.over25GoalsPct}
        homeName={hName} awayName={aName}
      />
      <PctRow
        label={t.insights.over95Corners} home={home.over95CornersPct} away={away.over95CornersPct}
        homeName={hName} awayName={aName}
      />
      <PctRow
        label={t.insights.over35Cards} home={home.over35CardsPct} away={away.over35CardsPct}
        homeName={hName} awayName={aName}
      />
      <PctRow
        label={t.insights.btts} home={home.bttsPct} away={away.bttsPct}
        homeName={hName} awayName={aName}
      />

      <Text style={s.insDisclaimer}>{t.insights.disclaimer}</Text>
      </>
      )}
    </Card>
  );
}

/**
 * Bảng thống kê cả trận. Khác với phần tách theo hiệp ở trên: nguồn dữ
 * liệu chỉ có tổng cả trận cho mấy chỉ số này nên không tách được.
 *
 * Thanh tỉ lệ vẽ theo phần của mỗi đội trong tổng hai đội. Hai đội cùng
 * bằng 0 thì bỏ qua dòng đó hẳn — vẽ một thanh rỗng chỉ tốn chỗ.
 */
function StatBar({
  label, home, away, unit,
}: { label: string; home?: number | null; away?: number | null; unit?: string }) {
  const h = home ?? 0;
  const a = away ?? 0;
  if (home == null && away == null) return null;
  if (h === 0 && a === 0) return null;
  const total = h + a;
  const hPct = total > 0 ? (h / total) * 100 : 50;
  const fmt = (v: number) =>
    (Number.isInteger(v) ? String(v) : v.toFixed(1)) + (unit ?? '');
  return (
    <View style={s.statRow}>
      <Text style={[s.statVal, { textAlign: 'left' }]}>{fmt(h)}</Text>
      <View style={s.statMid}>
        <Text style={s.statLabel} numberOfLines={1}>{label}</Text>
        <View style={s.statTrack}>
          <View style={[s.statFillHome, { width: `${hPct}%` }]} />
          <View style={[s.statFillAway, { width: `${100 - hPct}%` }]} />
        </View>
      </View>
      <Text style={[s.statVal, { textAlign: 'right' }]}>{fmt(a)}</Text>
    </View>
  );
}

function MatchStatsCard({
  home, away, t,
}: {
  home: TeamMatchStats; away: TeamMatchStats;
  t: ReturnType<typeof useI18n>['t'];
}) {
  const rows: Array<[string, number | null | undefined, number | null | undefined, string?]> = [
    [t.matchDetail.possession, home.possessionPct, away.possessionPct, '%'],
    [t.matchDetail.shots, home.shots, away.shots],
    [t.matchDetail.shotsOnTarget, home.shotsOnTarget, away.shotsOnTarget],
    [t.stat.corners, home.corners, away.corners],
    [t.matchDetail.saves, home.saves, away.saves],
    [t.matchDetail.fouls, home.fouls, away.fouls],
    [t.matchDetail.offsides, home.offsides, away.offsides],
    [t.matchDetail.tackles, home.tackles, away.tackles],
    [t.matchDetail.interceptions, home.interceptions, away.interceptions],
    [t.matchDetail.passAccuracy, home.passPct, away.passPct, '%'],
  ];
  // Lọc TRƯỚC khi dựng phần tử. Dựng rồi mới filter(Boolean) thì không
  // loại được gì: map trả về các phần tử React, chúng luôn truthy dù
  // StatBar sẽ trả null lúc vẽ. Hệ quả là thẻ vẫn hiện với mỗi cái tiêu
  // đề và bên dưới trống trơn — trận chưa đá nào cũng dính.
  const usable = rows.filter(([, h, a]) => {
    if (h == null && a == null) return false;
    return (h ?? 0) !== 0 || (a ?? 0) !== 0;
  });
  if (usable.length === 0) return null;
  const bars = usable.map(([label, h, a, unit]) => (
    <StatBar key={label} label={label} home={h} away={a} unit={unit} />
  ));
  return (
    <Card style={s.statCard}>
      <Text style={s.blockTitle}>{t.matchDetail.statsTitle}</Text>
      <View style={s.divider} />
      {bars}
    </Card>
  );
}

/** Biểu tượng cho từng loại diễn biến. */
function eventIcon(type: MatchEvent['type']): { name: IconName; color: string } {
  switch (type) {
    case 'goal':
    case 'penalty_goal':
      return { name: 'football', color: colors.text };
    case 'own_goal':
      return { name: 'football-outline', color: colors.live };
    case 'penalty_missed':
      return { name: 'close-circle-outline', color: colors.textDim };
    case 'yellow_card':
      return { name: 'square', color: colors.card_yellow };
    case 'red_card':
    case 'second_yellow':
      return { name: 'square', color: colors.card_red };
    case 'substitution':
      return { name: 'swap-horizontal', color: colors.accent };
    default:
      return { name: 'ellipse-outline', color: colors.textDim };
  }
}

type IconName = React.ComponentProps<typeof Ionicons>['name'];

/**
 * Dòng thời gian của trận. Sự kiện của đội nhà lùi về trái, đội khách
 * dạt sang phải, cột phút chạy ở giữa — nhìn là biết ngay bên nào đang
 * làm gì mà không phải đọc tên đội.
 */
function TimelineTab({
  data, error, onRetry, t,
}: {
  data: MatchDetailResponse | null; error: string | null;
  onRetry: () => void; t: ReturnType<typeof useI18n>['t'];
}) {
  if (error) return <ErrorBox message={error} onRetry={onRetry} />;
  if (!data) return <StatListSkeleton count={1} />;
  if (data.events.length === 0) return <NoData hint={t.matchDetail.timelineEmpty} />;

  const label = (e: MatchEvent) => {
    switch (e.type) {
      case 'goal': return t.matchDetail.event.goal;
      case 'own_goal': return t.matchDetail.event.ownGoal;
      case 'penalty_goal': return t.matchDetail.event.penaltyGoal;
      case 'penalty_missed': return t.matchDetail.event.penaltyMissed;
      case 'yellow_card': return t.stat.yellowCards;
      case 'red_card': return t.stat.redCards;
      case 'second_yellow': return t.matchDetail.event.secondYellow;
      case 'substitution': return t.matchDetail.event.substitution;
      default: return '';
    }
  };

  return (
    <Card style={s.statCard}>
      {data.events.map((e, i) => {
        const icon = eventIcon(e.type);
        const away = e.side === 'away';
        const who = e.type === 'substitution' && e.playerName && e.secondPlayerName
          ? t.matchDetail.substitutionOf(e.playerName, e.secondPlayerName)
          : e.playerName;
        return (
          <View key={`${e.minute}-${e.type}-${i}`} style={[s.evRow, away && s.evRowAway]}>
            <View style={[s.evSide, away && s.evSideAway]}>
              <Text style={[s.evPlayer, away && { textAlign: 'right' }]} numberOfLines={2}>
                {who || label(e)}
              </Text>
              {!!who && (
                <Text style={[s.evKind, away && { textAlign: 'right' }]} numberOfLines={1}>
                  {label(e)}
                </Text>
              )}
            </View>
            <View style={s.evMid}>
              <Ionicons name={icon.name} size={14} color={icon.color} />
              <Text style={s.evMinute}>
                {e.minute}{e.extraMinute ? `+${e.extraMinute}` : ''}&apos;
              </Text>
            </View>
            <View style={s.evSide} />
          </View>
        );
      })}
    </Card>
  );
}

function PlayerRow({ p }: { p: LineupPlayer }) {
  return (
    <View style={s.lnRow}>
      <Text style={s.lnJersey}>{p.jersey ?? '–'}</Text>
      <Text style={s.lnName} numberOfLines={1}>{p.name}</Text>
      {/* Dự bị có vào sân thì cũng có điểm; không vào sân thì không có
          gì để chấm nên để trống thay vì cho một con số vô nghĩa. */}
      {p.rating != null && <Text style={s.lnRating}>{p.rating.toFixed(1)}</Text>}
      {!!p.position && <Text style={s.lnPos}>{p.position}</Text>}
    </View>
  );
}

/** Đội hình ra sân hai đội, kèm sơ đồ và băng ghế dự bị. */
function LineupsTab({
  data, error, onRetry, t,
}: {
  data: MatchDetailResponse | null; error: string | null;
  onRetry: () => void; t: ReturnType<typeof useI18n>['t'];
}) {
  if (error) return <ErrorBox message={error} onRetry={onRetry} />;
  if (!data) return <StatListSkeleton count={1} />;
  if (data.lineups.length === 0) return <NoData hint={t.matchDetail.lineupsEmpty} />;

  return (
    <View style={{ gap: space.md }}>
      {data.lineups.map((l) => (
        <Card key={l.side} style={s.statCard}>
          <View style={s.lnHead}>
            <View style={[s.legendDot, { backgroundColor: l.side === 'home' ? colors.home : colors.away }]} />
            <Text style={s.blockTitle} numberOfLines={1}>{l.teamName}</Text>
            {!!l.formation && <Text style={s.lnFormation}>{l.formation}</Text>}
          </View>
          <View style={s.divider} />
          {/* Sân cỏ khi dựng được; không dựng được (thiếu sơ đồ, số
              người không khớp) thì lùi về danh sách tên như cũ. */}
          {buildRows(l) ? (
            <>
              <LineupPitch lineup={l} />
              {l.starters.some((p) => p.rating != null) && (
                <Text style={s.pitchNote}>{t.matchDetail.ratingNote}</Text>
              )}
            </>
          ) : (
            l.starters.map((p, i) => <PlayerRow key={`s${i}`} p={p} />)
          )}
          {l.bench.length > 0 && (
            <>
              <Text style={s.lnBenchLabel}>{t.matchDetail.bench}</Text>
              {l.bench.map((p, i) => <PlayerRow key={`b${i}`} p={p} />)}
            </>
          )}
        </Card>
      ))}
    </View>
  );
}

const WINDOWS: ReadonlyArray<{ value: Window; label: string }> = [
  { value: 5, label: '5' }, { value: 10, label: '10' }, { value: 20, label: '20' },
];

/** Nội dung tab "Đối đầu": chỉ những lần hai đội này thực sự gặp nhau. */
function HistoryTab({
  league, match, t, onOpenMatch,
}: {
  league: string; match: Match; t: ReturnType<typeof useI18n>['t'];
  onOpenMatch?: (m: Match) => void;
}) {
  const [window_, setWindow] = useState<Window>(10);
  const [data, setData] = useState<HeadToHeadMatchesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (w: Window) => {
    setError(null); setData(null);
    try {
      setData(await api.h2hMatches(
        league, match.home.refs[0]!.externalId, match.away.refs[0]!.externalId, w,
      ));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [league, match]);

  useEffect(() => { void load(window_); }, [window_, load]);

  return (
    <View style={{ gap: space.md }}>
      <Segmented options={WINDOWS} value={window_} onChange={setWindow} />

      {error && <ErrorBox message={error} onRetry={() => void load(window_)} />}
      {!error && !data && <MatchRowListSkeleton />}

      {data && (
        <>
          <Text style={s.meta}>{t.matchTable.metTimes(data.matches.length)}</Text>
          <MatchHistoryList
            key={window_} rows={data.matches} t={t}
            league={league} onOpenMatch={onOpenMatch} currentMatchId={match.id}
          />
        </>
      )}
    </View>
  );
}

export function MatchDetailScreen({
  league, match, onBack, onOpenTeam, onOpenMatch,
}: {
  league: string;
  match: Match;
  onBack: () => void;
  onOpenTeam: (teamExternalId: string, teamName: string) => void;
  /** Mở một trận khác từ tab Đối đầu, chồng lên màn hình hiện tại. */
  onOpenMatch?: (m: Match) => void;
}) {
  const { t, lang } = useI18n();
  const [tab, setTab] = useState<Tab>('this');
  const [data, setData] = useState<MatchDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Phần soi kèo + AI tải riêng: nó phải kéo phong độ 10 trận gần nhất
  // của cả hai đội (đo được 6 giây khi cache nguội), còn mọi thứ khác
  // trên trang đã sẵn sàng sau chưa tới một giây. Gộp chung thì cả trang
  // ngồi chờ phần chậm nhất.
  const [extra, setExtra] = useState<MatchInsightsResponse | null>(null);
  const [shareOpen, setShareOpen] = useState(false);
  const leagueLogos = useLeagueLogos();

  // Trận được truyền vào từ màn hình trước là ảnh chụp tại lúc bấm. Giữ
  // một bản riêng để vòng lặp trực tiếp cập nhật tỉ số và phút thi đấu
  // trên bảng điểm mà không phải tải lại cả trang chi tiết — phần thống
  // kê và nhận định AI bên dưới vốn không đổi trong lúc trận đang đá.
  const [liveMatch, setLiveMatch] = useState<Match>(match);
  useEffect(() => { setLiveMatch(match); }, [match]);
  const watchList = useMemo(() => [liveMatch], [liveMatch]);
  const applyLive = useCallback((updates: Map<string, LiveMatch>) => {
    setLiveMatch((prev) => mergeLive([prev], updates)![0]!);
  }, []);
  useLiveScores(league, watchList, applyLive);

  /**
   * Gom dữ liệu cho ảnh chia sẻ.
   *
   * Trận đã đá: ba ô là phạt góc, thẻ vàng, thẻ đỏ — những con số người
   * xem hay khoe nhất. Trận chưa đá: dùng con số kỳ vọng từ bảng soi
   * kèo, kèm ghi chú đây là số liệu tham khảo.
   */
  const shareData = useMemo<ShareCardData>(() => {
    const split = data?.split;
    const played = liveMatch.score !== null && liveMatch.score !== undefined;
    const ins = extra?.insights;

    const stats = played && split
      ? [
        { label: t.stat.corners, value: String(Math.round(split.corners.full.home + split.corners.full.away)) },
        { label: t.stat.yellowCards, value: String(split.cards.full.home.yellow + split.cards.full.away.yellow) },
        { label: t.stat.redCards, value: String(split.cards.full.home.red + split.cards.full.away.red) },
      ]
      : ins
        ? [
          { label: t.matchTable.goals, value: ins.expectedGoals.toFixed(1) },
          { label: t.stat.corners, value: ins.expectedCorners.toFixed(1) },
          { label: t.insights.cards, value: ins.expectedCards.toFixed(1) },
        ]
        : [];

    return {
      leagueName: t.league[league as keyof typeof t.league] ?? league,
      leagueLogoUrl: leagueLogos[league],
      kickoffUtc: liveMatch.kickoffUtc,
      status: liveMatch.status,
      homeName: liveMatch.home.shortName ?? liveMatch.home.name,
      homeLogoUrl: liveMatch.home.logoUrl,
      awayName: liveMatch.away.shortName ?? liveMatch.away.name,
      awayLogoUrl: liveMatch.away.logoUrl,
      homeScore: liveMatch.score?.home,
      awayScore: liveMatch.score?.away,
      htHome: split?.goals.first?.home,
      htAway: split?.goals.first?.away,
      stats,
      note: !played && ins ? `${t.share.expected} · ${t.insights.basedOn(ins.window)}` : undefined,
    };
  }, [data, extra, liveMatch, league, t, leagueLogos]);

  const load = useCallback(async () => {
    setError(null); setData(null);
    try {
      setData(await api.matchDetail(league, match.refs[0]!.externalId, lang));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [league, match, lang]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    // Trận đã đá xong không có gì ở đây (không soi kèo, không nhận định
    // AI) nên khỏi gọi.
    if (match.status !== 'scheduled') { setExtra(null); return undefined; }
    let alive = true;
    setExtra(null);
    void (async () => {
      try {
        const res = await api.matchInsights(league, match.refs[0]!.externalId, lang);
        if (alive) setExtra(res);
      } catch {
        // Im lặng: đây là phần bổ sung, hỏng thì trang vẫn dùng được
        // bình thường, hiện lỗi đỏ ở đây chỉ làm người dùng hoang mang.
        if (alive) setExtra({});
      }
    })();
    return () => { alive = false; };
  }, [league, match, lang]);

  const fade = useRef(new Animated.Value(1)).current;
  const switchTab = (next: Tab) => {
    if (next === tab) return;
    Animated.sequence([
      Animated.timing(fade, { toValue: 0, duration: 110, useNativeDriver: true }),
    ]).start(() => {
      setTab(next);
      Animated.timing(fade, { toValue: 1, duration: 220, useNativeDriver: true }).start();
    });
  };

  const TABS: ReadonlyArray<{ value: Tab; label: string }> = [
    { value: 'this', label: t.matchDetail.tabThis },
    { value: 'timeline', label: t.matchDetail.tabTimeline },
    { value: 'lineups', label: t.matchDetail.tabLineups },
    { value: 'history', label: t.matchDetail.tabHistory },
  ];

  return (
    <View style={s.root}>
      <HeaderGlow />
      <View style={s.nav}>
        <Pressable onPress={onBack} hitSlop={12} style={({ pressed }) => pressed && { opacity: 0.6 }}>
          <Text style={s.back}>‹  {t.matchDetail.back}</Text>
        </Pressable>
        {CAN_SHARE_IMAGE && (
          <Pressable
            onPress={() => setShareOpen(true)}
            hitSlop={10}
            style={({ pressed }) => [s.shareBtn, pressed && { opacity: 0.6 }]}
          >
            <Ionicons name="share-social-outline" size={16} color={colors.accent} />
            <Text style={s.shareText}>{t.share.button}</Text>
          </Pressable>
        )}
      </View>

      <ShareSheet
        visible={shareOpen}
        onClose={() => setShareOpen(false)}
        data={shareData}
        fileBase={`${liveMatch.home.shortName ?? 'home'}-${liveMatch.away.shortName ?? 'away'}`
          .toLowerCase().replace(/[^a-z0-9-]+/g, '-')}
      />

      <ScrollView contentContainerStyle={s.body} showsVerticalScrollIndicator={false}>
        {/* Bảng tỷ số */}
        <View style={s.hero}>
          <Pressable
            style={s.heroTeam}
            onPress={() => onOpenTeam(match.home.refs[0]!.externalId, match.home.name)}
          >
            <TeamLogo uri={match.home.logoUrl} size={58} />
            <Text style={s.heroName} numberOfLines={2}>{match.home.name}</Text>
            <View style={[s.tag, { backgroundColor: colors.homeSoft }]}>
              <Text style={[s.tagText, { color: colors.home }]}>{t.matchDetail.home}</Text>
            </View>
          </Pressable>

          <View style={s.heroMid}>
            <Text style={s.heroScore}>
              {liveMatch.score ? `${liveMatch.score.home} - ${liveMatch.score.away}` : 'vs'}
            </Text>
            {isLiveStatus(liveMatch.status) ? (
              <Pill text={liveMatch.clock || t.status.live} tone="live" />
            ) : (
              <Text style={s.heroDate}>
                {new Date(liveMatch.kickoffUtc).toLocaleDateString()}
              </Text>
            )}
          </View>

          <Pressable
            style={s.heroTeam}
            onPress={() => onOpenTeam(match.away.refs[0]!.externalId, match.away.name)}
          >
            <TeamLogo uri={match.away.logoUrl} size={58} />
            <Text style={s.heroName} numberOfLines={2}>{match.away.name}</Text>
            <View style={[s.tag, { backgroundColor: colors.awaySoft }]}>
              <Text style={[s.tagText, { color: colors.away }]}>{t.matchDetail.away}</Text>
            </View>
          </Pressable>
        </View>

        {/* Trận chưa đá: đặt phần soi kèo lên ngay dưới bảng điểm, trước
            cả nhận định AI — đây mới là thứ người xem mở trang này để tìm,
            còn AI có thể vắng mặt khi hết hạn mức gọi. */}
        {match.status === 'scheduled' && (
          extra === null
            ? <StatListSkeleton count={1} />
            : extra.insights
              ? <InsightsCard insights={extra.insights} odds={extra.odds} match={liveMatch} t={t} />
              : null
        )}

        {extra?.aiPrediction && (
          <Card style={s.predictCard}>
            <View style={s.aiHead}>
              <Ionicons name="sparkles" size={15} color={colors.accent2} />
              <Text style={s.aiLabel}>{t.matchDetail.aiPrediction}</Text>
            </View>
            <View style={s.predictScoreRow}>
              <Text style={s.predictScore}>
                {extra!.aiPrediction.homeScore} - {extra!.aiPrediction.awayScore}
              </Text>
            </View>
            <View style={s.predictStatsRow}>
              <View style={s.predictStat}>
                <Text style={s.predictStatValue}>{extra!.aiPrediction.corners}</Text>
                <Text style={s.predictStatLabel}>{t.stat.corners}</Text>
              </View>
              <View style={s.predictStatDivider} />
              <View style={s.predictStat}>
                <Text style={s.predictStatValue}>{extra!.aiPrediction.yellowCards}</Text>
                <Text style={s.predictStatLabel}>{t.stat.yellowCards}</Text>
              </View>
            </View>
            <Text style={s.predictNote}>{extra!.aiPrediction.note}</Text>
            <Text style={s.predictDisclaimer}>{t.matchDetail.aiPredictionDisclaimer}</Text>
          </Card>
        )}

        {data?.referee && (
          <View style={s.refereeCard}>
            <View style={s.refereeRow}>
              <Ionicons name="shield-checkmark-outline" size={16} color={colors.textDim} />
              <Text style={s.refereeName}>{t.matchDetail.referee}: {data.referee.name}</Text>
            </View>
            {data.referee.matchesTracked > 0 ? (
              <Text style={s.refereeStat}>
                {t.matchDetail.refereeAvg(
                  data.referee.avgYellowCards ?? 0,
                  data.referee.avgRedCards ?? 0,
                  data.referee.matchesTracked,
                )}
              </Text>
            ) : null}
            {data.referee.matchesTracked > 0 && data.referee.matchesTracked < 3 && (
              <Text style={s.refereeHint}>{t.matchDetail.refereeLowData(data.referee.matchesTracked)}</Text>
            )}
          </View>
        )}

        {extra?.aiAnalysis && (
          <Card style={s.aiCard}>
            <View style={s.aiHead}>
              <Ionicons name="sparkles" size={15} color={colors.accent2} />
              <Text style={s.aiLabel}>{t.matchDetail.aiAnalysis}</Text>
            </View>
            <Text style={s.aiText}>{extra!.aiAnalysis}</Text>
          </Card>
        )}

        {/* Khung hỏi đáp đặt sau phần nhận định: lúc này người xem đã
            đọc xong các con số, câu hỏi nảy ra ở đây chứ không phải lúc
            vừa mở trang. Chỉ hiện với trận chưa đá — trận đã đá xong
            thì số liệu thật nằm ngay bên dưới, không cần hỏi ước lượng. */}
        {match.status === 'scheduled' && (
          <MatchChat
            league={league}
            matchExternalId={match.refs[0]!.externalId}
            onOpenTab={(target) => setTab(target === 'lineups' ? 'lineups' : 'history')}
          />
        )}

        {data?.highlightUrl && (
          <PressScale
            onPress={() => Linking.openURL(data.highlightUrl!)}
            style={s.highlightBtn}
          >
            <Ionicons name="play-circle" size={18} color={colors.accent} />
            <Text style={s.highlightText}>{t.matchDetail.watchHighlights}</Text>
          </PressScale>
        )}

        <Text style={s.hint}>{t.matchDetail.hint}</Text>

        <TabBar options={TABS} value={tab} onChange={switchTab} />

        <Animated.View style={{ opacity: fade }}>
          {tab === 'this' && (
            <ThisMatchTab match={match} data={data} error={error} onRetry={() => void load()} t={t} />
          )}
          {tab === 'timeline' && (
            <TimelineTab data={data} error={error} onRetry={() => void load()} t={t} />
          )}
          {tab === 'lineups' && (
            <LineupsTab data={data} error={error} onRetry={() => void load()} t={t} />
          )}
          {tab === 'history' && (
            <HistoryTab league={league} match={match} t={t} onOpenMatch={onOpenMatch} />
          )}
        </Animated.View>
      </ScrollView>
    </View>
  );
}


const s = StyleSheet.create({
  root: { flex: 1, position: 'relative', backgroundColor: colors.bg },
  nav: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: space.lg, paddingTop: space.md, paddingBottom: space.sm,
  },
  shareBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: space.md, paddingVertical: 7,
    borderRadius: radius.pill,
    backgroundColor: colors.accentSoft,
    borderWidth: 1, borderColor: colors.accentLine,
  },
  shareText: { ...font.small, color: colors.accent, fontWeight: '800' },
  back: { ...font.h2, color: colors.accent },

  body: { padding: space.lg, paddingTop: 0, gap: space.md, paddingBottom: space.xxl },

  hero: {
    flexDirection: 'row', alignItems: 'flex-start',
    backgroundColor: colors.card, borderRadius: radius.xl,
    borderWidth: 1, borderColor: colors.hairline,
    paddingVertical: space.xl, paddingHorizontal: space.md,
    ...shadow.card,
  },
  heroTeam: { flex: 1, alignItems: 'center', gap: space.sm },
  heroName: { ...font.h2, color: colors.text, textAlign: 'center', fontSize: 13.5, lineHeight: 18 },
  tag: { paddingHorizontal: 8, paddingVertical: 3.5, borderRadius: radius.pill },
  tagText: { fontSize: 8.5, fontWeight: '800', letterSpacing: 0.7 },

  heroMid: { alignItems: 'center', justifyContent: 'center', paddingTop: space.lg, gap: 5 },
  heroScore: { ...font.display, fontSize: 32, color: colors.text },
  heroDate: { ...font.tiny, color: colors.textFaint, fontSize: 10.5 },

  hint: { ...font.tiny, color: colors.textFaint, textAlign: 'center' },

  aiCard: { gap: 8 },
  aiHead: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  aiLabel: { ...font.label, color: colors.accent2, fontSize: 10 },
  aiText: { ...font.body, color: colors.textSoft, lineHeight: 20 },

  predictCard: { gap: 10, alignItems: 'center' },
  predictScoreRow: { alignItems: 'center' },
  predictScore: { ...font.display, fontSize: 34, color: colors.text },
  predictStatsRow: {
    flexDirection: 'row', alignItems: 'center', gap: space.lg,
    paddingTop: space.xs,
  },
  predictStat: { alignItems: 'center', gap: 2 },
  predictStatValue: { ...font.h2, fontSize: 18, color: colors.text },
  predictStatLabel: { ...font.tiny, color: colors.textFaint },
  predictStatDivider: { width: 1, height: 26, backgroundColor: colors.hairline },
  predictNote: {
    ...font.small, color: colors.textSoft, textAlign: 'center', lineHeight: 18,
  },
  predictDisclaimer: { ...font.tiny, color: colors.textFaint, fontStyle: 'italic', fontSize: 10 },

  refereeCard: {
    alignSelf: 'center', alignItems: 'center', gap: 3,
    paddingHorizontal: space.md,
  },
  refereeRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  refereeName: { ...font.small, color: colors.textSoft, fontWeight: '700' },
  refereeStat: { ...font.tiny, color: colors.textFaint },
  refereeHint: { ...font.tiny, color: colors.textFaint, fontStyle: 'italic' },

  highlightBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7,
    alignSelf: 'center',
    paddingHorizontal: space.lg, paddingVertical: 10,
    borderRadius: radius.pill,
    backgroundColor: colors.accentSoft,
    borderWidth: 1, borderColor: colors.accentLine,
  },
  highlightText: { ...font.small, color: colors.accent, fontWeight: '800' },

  statCard: { gap: space.lg },
  legend: { flexDirection: 'row', alignItems: 'center' },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6, flex: 1 },
  legendDot: { width: 8, height: 8, borderRadius: 4 },
  legendText: { ...font.tiny, color: colors.textSoft },
  // flexShrink cao và không cho xuống dòng: ở bề ngang iPhone 14 nhãn
  // này từng ngắt thành hai dòng và đẩy cả hàng cao lên.
  legendPeriod: {
    ...font.label, color: colors.textFaint,
    flex: 1.4, flexShrink: 2, textAlign: 'center', fontSize: 9.5,
  },
  divider: { height: 1, backgroundColor: colors.hairline, marginTop: -space.xs },

  cornerLabel: { ...font.tiny, color: colors.textDim, textAlign: 'center', marginBottom: 6 },
  blockTitle: { ...font.h2, color: colors.text, fontSize: 14, flex: 1 },

  // Thống kê cả trận: hai số hai bên, thanh tỉ lệ ở giữa.
  statRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, paddingVertical: 7 },
  // Đủ rộng cho chuỗi dài nhất là phần trăm một chữ số thập phân
  // ("56.8%"); hẹp hơn thì dấu % bị đẩy xuống dòng.
  statVal: { ...font.small, color: colors.text, fontWeight: '800', width: 52 },
  statMid: { flex: 1, gap: 4 },
  statLabel: { ...font.tiny, color: colors.textDim, textAlign: 'center' },
  statTrack: {
    flexDirection: 'row', height: 5, borderRadius: 3, overflow: 'hidden',
    backgroundColor: 'rgba(255,255,255,0.05)',
  },
  statFillHome: { backgroundColor: colors.home },
  statFillAway: { backgroundColor: colors.away },

  // Dòng thời gian: đội nhà bám trái, đội khách bám phải, phút ở giữa.
  evRow: {
    flexDirection: 'row', alignItems: 'center', gap: space.sm,
    paddingVertical: 8,
    borderTopWidth: 1, borderTopColor: colors.hairline,
  },
  evRowAway: { flexDirection: 'row-reverse' },
  evSide: { flex: 1, minWidth: 0 },
  evSideAway: { alignItems: 'flex-end' },
  evPlayer: { ...font.small, color: colors.text, fontWeight: '700' },
  evKind: { ...font.tiny, color: colors.textDim, marginTop: 1 },
  evMid: { alignItems: 'center', width: 46, gap: 2 },
  evMinute: { ...font.tiny, color: colors.textFaint, fontWeight: '800' },

  // Đội hình
  lnHead: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  lnFormation: {
    ...font.tiny, color: colors.accent, fontWeight: '800',
    backgroundColor: colors.accentSoft,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.sm,
  },
  lnRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, paddingVertical: 5 },
  lnJersey: {
    ...font.tiny, color: colors.textFaint, width: 20, textAlign: 'center', fontWeight: '800',
  },
  lnName: { ...font.small, color: colors.textSoft, flex: 1, minWidth: 0 },
  lnPos: { ...font.tiny, color: colors.textFaint },
  lnRating: {
    ...font.small, color: colors.text, fontWeight: '800',
    minWidth: 26, textAlign: 'right',
  },
  pitchNote: {
    ...font.tiny, color: colors.textFaint, fontSize: 10,
    marginTop: 8, lineHeight: 14, fontStyle: 'italic',
  },
  lnBenchLabel: {
    ...font.label, color: colors.textFaint,
    marginTop: space.md, marginBottom: 2,
  },

  // Thẻ chỉ số trước trận
  insWindow: { ...font.tiny, color: colors.textFaint },
  insSection: { ...font.label, color: colors.textFaint, marginTop: space.sm, marginBottom: 6 },
  insBigRow: { flexDirection: 'row', gap: space.sm },
  insBig: {
    flex: 1, alignItems: 'center', gap: 2,
    paddingVertical: space.sm,
    backgroundColor: 'rgba(255,255,255,0.035)',
    borderRadius: radius.md,
  },
  insBigValue: { ...font.score, fontSize: 22 },
  insBigLabel: { ...font.tiny, color: colors.textDim, textAlign: 'center' },

  // Dải phân bố bàn thắng theo hiệp: một thanh, hai màu, cộng lại 100%.
  halfTrack: { flexDirection: 'row', height: 24, borderRadius: radius.sm, overflow: 'hidden' },
  halfFirst: { backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center' },
  halfSecond: { backgroundColor: colors.accent2, alignItems: 'center', justifyContent: 'center' },
  halfText: { ...font.tiny, color: '#FFFFFF', fontWeight: '800' },
  halfLegend: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },

  insRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, paddingVertical: 8 },
  insLabel: { ...font.tiny, color: colors.textSoft, flex: 1, minWidth: 0 },
  insCells: { flexDirection: 'row', gap: space.sm, width: 170 },
  insCell: { flex: 1, gap: 3 },
  insPct: { ...font.small, fontWeight: '800' },
  insTrack: {
    height: 4, borderRadius: 2, overflow: 'hidden',
    backgroundColor: 'rgba(255,255,255,0.06)',
  },
  insFill: { height: 4, borderRadius: 2 },
  insTeam: { ...font.tiny, color: colors.textFaint, fontSize: 9.5 },
  oddsRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  oddsChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 10, paddingVertical: 6,
    borderRadius: radius.md,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1, borderColor: colors.hairline,
  },
  oddsLabel: { ...font.tiny, color: colors.textDim },
  oddsValue: { ...font.small, color: colors.text, fontWeight: '800' },
  oddsProvider: { ...font.tiny, color: colors.textFaint, flex: 1, textAlign: 'right' },

  insDisclaimer: {
    ...font.tiny, color: colors.textFaint, fontStyle: 'italic',
    marginTop: space.md, textAlign: 'center',
  },

  meta: { ...font.tiny, color: colors.textFaint, textAlign: 'center' },
});
