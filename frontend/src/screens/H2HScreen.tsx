/**
 * Kết quả đối đầu giữa hai đội.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { HeadToHeadResponse, StatCardDto, Team, Window } from '../types';
import { api } from '../api';
import { colors, font, radius, shadow, space } from '../theme';
import {
  Card, CompareRow, Empty, ErrorBox, HeaderGlow, Reveal, Segmented, TeamLogo,
} from '../components/ui';
import { StatListSkeleton } from '../components/skeleton';
import { useI18n } from '../i18n';

export function H2HScreen({
  league, teamA, teamB, onBack,
}: {
  league: string;
  teamA: Team;
  teamB: Team;
  onBack: () => void;
}) {
  const { t } = useI18n();
  const WINDOWS: ReadonlyArray<{ value: Window; label: string }> = [
    { value: 5, label: t.window.n5 },
    { value: 10, label: t.window.n10 },
    { value: 20, label: t.window.n20 },
  ];
  const [window, setWindow] = useState<Window>(10);
  const [data, setData] = useState<HeadToHeadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (w: Window) => {
    setError(null); setData(null);
    try {
      setData(await api.headToHead(
        league, teamA.refs[0]!.externalId, teamB.refs[0]!.externalId, w,
      ));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [league, teamA, teamB]);

  useEffect(() => { void load(window); }, [window, load]);

  const pairs: Array<{ key: StatCardDto['key']; label: string; a: number; b: number }> =
    data
      ? data.teamACards.map((c, i) => ({
          key: c.key,
          label: t.stat[c.key],
          a: c.stats.avgFull,
          b: data.teamBCards[i]?.stats.avgFull ?? 0,
        }))
      : [];

  return (
    <View style={s.root}>
      <HeaderGlow />
      <View style={s.nav}>
        <Pressable onPress={onBack} hitSlop={12} style={({ pressed }) => pressed && { opacity: 0.6 }}>
          <Text style={s.back}>‹  {t.matchDetail.back}</Text>
        </Pressable>
      </View>

      <View style={s.hero}>
        <View style={s.heroTeam}>
          <TeamLogo uri={teamA.logoUrl} size={50} />
          <Text style={s.heroName} numberOfLines={2}>{teamA.name}</Text>
          <View style={[s.tag, { backgroundColor: colors.homeSoft }]}>
            <Text style={[s.tagText, { color: colors.home }]}>{t.h2h.teamA}</Text>
          </View>
        </View>
        <Text style={s.vs}>VS</Text>
        <View style={s.heroTeam}>
          <TeamLogo uri={teamB.logoUrl} size={50} />
          <Text style={s.heroName} numberOfLines={2}>{teamB.name}</Text>
          <View style={[s.tag, { backgroundColor: colors.awaySoft }]}>
            <Text style={[s.tagText, { color: colors.away }]}>{t.h2h.teamB}</Text>
          </View>
        </View>
      </View>

      <View style={s.segBox}>
        <Segmented options={WINDOWS} value={window} onChange={setWindow} />
      </View>

      <ScrollView contentContainerStyle={s.body} showsVerticalScrollIndicator={false}>
        {error && <ErrorBox message={error} onRetry={() => void load(window)} />}
        {!error && !data && <StatListSkeleton count={1} />}

        {data && data.matchesUsed === 0 && (
          <Empty text={t.h2h.empty} />
        )}

        {data && data.matchesUsed > 0 && (
          <>
            <Text style={s.meta}>{t.h2h.basedOn(data.matchesUsed)}</Text>
            <Reveal>
              <Card style={{ gap: space.lg }}>
                {pairs.map((p) => (
                  <CompareRow
                    key={p.key}
                    label={p.label}
                    home={Number(p.a.toFixed(2))}
                    away={Number(p.b.toFixed(2))}
                  />
                ))}
              </Card>
            </Reveal>
            <Text style={s.note}>{t.h2h.legend(teamA.name, teamB.name)}</Text>
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

  hero: {
    flexDirection: 'row', alignItems: 'flex-start',
    marginHorizontal: space.lg,
    backgroundColor: colors.card, borderRadius: radius.xl,
    borderWidth: 1, borderColor: colors.hairline,
    paddingVertical: space.lg, paddingHorizontal: space.md,
    ...shadow.card,
  },
  heroTeam: { flex: 1, alignItems: 'center', gap: 7 },
  heroName: { ...font.h2, color: colors.text, textAlign: 'center', fontSize: 13, lineHeight: 17 },
  tag: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.pill },
  tagText: { fontSize: 8.5, fontWeight: '800', letterSpacing: 0.7 },
  vs: { ...font.label, color: colors.textFaint, alignSelf: 'center' },

  segBox: { paddingHorizontal: space.lg, paddingTop: space.md, paddingBottom: space.sm },
  body: { padding: space.lg, paddingTop: space.sm, gap: space.md, paddingBottom: space.xxl },
  meta: { ...font.tiny, color: colors.textFaint, textAlign: 'center' },
  note: { ...font.tiny, color: colors.textFaint, textAlign: 'center', lineHeight: 16 },
});
