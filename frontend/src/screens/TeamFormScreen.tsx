/**
 * Phong độ một đội qua 5, 10 hoặc 20 trận gần nhất.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { Match, MatchPoint, StatCardDto, TeamFormResponse, Window } from '../types';
import { api } from '../api';
import { colors, font, radius, space } from '../theme';
import {
  Card, ErrorBox, HeaderGlow, MetricBar, Reveal, Segmented, TrendBars,
} from '../components/ui';
import { MatchHistoryList } from '../components/matchHistory';
import { MatchRowListSkeleton, StatListSkeleton } from '../components/skeleton';
import { useI18n } from '../i18n';
import type { Dict } from '../i18n/translations';

type InnerTab = 'form' | 'recent';

function useWindowOptions(t: Dict): ReadonlyArray<{ value: Window; label: string }> {
  return [
    { value: 5, label: t.window.n5 },
    { value: 10, label: t.window.n10 },
    { value: 20, label: t.window.n20 },
  ];
}

const TONE: Record<StatCardDto['key'], string> = {
  goalsFor: colors.accent,
  goalsAgainst: colors.home,
  corners: colors.purple,
  yellowCards: colors.card_yellow,
  redCards: colors.card_red,
};

/** Dải kết quả gần đây: thắng, hòa, thua. */
function ResultStrip({ series, t }: { series: MatchPoint[]; t: Dict }) {
  const items = [...series].slice(0, 10).reverse();
  return (
    <View style={s.strip}>
      {items.map((p, i) => {
        const win = p.scored > p.conceded;
        const draw = p.scored === p.conceded;
        const bg = win ? colors.accent : draw ? colors.textFaint : colors.card_red;
        const ch = win ? t.teamForm.resultWin : draw ? t.teamForm.resultDraw : t.teamForm.resultLoss;
        return (
          <View key={i} style={[s.stripItem, { backgroundColor: bg }]}>
            <Text style={s.stripText}>{ch}</Text>
          </View>
        );
      })}
    </View>
  );
}

function StatBlock({ card, series, t }: { card: StatCardDto; series: MatchPoint[]; t: Dict }) {
  const { stats } = card;
  const tone = TONE[card.key];
  // Nhãn tiếng Việt từ backend chỉ dùng để dự phòng, giao diện luôn ưu tiên
  // bản dịch theo key để đúng ngôn ngữ đang chọn.
  const label = t.stat[card.key];
  const max = Math.max(stats.avgFull, stats.avgFirst ?? 0, stats.avgSecond ?? 0, 0.5);

  const rows: Array<{ label: string; value: number | null }> = [
    { label: t.period.first, value: stats.avgFirst },
    { label: t.period.second, value: stats.avgSecond },
    { label: t.period.full, value: stats.avgFull },
  ];

  const trend = [...series].slice(0, 8).reverse().map((p) => ({
    value: p.values[card.key],
    label: p.opponentShort,
  }));

  return (
    <Card style={s.card}>
      <View style={s.cardHead}>
        <View style={{ flex: 1 }}>
          <Text style={s.cardTitle}>{label}</Text>
          <Text style={s.cardCaption}>{t.teamForm.perMatch}</Text>
        </View>
        <Text style={[s.headline, { color: tone }]}>{stats.avgFull.toFixed(2)}</Text>
      </View>

      <View style={s.rows}>
        {rows.map((r) => (
          <View key={r.label} style={s.row}>
            <Text style={s.rowLabel}>{r.label}</Text>
            {r.value === null ? (
              <Text style={s.rowNoData}>{t.teamForm.noHalfData}</Text>
            ) : (
              <>
                <View style={{ flex: 1 }}>
                  <MetricBar value={r.value} max={max} tone={tone} />
                </View>
                <Text style={s.rowValue}>{r.value.toFixed(2)}</Text>
              </>
            )}
          </View>
        ))}
      </View>

      {trend.length > 1 && (
        <>
          <View style={s.sep} />
          <Text style={s.trendTitle}>{t.teamForm.trendTitle}</Text>
          <TrendBars data={trend} tone={tone} />
        </>
      )}
    </Card>
  );
}

