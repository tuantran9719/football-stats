/**
 * Bảng xếp hạng một giải.
 *
 * Cố ý KHÔNG có mục "tất cả các giải" như màn hình trận đấu: gộp mười hai
 * bảng xếp hạng khác nhau thành một danh sách thì không còn ý nghĩa gì.
 * Vì vậy menu ở đây bỏ showAll, và giải mặc định là Ngoại hạng Anh.
 *
 * Bảng vừa trọn bề ngang màn hình, KHÔNG cuộn ngang: ScrollView ngang
 * lồng trong ScrollView dọc co về bề rộng 0 trên RN Web. Vì vậy mọi cột
 * đều có bề rộng cố định nhỏ nhất có thể và tên đội co giãn phần còn
 * lại — thêm cột mới thì phải đo lại trên màn hình 430px.
 *
 * Cột phong độ tải bằng một lời gọi riêng: ESPN không trả kèm phong độ
 * trong dữ liệu xếp hạng nên phải tra lịch từng đội, mất vài giây. Bảng
 * vẽ ngay khi có dữ liệu xếp hạng, cột phong độ điền vào sau.
 *
 * Màn hình dưới 400px (iPhone SE, mini) không đủ chỗ cho cả mười cột:
 * giữ hết thì tên đội còn "Man…", "Brig…", bảng thành vô dụng. Ở cỡ đó
 * ba cột T/H/B được ẩn đi — chúng là cột ít cần nhất, vì cột phong độ
 * đã cho thấy thắng thua gần đây, còn tổng thì suy ra được từ số trận
 * và điểm.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Pressable, RefreshControl, ScrollView, StyleSheet, Text, useWindowDimensions, View,
} from 'react-native';
import type { StandingRow, StandingsResponse } from '../types';
import { api } from '../api';
import { colors, font, radius, space } from '../theme';
import { Empty, ErrorBox, HeaderGlow, LangSwitch, Loading, PressScale, TeamLogo } from '../components/ui';
import { Ionicons } from '@expo/vector-icons';
import { HamburgerButton, LeagueMenu } from '../components/leagueMenu';
import { useFavorites } from '../favorites';
import { useI18n } from '../i18n';
import type { Dict } from '../i18n/translations';
import { DEFAULT_LEAGUE, useLeagueName, useLeagueOptions, type LeagueValue } from './HomeScreen';

/**
 * Màu dải bên trái mỗi dòng, theo vùng của giải. Không có nguồn dữ liệu
 * nào nói bảng này lấy mấy suất dự cúp châu Âu hay xuống hạng, nên suy ra
 * theo quy ước phổ biến nhất của các giải quốc nội châu Âu và chỉ áp dụng
 * khi bảng có đủ 18 đội trở lên — giải cúp chia bảng thì bỏ qua hẳn.
 */
function zoneColor(rank: number, total: number): string | null {
  if (total < 18) return null;
  if (rank <= 4) return colors.accent;
  if (rank <= 6) return colors.purple;
  if (rank > total - 3) return colors.live;
  return null;
}

/**
 * Năm ô vuông W/D/L, trận mới nhất ở BÊN PHẢI.
 *
 * Đảo thứ tự so với dữ liệu (vốn mới nhất trước) để đọc theo chiều thời
 * gian từ trái sang phải, giống mọi bảng xếp hạng người ta quen nhìn.
 *
 * Chưa có dữ liệu thì vẽ ô rỗng mờ chứ không bỏ trống hẳn: cột giữ
 * nguyên bề rộng nên bảng không nhảy khi phong độ tải xong.
 */
function FormCells({ letters, t }: { letters?: string[]; t: Dict }) {
  const shown = letters ? [...letters].slice(0, 5).reverse() : [];
  const slots = shown.length ? shown : [null, null, null, null, null];
  return (
    <View style={s.form}>
      {slots.map((r, i) => {
        if (!r) return <View key={i} style={[s.formCell, s.formEmpty]} />;
        const bg = r === 'W' ? colors.accent : r === 'D' ? colors.textFaint : colors.card_red;
        const ch = r === 'W' ? t.standings.win : r === 'D' ? t.standings.draw : t.standings.loss;
        return (
          <View key={i} style={[s.formCell, { backgroundColor: bg }]}>
            <Text style={s.formText}>{ch}</Text>
          </View>
        );
      })}
    </View>
  );
}

function Row({
  row, total, highlight, onPress, form, t, compact,
}: {
  row: StandingRow; total: number; highlight: boolean;
  onPress?: () => void;
  form?: string[];
  t: Dict;
  /** Màn hình hẹp: bỏ ba cột thắng/hoà/thua để tên đội đủ chỗ. */
  compact: boolean;
}) {
  const zone = zoneColor(row.rank, total);
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      style={({ pressed }) => [s.row, highlight && s.rowFav, pressed && s.rowPressed]}
    >
      <View style={[s.zone, zone ? { backgroundColor: zone } : null]} />
      <Text style={s.rank}>{row.rank}</Text>
      <TeamLogo uri={row.logoUrl ?? undefined} size={22} />
      <Text style={s.team} numberOfLines={1}>{row.shortName || row.teamName}</Text>
      <Text style={s.num}>{row.played}</Text>
      {!compact && <Text style={s.num}>{row.wins}</Text>}
      {!compact && <Text style={s.num}>{row.draws}</Text>}
      {!compact && <Text style={s.num}>{row.losses}</Text>}
      <Text style={[s.num, s.numWide]}>
        {row.goalDiff > 0 ? `+${row.goalDiff}` : row.goalDiff}
      </Text>
      <Text style={s.points}>{row.points}</Text>
      <FormCells letters={form} t={t} />
    </Pressable>
  );
}

