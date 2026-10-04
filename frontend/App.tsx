/**
 * Điểm vào của app.
 *
 * Có hai tab chính ở dưới cùng, và các màn hình chi tiết mở chồng lên trên.
 * Dùng state thay vì thư viện điều hướng vì số màn hình còn ít.
 */
import React, { useEffect, useRef, useState } from 'react';
import {
  Animated, Platform, Pressable, SafeAreaView, StatusBar, StyleSheet, Text, View,
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { BlurView } from 'expo-blur';
import { LinearGradient } from 'expo-linear-gradient';
import type { Match, Team } from './src/types';
import { colors, font, gradients, radius, space } from './src/theme';
import { LanguageProvider, useI18n } from './src/i18n';
import { FavoritesProvider } from './src/favorites';
import { SettingsProvider } from './src/settings';
import { HomeScreen, type LeagueValue } from './src/screens/HomeScreen';
import { CompareScreen } from './src/screens/CompareScreen';
import { NewsScreen } from './src/screens/NewsScreen';
import { StandingsScreen } from './src/screens/StandingsScreen';
import { MatchDetailScreen } from './src/screens/MatchDetailScreen';
import { TeamFormScreen } from './src/screens/TeamFormScreen';
import { H2HScreen } from './src/screens/H2HScreen';

type Tab = 'matches' | 'standings' | 'news' | 'compare';

/**
 * Một màn hình con chồng lên phần tab.
 *
 * Giữ thành ngăn xếp thật (mảng) chứ không phải một giá trị đơn: từ chi
 * tiết trận có thể mở phong độ một đội, rồi từ danh sách trận gần đây của
 * đội đó lại mở chi tiết một trận khác. Với một giá trị đơn, nút Quay lại
 * ở trận thứ hai sẽ nhảy thẳng về trang chủ thay vì về màn hình trước.
 */
type Screen =
  | { name: 'match'; league: string; match: Match }
  | { name: 'team'; league: string; teamExternalId: string; teamName: string }
  | { name: 'h2h'; league: string; teamA: Team; teamB: Team };

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];
type MaterialIconName = React.ComponentProps<typeof MaterialCommunityIcons>['name'];

/**
 * Icon của một tab, kèm bộ icon mà nó thuộc về.
 *
 * Phần lớn tab dùng Ionicons, nhưng bộ này không có quả bóng tròn:
 * 'football' của Ionicons là bóng bầu dục kiểu Mỹ. Nên tab trận đấu lấy
 * quả bóng đá từ MaterialCommunityIcons.
 */
type TabIcon =
  | { set: 'ionicons'; active: IoniconName; inactive: IoniconName }
  | { set: 'material'; active: MaterialIconName; inactive: MaterialIconName };

// Bảng xếp hạng đứng ngay sau danh sách trận: đó là hai thứ người xem
// bóng đá mở nhiều nhất, còn tin tức và đối đầu là phần tra cứu thêm.
const TAB_ORDER: Tab[] = ['matches', 'standings', 'news', 'compare'];
const TAB_ICON: Record<Tab, TabIcon> = {
  // MaterialCommunityIcons chỉ có một biến thể quả bóng, nên trạng thái
  // chọn/không chọn phân biệt bằng màu như các tab khác.
  matches: { set: 'material', active: 'soccer', inactive: 'soccer' },
  standings: { set: 'ionicons', active: 'list', inactive: 'list-outline' },
  news: { set: 'ionicons', active: 'newspaper', inactive: 'newspaper-outline' },
  compare: { set: 'ionicons', active: 'people', inactive: 'people-outline' },
};

export default function App() {
  return (
    <LanguageProvider>
      <FavoritesProvider>
        <SettingsProvider>
          <AppShell />
        </SettingsProvider>
      </FavoritesProvider>
    </LanguageProvider>
  );
}

