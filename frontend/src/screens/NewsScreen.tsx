/**
 * Màn hình Tin tức: gộp tin từ 12 giải (hoặc lọc theo một giải), lấy dữ
 * liệu từ ESPN. Bấm vào tin sẽ mở bài viết gốc trên espn.com bằng trình
 * duyệt/app ngoài — không hiển thị nội dung đầy đủ trong app, cùng lý do
 * với link xem highlight: tránh sao chép nội dung có bản quyền của ESPN.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Image, Linking, RefreshControl, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { NewsItem } from '../types';
import { api } from '../api';
import { colors, font, radius, shadow, space } from '../theme';
import { Empty, ErrorBox, HeaderGlow, LangSwitch, PressScale } from '../components/ui';
import { HamburgerButton, LeagueMenu } from '../components/leagueMenu';
import { NewsListSkeleton } from '../components/skeleton';
import { useI18n } from '../i18n';
import type { Dict } from '../i18n/translations';
import { type HomeFilter, useLeagueOptions , useLeagueName } from './HomeScreen';

/** "3 giờ trước" / "3h ago", rơi về ngày/giờ cụ thể khi đã quá lâu. */
function timeAgo(iso: string, t: Dict): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffMin = Math.max(0, Math.round((now - then) / 60000));
  if (diffMin < 1) return t.news.justNow;
  if (diffMin < 60) return t.news.minutesAgo(diffMin);
  const diffHour = Math.round(diffMin / 60);
  if (diffHour < 24) return t.news.hoursAgo(diffHour);
  const diffDay = Math.round(diffHour / 24);
  if (diffDay < 7) return t.news.daysAgo(diffDay);
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`;
}

function NewsCard({ item, t }: { item: NewsItem; t: Dict }) {
  return (
    <PressScale onPress={() => Linking.openURL(item.webUrl)} style={s.card}>
      {item.imageUrl && (
        <Image source={{ uri: item.imageUrl }} style={s.image} resizeMode="cover" />
      )}
      <View style={s.body}>
        <View style={s.metaRow}>
          <Text style={s.league} numberOfLines={1}>
            {t.league[item.leagueCode as keyof typeof t.league] ?? item.leagueCode}
          </Text>
          <Text style={s.time}>{timeAgo(item.publishedUtc, t)}</Text>
        </View>
        <Text style={s.headline} numberOfLines={3}>{item.headline}</Text>
        {item.description && (
          <Text style={s.desc} numberOfLines={2}>{item.description}</Text>
        )}
        <View style={s.foot}>
          <Text style={s.cta}>{t.news.readMore}</Text>
          <Ionicons name="open-outline" size={13} color={colors.accent} />
        </View>
      </View>
    </PressScale>
  );
}

export function NewsScreen() {
  const { t } = useI18n();
  const leagueOptions = useLeagueOptions();
  const [filter, setFilter] = useState<HomeFilter>('ALL');
  const [menuOpen, setMenuOpen] = useState(false);
  const [articles, setArticles] = useState<NewsItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (lg: HomeFilter) => {
    setError(null); setArticles(null);
    try {
      setArticles((await api.news(lg)).articles);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => { void load(filter); }, [filter, load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true); await load(filter); setRefreshing(false);
  }, [filter, load]);

  const leagueName = useLeagueName();
  const filterLabel = filter === 'ALL' ? t.league.ALL : leagueName(filter);

  return (
    <View style={s.root}>
      <HeaderGlow />
      <View style={s.header}>
        <View style={s.headRow}>
          <HamburgerButton onPress={() => setMenuOpen(true)} />
          <View style={{ flex: 1 }}>
            <View style={s.brandRow}>
              <Ionicons name="newspaper" size={22} color={colors.accent} />
              <Text style={s.brand}>{t.news.brand}</Text>
            </View>
            <Text style={s.sub}>{t.news.sub}</Text>
          </View>
          <LangSwitch />
        </View>
        <PressScale onPress={() => setMenuOpen(true)} style={s.filterBar}>
          <Text style={s.filterText} numberOfLines={1}>{filterLabel}</Text>
          <Text style={s.filterChevron}>▾</Text>
        </PressScale>
      </View>

      <LeagueMenu
        visible={menuOpen}
        onClose={() => setMenuOpen(false)}
        options={leagueOptions}
        value={filter}
        onChange={setFilter}
        showAll
      />

      <ScrollView
        contentContainerStyle={s.list}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
        }
      >
        {error && <ErrorBox message={error} onRetry={() => void load(filter)} />}
        {!error && articles === null && <NewsListSkeleton key={`skel-${filter}`} />}
        {!error && articles?.length === 0 && <Empty text={t.news.empty} />}
        {articles && articles.length > 0 && (
          <View key={`news-${filter}`} style={{ gap: space.md }}>
            {articles.map((a) => <NewsCard key={a.id} item={a} t={t} />)}
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, position: 'relative', backgroundColor: colors.bg },
  header: { paddingHorizontal: space.lg, paddingTop: space.md, paddingBottom: space.sm },
  headRow: { flexDirection: 'row', alignItems: 'flex-start', gap: space.sm },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  brand: { ...font.display, fontSize: 26, color: colors.text },
  sub: { ...font.small, color: colors.textDim, marginTop: 4 },

  filterBar: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    alignSelf: 'flex-start',
    marginTop: space.md,
    paddingHorizontal: space.md, paddingVertical: 8,
    borderRadius: radius.pill,
    backgroundColor: colors.accentSoft,
    borderWidth: 1, borderColor: colors.accentLine,
    maxWidth: '100%',
  },
  filterText: { ...font.small, color: colors.accent, fontWeight: '800' },
  filterChevron: { color: colors.accent, fontSize: 11, marginTop: 1 },

  list: { padding: space.lg, paddingTop: space.xs, gap: space.md, paddingBottom: space.xxl },

  card: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    overflow: 'hidden',
    ...shadow.card,
  },
  image: { width: '100%', height: 160, backgroundColor: colors.bgElev },
  body: { padding: space.lg, gap: 6 },
  metaRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.sm },
  league: { ...font.label, color: colors.accent, fontSize: 9.5 },
  time: { ...font.tiny, color: colors.textFaint },
  headline: { ...font.h2, color: colors.text, fontSize: 15.5, lineHeight: 20 },
  desc: { ...font.small, color: colors.textDim, lineHeight: 18 },
  foot: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 4 },
  cta: { ...font.small, color: colors.accent },
});