export function StandingsScreen({
  onOpenTeam,
}: {
  /** Bấm một đội để xem phong độ gần đây của đội đó. */
  onOpenTeam?: (league: string, teamExternalId: string, teamName: string) => void;
} = {}) {
  const { t } = useI18n();
  const { width } = useWindowDimensions();
  const compact = width < 400;
  const leagueOptions = useLeagueOptions();
  const leagueName = useLeagueName();
  const { isFavorite } = useFavorites();
  const [league, setLeague] = useState<LeagueValue>(DEFAULT_LEAGUE);
  const [menuOpen, setMenuOpen] = useState(false);
  const [data, setData] = useState<StandingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [form, setForm] = useState<Record<string, string[]> | null>(null);

  const load = useCallback(async (lg: LeagueValue) => {
    setError(null); setData(null);
    try {
      setData(await api.standings(lg));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => { void load(league); }, [league, load]);

  /*
   * Phong độ tải tách khỏi bảng, và lỗi thì im lặng bỏ qua.
   *
   * Đây là cột phụ: bảng xếp hạng vẫn đầy đủ ý nghĩa khi thiếu nó, nên
   * một lời gọi hỏng không được phép làm cả trang báo lỗi. Huỷ theo
   * giải đang xem để đổi giải nhanh không bị dữ liệu giải cũ về sau ghi
   * đè lên giải mới.
   */
  useEffect(() => {
    const ctrl = new AbortController();
    setForm(null);
    api.standingsForm(league, ctrl.signal)
      .then((res) => { if (!ctrl.signal.aborted) setForm(res.form); })
      .catch(() => {});
    return () => ctrl.abort();
  }, [league]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load(league);
    try {
      setForm((await api.standingsForm(league)).form);
    } catch {
      // Cột phụ, hỏng thì giữ nguyên cái đang có.
    }
    setRefreshing(false);
  }, [league, load]);

  // Đội yêu thích được tô sáng ngay trong bảng để tìm nhanh, nhưng KHÔNG
  // đẩy lên đầu như ở danh sách trận: đổi thứ tự của một bảng xếp hạng
  // thì bảng đó không còn là bảng xếp hạng nữa.
  //
  // Dùng teamRef do backend gắn sẵn thay vì tự nối tiền tố: tên nguồn
  // dữ liệu không phải việc của giao diện, và nối tay thì đổi nguồn là
  // mục yêu thích hỏng âm thầm.
  const isFavRow = useCallback(
    (r: StandingRow) => isFavorite(r.teamRef ?? r.teamId),
    [isFavorite],
  );

  const empty = data && data.groups.length === 0;

  return (
    <View style={s.root}>
      <HeaderGlow />
      <View style={s.header}>
        <View style={s.headRow}>
          <HamburgerButton onPress={() => setMenuOpen(true)} />
          <View style={{ flex: 1 }}>
            <Text style={s.brand}>{t.standings.brand}</Text>
            {/* Phụ đề KHÔNG nhắc lại tên giải: ngay bên dưới đã có nút
                chọn giải ghi đúng tên đó rồi, lặp hai lần chỉ tốn chỗ. */}
            <Text style={s.sub}>{t.standings.sub}</Text>
          </View>
          <LangSwitch />
        </View>

        {/* Hàng chọn giải: nút chiếm trọn bề ngang thay vì co theo chữ,
            mùa giải tách hẳn sang phải. Trước đây logo bị nhét chung vào
            một viên nhỏ cạnh tên giải nên phần đầu trang trông chật. */}
        <View style={s.pickRow}>
          <PressScale onPress={() => setMenuOpen(true)} style={s.filterBar}>
            <Text style={s.filterText} numberOfLines={1}>{leagueName(league)}</Text>
            <Ionicons name="chevron-down" size={14} color={colors.accent} />
          </PressScale>
          {!!data?.season && <Text style={s.season}>{data.season}</Text>}
        </View>
      </View>

      <LeagueMenu
        visible={menuOpen}
        onClose={() => setMenuOpen(false)}
        options={leagueOptions}
        value={league}
        onChange={(v) => setLeague(v as LeagueValue)}
      />

      <ScrollView
        contentContainerStyle={s.body}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
        }
      >
        {error && <ErrorBox message={error} onRetry={() => void load(league)} />}
        {!error && !data && <Loading text={t.common.loading} />}
        {empty && <Empty text={t.standings.empty} />}

        {data?.groups.map((g) => (
          <View key={g.name} style={s.group}>
            {data.groups.length > 1 && <Text style={s.groupName}>{g.name}</Text>}
            <View style={s.table}>
              <View style={[s.row, s.headRowTable]}>
                <View style={s.zone} />
                <Text style={[s.rank, s.th]}>#</Text>
                <View style={{ width: 22 }} />
                <Text style={[s.team, s.th]}>{t.standings.team}</Text>
                <Text style={[s.num, s.th]}>{t.standings.played}</Text>
                {!compact && <Text style={[s.num, s.th]}>{t.standings.win}</Text>}
                {!compact && <Text style={[s.num, s.th]}>{t.standings.draw}</Text>}
                {!compact && <Text style={[s.num, s.th]}>{t.standings.loss}</Text>}
                <Text style={[s.num, s.numWide, s.th]}>{t.standings.goalDiff}</Text>
                <Text style={[s.points, s.th]}>{t.standings.points}</Text>
                <Text style={[s.form, s.formTh, s.th]}>{t.standings.form}</Text>
              </View>
              {g.rows.map((r) => (
                <Row
                  key={r.teamId} row={r} total={g.rows.length} highlight={isFavRow(r)}
                  form={form?.[r.teamId]} t={t} compact={compact}
                  // teamId là mã thô của nhà cung cấp, đúng dạng màn
                  // hình phong độ cần (khác teamRef vốn có tiền tố).
                  onPress={onOpenTeam
                    ? () => onOpenTeam(league, r.teamId, r.teamName)
                    : undefined}
                />
              ))}
            </View>
          </View>
        ))}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, position: 'relative', backgroundColor: colors.bg },
  header: { paddingHorizontal: space.lg, paddingTop: space.md, paddingBottom: space.sm },
  headRow: { flexDirection: 'row', alignItems: 'flex-start', gap: space.sm },
  brand: { ...font.title, color: colors.text },
  sub: { ...font.small, color: colors.textDim, marginTop: 3 },

  pickRow: {
    flexDirection: 'row', alignItems: 'center', gap: space.md,
    marginTop: space.md,
  },
  // Đẩy hẳn ra mép phải: để nó dính ngay sau nút chọn giải thì cả hàng
  // dồn về một bên, phần còn lại trống trông như quên căn.
  season: {
    ...font.small, color: colors.textFaint, fontWeight: '700',
    flex: 1, textAlign: 'right',
  },
  filterBar: {
    flexDirection: 'row', alignItems: 'center',
    gap: space.sm,
    paddingHorizontal: space.lg, paddingVertical: 10,
    borderRadius: radius.pill,
    backgroundColor: colors.accentSoft,
    borderWidth: 1, borderColor: colors.accentLine,
  },
  filterText: { ...font.h2, color: colors.accent, fontSize: 14.5, flexShrink: 1 },

  body: { padding: space.lg, paddingTop: space.xs, paddingBottom: space.xxl, gap: space.lg },
  group: { gap: space.sm },
  groupName: { ...font.label, color: colors.textDim },

  table: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.hairline,
    overflow: 'hidden',
  },
  row: {
    // Khe 4px chứ không phải 6: dòng có mười cột nên mỗi pixel khe bị
    // nhân lên chín lần, và chỗ đó lấy thẳng từ tên đội.
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingRight: space.md, paddingVertical: 9,
    borderBottomWidth: 1, borderBottomColor: colors.hairline,
  },
  rowFav: { backgroundColor: colors.accentSoft },
  rowPressed: { backgroundColor: colors.cardPressed },
  headRowTable: { backgroundColor: 'rgba(255,255,255,0.03)', paddingVertical: 7 },
  th: { ...font.tiny, color: colors.textFaint, fontWeight: '800' },

  // Dải màu vùng giải, sát mép trái.
  zone: { width: 3, alignSelf: 'stretch', marginRight: 4 },
  rank: { ...font.tiny, color: colors.textDim, width: 20, textAlign: 'center' },
  team: { ...font.small, color: colors.text, flex: 1, minWidth: 0, fontWeight: '700' },
  num: { ...font.tiny, color: colors.textSoft, width: 20, textAlign: 'center' },
  numWide: { width: 26 },
  points: { ...font.small, color: colors.text, width: 24, textAlign: 'center', fontWeight: '800' },

  // Cột phong độ: 5 ô 12px + 4 khe 2px = 68px. Đây là cột rộng nhất
  // bảng nên mọi thay đổi ở đây đều ăn thẳng vào chỗ của tên đội.
  form: { flexDirection: 'row', gap: 2, width: 68, marginLeft: 2 },
  formTh: { textAlign: 'right' },
  formCell: {
    width: 12, height: 15, borderRadius: 3,
    alignItems: 'center', justifyContent: 'center',
  },
  formEmpty: { backgroundColor: 'rgba(255,255,255,0.05)' },
  formText: { ...font.tiny, color: '#061024', fontSize: 9, fontWeight: '900', lineHeight: 12 },
});
