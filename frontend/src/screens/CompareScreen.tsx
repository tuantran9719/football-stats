/**
 * Chọn hai đội bất kỳ để so sánh đối đầu.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { Team } from '../types';
import { api } from '../api';
import { colors, font, radius, shadow, space } from '../theme';
import {
  ChipRow, ErrorBox, HeaderGlow, LangSwitch, PressScale, Reveal, TeamLogo,
} from '../components/ui';
import { TeamListSkeleton } from '../components/skeleton';
import { useI18n } from '../i18n';
import { useLeagueOptions, type LeagueValue } from './HomeScreen';

function Slot({
  team, side, onClear,
}: { team: Team | null; side: 'home' | 'away'; onClear: () => void }) {
  const { t } = useI18n();
  const tone = side === 'home' ? colors.home : colors.away;
  const soft = side === 'home' ? colors.homeSoft : colors.awaySoft;
  return (
    <Pressable
      onPress={team ? onClear : undefined}
      style={[s.slot, team && { borderColor: tone, backgroundColor: soft }]}
    >
      {team ? (
        <>
          <TeamLogo uri={team.logoUrl} size={40} />
          <Text style={s.slotName} numberOfLines={2}>{team.name}</Text>
          <Text style={[s.slotHint, { color: tone }]}>{t.compare.tapToRemove}</Text>
        </>
      ) : (
        <>
          <View style={s.slotEmpty}>
            <Text style={s.slotPlus}>+</Text>
          </View>
          <Text style={s.slotName}>
            {side === 'home' ? t.compare.chooseFirst : t.compare.chooseSecond}
          </Text>
        </>
      )}
    </Pressable>
  );
}

export function CompareScreen({
  league, onLeagueChange, onCompare, onOpenTeam,
}: {
  league: LeagueValue;
  onLeagueChange: (l: LeagueValue) => void;
  onCompare: (league: LeagueValue, a: Team, b: Team) => void;
  onOpenTeam: (league: LeagueValue, teamExternalId: string, teamName: string) => void;
}) {
  const { t } = useI18n();
  const leagueOptions = useLeagueOptions();
  const [teams, setTeams] = useState<Team[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [a, setA] = useState<Team | null>(null);
  const [b, setB] = useState<Team | null>(null);

  const load = useCallback(async (lg: LeagueValue) => {
    setError(null); setTeams(null); setA(null); setB(null);
    try {
      setTeams((await api.teams(lg)).teams);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => { void load(league); }, [league, load]);

  const choose = (t: Team) => {
    if (a?.id === t.id) { setA(null); return; }
    if (b?.id === t.id) { setB(null); return; }
    if (!a) setA(t); else if (!b) setB(t); else setB(t);
  };

  const ready = a !== null && b !== null;

  return (
    <View style={s.root}>
      <HeaderGlow />
      <View style={s.header}>
        <View style={s.headRow}>
          <View style={{ flex: 1 }}>
            <Text style={s.brand}>{t.compare.brand}</Text>
            <Text style={s.sub}>{t.compare.sub}</Text>
          </View>
          <LangSwitch />
        </View>
      </View>

      <ChipRow options={leagueOptions} value={league} onChange={onLeagueChange} />

      <View style={s.slots}>
        <Slot team={a} side="home" onClear={() => setA(null)} />
        <Text style={s.vs}>VS</Text>
        <Slot team={b} side="away" onClear={() => setB(null)} />
      </View>

      <PressScale
        disabled={!ready}
        onPress={() => ready && onCompare(league, a!, b!)}
        style={[s.cta, !ready && s.ctaOff]}
      >
        <Text style={[s.ctaText, !ready && { color: colors.textFaint }]}>
          {ready ? t.compare.ctaReady : t.compare.ctaNotReady}
        </Text>
      </PressScale>

      <ScrollView contentContainerStyle={s.list} showsVerticalScrollIndicator={false}>
        {error && <ErrorBox message={error} onRetry={() => void load(league)} />}
        {!error && !teams && <TeamListSkeleton />}
        {teams?.map((tm, i) => {
          const picked = a?.id === tm.id || b?.id === tm.id;
          return (
            <Reveal key={tm.id} index={i}>
              <PressScale
                onPress={() => choose(tm)}
                onLongPress={() => onOpenTeam(league, tm.refs[0]!.externalId, tm.name)}
                style={[s.item, picked && s.itemPicked]}
              >
                <TeamLogo uri={tm.logoUrl} size={30} />
                <Text style={[s.itemName, picked && { color: colors.accent }]} numberOfLines={1}>
                  {tm.name}
                </Text>
                {picked && <Text style={s.check}>✓</Text>}
              </PressScale>
            </Reveal>
          );
        })}
        {teams && <Text style={s.tip}>{t.compare.longPressTip}</Text>}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, position: 'relative', backgroundColor: colors.bg },
  header: { paddingHorizontal: space.lg, paddingTop: space.md },
  headRow: { flexDirection: 'row', alignItems: 'flex-start', gap: space.sm },
  brand: { ...font.display, color: colors.text },
  sub: { ...font.small, color: colors.textDim, marginTop: 4 },

  slots: {
    flexDirection: 'row', alignItems: 'center', gap: space.sm,
    paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.md,
  },
  slot: {
    flex: 1, alignItems: 'center', gap: 7, paddingVertical: space.lg,
    backgroundColor: colors.card, borderRadius: radius.lg,
    borderWidth: 1.5, borderColor: colors.hairline, borderStyle: 'dashed',
  },
  slotEmpty: {
    width: 40, height: 40, borderRadius: 14,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.055)',
  },
  slotPlus: { fontSize: 22, color: colors.textFaint, fontWeight: '700', marginTop: -2 },
  slotName: { ...font.tiny, color: colors.textSoft, textAlign: 'center', paddingHorizontal: 6 },
  slotHint: { fontSize: 9, fontWeight: '700' },
  vs: { ...font.label, color: colors.textFaint },

  cta: {
    marginHorizontal: space.lg, paddingVertical: space.lg,
    borderRadius: radius.pill, backgroundColor: colors.accent,
    alignItems: 'center', ...shadow.card,
  },
  ctaOff: { backgroundColor: 'rgba(255,255,255,0.055)' },
  ctaText: { ...font.h2, color: '#00230F', fontWeight: '800' },

  list: { padding: space.lg, gap: space.sm, paddingBottom: space.xxl },
  item: {
    flexDirection: 'row', alignItems: 'center', gap: space.md,
    backgroundColor: colors.card, borderRadius: radius.md,
    borderWidth: 1, borderColor: colors.hairline,
    paddingHorizontal: space.lg, paddingVertical: space.md,
  },
  itemPicked: { borderColor: colors.accentLine, backgroundColor: colors.accentSoft },
  itemName: { ...font.body, color: colors.text, flex: 1, fontSize: 14.5 },
  check: { color: colors.accent, fontWeight: '800', fontSize: 15 },
  tip: { ...font.tiny, color: colors.textFaint, textAlign: 'center', marginTop: space.sm },
});