/** Một nút tab: icon nảy nhẹ khi được chọn, đo chiều rộng cho viên chỉ báo bên trên. */
function TabButton({
  tabKey, active, label, onPress, onLayout,
}: {
  tabKey: Tab; active: boolean; label: string; onPress: () => void;
  onLayout: (w: number) => void;
}) {
  const bounce = useRef(new Animated.Value(1)).current;
  const icon = TAB_ICON[tabKey];

  useEffect(() => {
    if (!active) return;
    bounce.setValue(0.72);
    Animated.spring(bounce, { toValue: 1, useNativeDriver: true, speed: 16, bounciness: 12 }).start();
  }, [active, bounce]);

  return (
    <Pressable
      onPress={onPress}
      onLayout={(e) => onLayout(e.nativeEvent.layout.width)}
      style={({ pressed }) => [s.tab, pressed && { opacity: 0.7 }]}
    >
      <Animated.View style={{ transform: [{ scale: bounce }] }}>
        {icon.set === 'material' ? (
          <MaterialCommunityIcons
            name={active ? icon.active : icon.inactive}
            size={22}
            color={active ? colors.accent : colors.textFaint}
          />
        ) : (
          <Ionicons
            name={active ? icon.active : icon.inactive}
            size={22}
            color={active ? colors.accent : colors.textFaint}
          />
        )}
      </Animated.View>
      <Text style={[s.tabLabel, active && s.tabLabelActive]}>{label}</Text>
    </Pressable>
  );
}