export function TeamFormScreen({
  league, teamExternalId, teamName, onBack, onOpenMatch,
}: {
  league: string;
  teamExternalId: string;
  teamName: string;
  onBack: () => void;
  /** Bấm một trận trong danh sách "Trận gần đây" để mở chi tiết trận đó. */
  onOpenMatch?: (m: Match) => void;
}) {
  const { t } = useI18n();
  const WINDOWS = useWindowOptions(t);
  const [window, setWindow] = useState<Window>(10);
  const [data, setData] = useState<TeamFormResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [innerTab, setInnerTab] = useState<InnerTab>('form');

  const load = useCallback(async (w: Window) => {
    setError(null); setData(null);
    try {
      setData(await api.teamForm(league, teamExternalId, w));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [league, teamExternalId]);

  useEffect(() => { void load(window); }, [window, load]);

  const fade = useRef(new Animated.Value(1)).current;
  const switchInnerTab = (next: InnerTab) => {
    if (next === innerTab) return;
    Animated.timing(fade, { toValue: 0, duration: 110, useNativeDriver: true }).start(() => {
      setInnerTab(next);
      Animated.timing(fade, { toValue: 1, duration: 220, useNativeDriver: true }).start();
    });
  };

  const INNER_TABS: ReadonlyArray<{ value: InnerTab; label: string }> = [
    { value: 'form', label: t.teamForm.tabForm },
    { value: 'recent', label: t.teamForm.tabRecent },
  ];

  return (
    <View style={s.root}>
      <HeaderGlow />
      <View style={s.nav}>
        <Pressable onPress={onBack} hitSlop={12} style={({ pressed }) => pressed && { opacity: 0.6 }}>
          <Text style={s.back}>‹  {t.matchDetail.back}</Text>
        </Pressable>
      </View>

      <View style={s.head}>
        <Text style={s.team} numberOfLines={1}>{data?.teamName ?? teamName}</Text>
        {data && <ResultStrip series={data.series} t={t} />}
      </View>

      <View style={s.segBox}>
        <Segmented options={WINDOWS} value={window} onChange={setWindow} />
      </View>

      <ScrollView contentContainerStyle={s.body} showsVerticalScrollIndicator={false}>
        {error && <ErrorBox message={error} onRetry={() => void load(window)} />}
        {!error && !data && (innerTab === 'form' ? <StatListSkeleton /> : <MatchRowListSkeleton />)}
        {data && (
          <>
            <Segmented options={INNER_TABS} value={innerTab} onChange={switchInnerTab} />

            <Animated.View style={{ opacity: fade, gap: space.md }}>
              {innerTab === 'form' ? (
                <>
                  <Text style={s.meta}>{t.teamForm.basedOn(data.matchesUsed)}</Text>
                  {data.cards.map((c, i) => (
                    <Reveal key={c.key} index={i}>
                      <StatBlock card={c} series={data.series} t={t} />
                    </Reveal>
                  ))}
                </>
              ) : (
                <>
                  <Text style={s.meta}>{t.teamForm.basedOn(data.rows.length)}</Text>
                  <MatchHistoryList
                    key={window} rows={data.rows} t={t} focusTeamId={data.teamId}
                    league={league} onOpenMatch={onOpenMatch}
                  />
                </>
              )}
            </Animated.View>
          </>
        )}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, position: 'relative', backgroundColor: colors.bg },
  nav: { paddingHorizontal: space.lg, paddingTop: space.md, paddingBottom: space.sm },
  back: { ...font.h2, color: colors.accent },

  head: { paddingHorizontal: space.lg, paddingBottom: space.md, gap: space.md },
  team: { ...font.display, fontSize: 26, color: colors.text },

  strip: { flexDirection: 'row', gap: 5 },
  stripItem: { width: 20, height: 20, borderRadius: 6, alignItems: 'center', justifyContent: 'center' },
  stripText: { fontSize: 10, fontWeight: '800', color: '#00230F' },

  segBox: { paddingHorizontal: space.lg, paddingBottom: space.sm },
  body: { padding: space.lg, paddingTop: space.sm, gap: space.md, paddingBottom: space.xxl },
  meta: { ...font.tiny, color: colors.textFaint, textAlign: 'center' },

  card: { gap: space.md },
  cardHead: { flexDirection: 'row', alignItems: 'center' },
  cardTitle: { ...font.h2, color: colors.text, fontSize: 15 },
  cardCaption: { ...font.tiny, color: colors.textFaint, marginTop: 1 },
  headline: { ...font.stat, fontSize: 27 },

  rows: { gap: space.sm },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  rowLabel: { ...font.tiny, color: colors.textDim, width: 52 },
  rowValue: { ...font.h2, color: colors.text, width: 42, textAlign: 'right' },
  rowNoData: { ...font.tiny, color: colors.textFaint, fontStyle: 'italic', flex: 1 },

  sep: { height: 1, backgroundColor: colors.hairline },
  trendTitle: { ...font.tiny, color: colors.textFaint, marginBottom: -space.xs },
});