function AppShell() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>('matches');
  const [league, setLeague] = useState<LeagueValue>('EPL');
  const [stack, setStack] = useState<Screen[]>([]);
  const top = stack.length > 0 ? stack[stack.length - 1]! : null;

  const push = (screen: Screen) => setStack((prev) => {
    // Bỏ qua khi màn hình định mở trùng đúng màn hình đang đứng. Không có
    // chốt này thì bấm vào trận đang xem trong danh sách đối đầu sẽ đẩy
    // thêm một bước y hệt vào ngăn xếp: màn hình không đổi gì nhưng phải
    // bấm Quay lại hai lần mới thoát.
    const cur = prev[prev.length - 1];
    if (cur && cur.name === screen.name) {
      if (cur.name === 'match' && screen.name === 'match' && cur.match.id === screen.match.id) return prev;
      if (cur.name === 'team' && screen.name === 'team'
        && cur.teamExternalId === screen.teamExternalId) return prev;
    }
    return [...prev, screen];
  });
  const closeTop = () => setStack((prev) => prev.slice(0, -1));

  // Viên chỉ báo phía trên tab đang chọn, trượt mượt thay vì nhảy tức thì.
  const [tabWidths, setTabWidths] = useState<number[]>(TAB_ORDER.map(() => 0));
  const markX = useRef(new Animated.Value(0)).current;
  const markW = useRef(new Animated.Value(0)).current;
  const tabIndex = TAB_ORDER.indexOf(tab);
  const tabsMeasured = tabWidths.every((w) => w > 0);

  useEffect(() => {
    if (!tabsMeasured) return;
    const tabStart = tabWidths.slice(0, tabIndex).reduce((a, b) => a + b, 0);
    const indicatorW = tabWidths[tabIndex]! * 0.42;
    const x = tabStart + (tabWidths[tabIndex]! - indicatorW) / 2;
    Animated.spring(markX, { toValue: x, useNativeDriver: false, speed: 18, bounciness: 6 }).start();
    Animated.spring(markW, { toValue: indicatorW, useNativeDriver: false, speed: 18, bounciness: 6 }).start();
  }, [tabIndex, tabsMeasured, tabWidths, markX, markW]);

  // Chuyển mượt giữa nội dung hai tab thay vì đổi đột ngột.
  const contentFade = useRef(new Animated.Value(1)).current;
  const changeTab = (next: Tab) => {
    if (next === tab) return;
    Animated.timing(contentFade, { toValue: 0, duration: 90, useNativeDriver: true }).start(() => {
      setTab(next);
      Animated.timing(contentFade, { toValue: 1, duration: 200, useNativeDriver: true }).start();
    });
  };

  return (
    <View style={s.root}>
      <StatusBar barStyle="light-content" backgroundColor={colors.bg} />
      <SafeAreaView style={s.safe}>
        <View style={s.content}>
          {/* Tab bên dưới, luôn tồn tại để giữ trạng thái khi mở màn hình con */}
          <View style={[s.layer, top !== null && s.hidden]} pointerEvents={top ? 'none' : 'auto'}>
            <Animated.View style={{ flex: 1, opacity: contentFade }}>
              {tab === 'matches' && (
                <HomeScreen onOpenMatch={(lg, m) => push({ name: 'match', league: lg, match: m })} />
              )}
              {tab === 'standings' && (
                <StandingsScreen
                  onOpenTeam={(lg, id, name) =>
                    push({ name: 'team', league: lg, teamExternalId: id, teamName: name })
                  }
                />
              )}
              {tab === 'news' && <NewsScreen />}
              {tab === 'compare' && (
                <CompareScreen
                  league={league}
                  onLeagueChange={setLeague}
                  onCompare={(lg, a, b) => push({ name: 'h2h', league: lg, teamA: a, teamB: b })}
                  onOpenTeam={(lg, id, name) =>
                    push({ name: 'team', league: lg, teamExternalId: id, teamName: name })
                  }
                />
              )}
            </Animated.View>
          </View>

          {/* Màn hình chi tiết mở chồng lên */}
          {top?.name === 'match' && (
            <View style={s.layer}>
              <MatchDetailScreen
                key={top.match.id}
                league={top.league}
                match={top.match}
                onBack={closeTop}
                onOpenTeam={(id, name) =>
                  push({ name: 'team', league: top.league, teamExternalId: id, teamName: name })
                }
                onOpenMatch={(m) => push({ name: 'match', league: top.league, match: m })}
              />
            </View>
          )}

          {top?.name === 'team' && (
            <View style={s.layer}>
              <TeamFormScreen
                key={top.teamExternalId}
                league={top.league}
                teamExternalId={top.teamExternalId}
                teamName={top.teamName}
                onBack={closeTop}
                onOpenMatch={(m) => push({ name: 'match', league: top.league, match: m })}
              />
            </View>
          )}

          {top?.name === 'h2h' && (
            <View style={s.layer}>
              <H2HScreen
                league={top.league}
                teamA={top.teamA}
                teamB={top.teamB}
                onBack={closeTop}
              />
            </View>
          )}
        </View>

        {top === null && (
          <View style={s.tabbarWrap}>
            <BlurView
              intensity={54}
              tint="dark"
              style={StyleSheet.absoluteFill}
              blurMethod="dimezisBlurView"
            />
            <View style={s.tabbarTint} pointerEvents="none" />
            <View style={s.tabbar}>
              {tabsMeasured && (
                <Animated.View
                  pointerEvents="none"
                  style={[s.tabMark, { transform: [{ translateX: markX }], width: markW }]}
                >
                  <LinearGradient
                    colors={gradients.electric}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 0 }}
                    style={StyleSheet.absoluteFill}
                  />
                </Animated.View>
              )}
              {TAB_ORDER.map((key, i) => (
                <TabButton
                  key={key}
                  tabKey={key}
                  active={key === tab}
                  label={t.tab[key]}
                  onPress={() => changeTab(key)}
                  onLayout={(w) => setTabWidths((prev) => {
                    if (prev[i] === w) return prev;
                    const next = [...prev];
                    next[i] = w;
                    return next;
                  })}
                />
              ))}
            </View>
          </View>
        )}
      </SafeAreaView>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { flex: 1, position: 'relative' },
  layer: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: colors.bg,
  },
  hidden: { opacity: 0 },

  // Thanh tab nổi dạng kính mờ (glass), cách viền màn hình thay vì dính
  // sát đáy như trước — đúng xu hướng navigation nổi phổ biến 2026 thay vì
  // thanh đặc kẻ viền trên cứng nhắc.
  tabbarWrap: {
    position: 'relative',
    marginHorizontal: space.lg,
    marginBottom: Platform.OS === 'ios' ? space.xs : space.md,
    borderRadius: radius.xl,
    overflow: 'hidden',
    borderWidth: 1, borderColor: colors.glassBorder,
    shadowColor: '#000', shadowOpacity: 0.35, shadowRadius: 18,
    shadowOffset: { width: 0, height: 8 }, elevation: 10,
  },
  tabbarTint: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: colors.glassTint,
  },
  tabbar: {
    position: 'relative',
    flexDirection: 'row',
    paddingTop: space.sm,
    paddingBottom: space.sm,
  },
  tab: { flex: 1, alignItems: 'center', gap: 3, paddingVertical: space.xs },
  tabLabel: { ...font.tiny, color: colors.textFaint, fontSize: 10.5 },
  tabLabelActive: { color: colors.accent, fontWeight: '800' },
  tabMark: {
    position: 'absolute', top: -space.sm, left: 0, height: 2.5,
    borderRadius: 2, overflow: 'hidden',
  },
});
