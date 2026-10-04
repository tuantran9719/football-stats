/**
 * Bảng lịch sử theo trận, dùng chung cho hai chỗ:
 *   - Tab "Đối đầu" trong màn hình chi tiết trận: chỉ những lần hai đội
 *     thực sự gặp nhau, gặp bao nhiêu hiện bấy nhiêu.
 *   - Tab "Trận gần đây" trong màn hình phong độ đội: N trận gần nhất
 *     của riêng một đội, không kể đối thủ.
 *
 * Số bàn thắng/phạt góc/thẻ hiển thị là TỔNG của cả hai đội trong trận đó,
 * đúng kiểu người xem để soi tài xỉu. Tỉ số và tỉ số hiệp một giữ nguyên
 * dạng nhà/khách vì đó là con số cụ thể của trận.
 *
 * Mỗi dòng có hiệu ứng xuất hiện so le (fade và trượt nhẹ lên trên), làm
 * mới lại mỗi khi đổi cửa sổ 5/10/20 nhờ key ở component cha.
 */
import React, { useEffect, useRef } from 'react';
import {
  Animated, Image, Pressable, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import type { Match, MatchRow } from '../types';
import type { Dict } from '../i18n/translations';

/**
 * Tên giải để hiện lên màn hình.
 *
 * Ưu tiên bản dịch cho 12 giải vô địch chính; các giải cúp (FA Cup,
 * Coppa Italia, Campeonato Paulista...) không có trong từ điển vì đều là
 * danh từ riêng, nên lấy tên backend gửi kèm.
 */
function leagueLabel(t: Dict, code?: string | null, name?: string | null): string {
  if (code && code in t.league) return t.league[code as keyof typeof t.league];
  return name || code || '';
}
import { colors, font, radius, shadow, space } from '../theme';

/**
 * Dựng một Match tối thiểu từ một dòng lịch sử, đủ để mở màn hình chi
 * tiết trận.
 *
 * Màn hình chi tiết chỉ cần mã trận để tự gọi API lấy đầy đủ số liệu;
 * phần còn lại ở đây chỉ để vẽ bảng điểm trong lúc chờ tải, nên không
 * cần dựng lại một Match hoàn chỉnh.
 */
function rowToMatch(row: MatchRow, leagueCode: string): Match {
  // Mã từ backend luôn có dạng "<nguồn>:<mã thô>". Tách ra thay vì
  // viết cứng tên nguồn: đổi nhà cung cấp dữ liệu thì chỗ này tự đúng.
  const bare = (id: string) => id.replace(/^[a-z0-9]+:/i, '');
  const source = (id: string) => (id.includes(':') ? id.split(':')[0] : 'unknown');
  const team = (id: string, name: string, short?: string, logo?: string) => ({
    id, name, shortName: short, logoUrl: logo,
    refs: [{ provider: source(id), externalId: bare(id) }],
  });
  return {
    id: row.matchId,
    leagueCode,
    season: String(new Date(row.date).getFullYear()),
    kickoffUtc: row.date,
    status: row.status,
    home: team(row.homeTeamId, row.homeTeamName, row.homeTeamShort, row.homeTeamLogo),
    away: team(row.awayTeamId, row.awayTeamName, row.awayTeamShort, row.awayTeamLogo),
    score: row.score,
    refs: [{ provider: source(row.matchId), externalId: bare(row.matchId) }],
  };
}

function fmtDate(iso: string) {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  return `${dd}/${mm}/${d.getFullYear()}`;
}

function MiniLogo({ uri, size = 26 }: { uri?: string; size?: number }) {
  return (
    <View style={[mini.box, { width: size, height: size, borderRadius: size / 2.6 }]}>
      {uri ? (
        <Image source={{ uri }} style={{ width: size * 0.76, height: size * 0.76 }} resizeMode="contain" />
      ) : null}
    </View>
  );
}
const mini = StyleSheet.create({
  box: {
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.06)',
  },
});

function StatCell({ value, label }: { value: number | null | undefined; label: string }) {
  return (
    <View style={s.statCell}>
      <Text style={s.statValue}>{value === null || value === undefined ? '–' : Math.round(value)}</Text>
      <Text style={s.statLabel} numberOfLines={1}>{label}</Text>
    </View>
  );
}

function Row({
  row, t, focusTeamId, index, onPress, isCurrent,
}: {
  row: MatchRow; t: Dict; focusTeamId?: string; index: number;
  onPress?: () => void;
  /** Dòng này chính là trận đang mở ở màn hình cha. */
  isCurrent?: boolean;
}) {
  const fade = useRef(new Animated.Value(0)).current;
  const slide = useRef(new Animated.Value(10)).current;

  useEffect(() => {
    const delay = Math.min(index, 8) * 45;
    Animated.parallel([
      Animated.timing(fade, {
        toValue: 1, duration: 320, delay, useNativeDriver: true,
      }),
      Animated.timing(slide, {
        toValue: 0, duration: 320, delay, useNativeDriver: true,
      }),
    ]).start();
  }, [fade, slide, index]);

  const homeIsFocus = focusTeamId !== undefined && row.homeTeamId === focusTeamId;
  const awayIsFocus = focusTeamId !== undefined && row.awayTeamId === focusTeamId;

  return (
    <Animated.View style={{ opacity: fade, transform: [{ translateY: slide }] }}>
      <Pressable
        onPress={onPress}
        disabled={!onPress}
        style={({ pressed }) => [
          s.card,
          isCurrent && s.cardCurrent,
          pressed && !!onPress && s.cardPressed,
        ]}
      >
        <View style={s.topRow}>
          <Text style={s.date}>{fmtDate(row.date)}</Text>
          {/* Tên giải: hai đội có thể gặp nhau ở nhiều giải khác nhau,
              một trận cúp và một trận vô địch quốc gia nói lên hai câu
              chuyện khác hẳn nhau. */}
          {!!row.leagueCode && (
            <View style={s.leagueWrap}>
              {!!row.leagueLogoUrl && (
                <Image
                  source={{ uri: row.leagueLogoUrl }}
                  style={s.leagueLogo}
                  resizeMode="contain"
                />
              )}
              <Text style={s.league} numberOfLines={1}>
                {leagueLabel(t, row.leagueCode, row.leagueName)}
              </Text>
            </View>
          )}
          {/* Trận đang mở thì nói rõ ra. Trước đây dòng này vẫn bấm được
              nhưng mở lại đúng trang đang đứng nên trông như nút hỏng:
              có nhấp nháy mà không đi đâu cả. */}
          {isCurrent && (
            <View style={[s.tag, { backgroundColor: colors.accentSoft }]}>
              <Text style={[s.tagText, { color: colors.accent }]}>{t.matchTable.viewing}</Text>
            </View>
          )}
          {!isCurrent && focusTeamId !== undefined && (
            <View style={[s.tag, { backgroundColor: homeIsFocus ? colors.homeSoft : colors.awaySoft }]}>
              <Text style={[s.tagText, { color: homeIsFocus ? colors.home : colors.away }]}>
                {homeIsFocus ? t.matchDetail.home : t.matchDetail.away}
              </Text>
            </View>
          )}
        </View>

        <View style={s.midRow}>
          <View style={s.teamSide}>
            <MiniLogo uri={row.homeTeamLogo} />
            <Text
              style={[s.teamName, homeIsFocus && s.teamNameFocus]}
              numberOfLines={1}
            >
              {row.homeTeamShort ?? row.homeTeamName}
            </Text>
          </View>

          <View style={s.scoreBlock}>
            <Text style={s.score}>
              {row.score ? `${row.score.home} - ${row.score.away}` : '–'}
            </Text>
            {row.htScore && (
              <Text style={s.ht}>{t.matchTable.ht(row.htScore.home, row.htScore.away)}</Text>
            )}
          </View>

          <View style={[s.teamSide, s.teamSideRight]}>
            <Text
              style={[s.teamName, s.teamNameRight, awayIsFocus && s.teamNameFocus]}
              numberOfLines={1}
            >
              {row.awayTeamShort ?? row.awayTeamName}
            </Text>
            <MiniLogo uri={row.awayTeamLogo} />
          </View>
        </View>

        <View style={s.statsStrip}>
          <StatCell value={row.totalGoals} label={t.matchTable.goals} />
          <StatCell value={row.totalCorners} label={t.matchTable.corners} />
          <StatCell value={row.totalYellowCards} label={t.matchTable.yellow} />
          <StatCell value={row.totalRedCards} label={t.matchTable.red} />
        </View>
      </Pressable>
    </Animated.View>
  );
}

/**
 * Hàng nút lọc theo giải cho bảng đối đầu.
 *
 * Chỉ hiện khi danh sách thực sự có từ hai giải trở lên — hai đội quốc
 * nội chỉ gặp nhau ở một giải thì bộ lọc một nút là thừa và rối.
 *
 * Cho chọn nhiều giải cùng lúc: bỏ chọn hết đồng nghĩa với xem tất cả,
 * nên không cần thêm nút "tất cả" riêng bên cạnh.
 */
function CompetitionFilter({
  codes, selected, onToggle, onClear, t,
}: {
  codes: Array<{ code: string; label: string; logo?: string | null }>;
  selected: Set<string>;
  onToggle: (code: string) => void;
  onClear: () => void;
  t: Dict;
}) {
  const all = selected.size === 0;
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      style={s.filterScroll}
      contentContainerStyle={s.filterRow}
    >
      <Pressable
        onPress={onClear}
        style={[s.chip, all && s.chipActive]}
      >
        <Text style={[s.chipText, all && s.chipTextActive]}>{t.matchTable.allCompetitions}</Text>
      </Pressable>
      {codes.map(({ code, label, logo }) => {
        const on = selected.has(code);
        return (
          <Pressable
            key={code}
            onPress={() => onToggle(code)}
            style={[s.chip, on && s.chipActive]}
          >
            {!!logo && (
              <Image source={{ uri: logo }} style={s.chipLogo} resizeMode="contain" />
            )}
            <Text style={[s.chipText, on && s.chipTextActive]} numberOfLines={1}>
              {label}
            </Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

export function MatchHistoryList({
  rows, t, focusTeamId, league, onOpenMatch, currentMatchId,
}: {
  rows: MatchRow[]; t: Dict; focusTeamId?: string;
  /** Cần để dựng Match khi mở chi tiết; bỏ trống thì dòng không bấm được. */
  league?: string;
  onOpenMatch?: (m: Match) => void;
  /** Mã trận đang mở ở màn hình cha, nếu có, để khỏi mở lại chính nó. */
  currentMatchId?: string;
}) {
  const [picked, setPicked] = React.useState<Set<string>>(() => new Set());

  // Giữ nguyên thứ tự xuất hiện: giải hay gặp nhất nằm trước.
  const codes = React.useMemo(() => {
    const out: Array<{ code: string; label: string; logo?: string | null }> = [];
    for (const r of rows) {
      if (!r.leagueCode || out.some((o) => o.code === r.leagueCode)) continue;
      out.push({
        code: r.leagueCode,
        label: leagueLabel(t, r.leagueCode, r.leagueName),
        logo: r.leagueLogoUrl,
      });
    }
    return out;
  }, [rows, t]);

  const shown = React.useMemo(
    () => (picked.size === 0
      ? rows
      : rows.filter((r) => !!r.leagueCode && picked.has(r.leagueCode))),
    [rows, picked],
  );

  const toggle = React.useCallback((code: string) => {
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }, []);

  if (rows.length === 0) {
    return (
      <View style={s.empty}>
        <Text style={s.emptyText}>{t.matchTable.noRows}</Text>
      </View>
    );
  }
  return (
    <View style={s.list}>
      {codes.length > 1 && (
        <CompetitionFilter
          codes={codes} selected={picked} t={t}
          onToggle={toggle} onClear={() => setPicked(new Set())}
        />
      )}
      {shown.length === 0 && (
        <View style={s.empty}>
          <Text style={s.emptyText}>{t.matchTable.noRows}</Text>
        </View>
      )}
      {shown.map((row, i) => (
        <Row
          key={row.matchId} row={row} t={t} focusTeamId={focusTeamId} index={i}
          isCurrent={row.matchId === currentMatchId}
          onPress={onOpenMatch && league && row.matchId !== currentMatchId
            ? () => onOpenMatch(rowToMatch(row, league))
            : undefined}
        />
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  list: { gap: space.sm },

  // Bộ lọc giải. Không có style này thì ScrollView ngang trên web tự co
  // chiều cao xuống gần 0 và cắt mất chữ bên trong.
  filterScroll: { flexGrow: 0, flexShrink: 0, width: '100%' },
  filterRow: { gap: 6, paddingRight: space.lg, paddingBottom: 2 },
  chipLogo: { width: 14, height: 14 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 7,
    borderRadius: radius.pill,
    backgroundColor: colors.card,
    borderWidth: 1, borderColor: colors.hairline,
  },
  chipActive: { backgroundColor: colors.accentSoft, borderColor: colors.accentLine },
  chipText: { ...font.tiny, color: colors.textDim, fontWeight: '700' },
  chipTextActive: { color: colors.accent, fontWeight: '800' },

  cardPressed: { backgroundColor: colors.cardPressed, borderColor: colors.border },
  cardCurrent: { borderColor: colors.accentLine, backgroundColor: colors.accentSoft },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.md,
    gap: space.sm,
    ...shadow.card,
  },

  topRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  leagueWrap: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    flex: 1, marginLeft: space.sm, minWidth: 0,
  },
  leagueLogo: { width: 13, height: 13 },
  league: {
    ...font.tiny, color: colors.accent, fontWeight: '800',
    fontSize: 10, flexShrink: 1,
  },
  date: { ...font.tiny, color: colors.textFaint },
  tag: { paddingHorizontal: 7, paddingVertical: 2.5, borderRadius: radius.pill },
  tagText: { fontSize: 8.5, fontWeight: '800', letterSpacing: 0.5 },

  midRow: { flexDirection: 'row', alignItems: 'center' },
  teamSide: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 7 },
  teamSideRight: { justifyContent: 'flex-end' },
  teamName: { ...font.small, color: colors.textSoft, flexShrink: 1, fontSize: 12.5 },
  teamNameRight: { textAlign: 'right' },
  teamNameFocus: { color: colors.text, fontWeight: '800' },

  scoreBlock: { alignItems: 'center', paddingHorizontal: space.sm, minWidth: 68 },
  score: { ...font.h2, color: colors.text, fontSize: 17, fontWeight: '800' },
  ht: { fontSize: 9.5, color: colors.textFaint, marginTop: 1, fontWeight: '600' },

  statsStrip: {
    flexDirection: 'row', borderTopWidth: 1, borderTopColor: colors.hairline,
    paddingTop: space.sm, marginTop: 2,
  },
  statCell: { flex: 1, alignItems: 'center', gap: 1 },
  statValue: { ...font.h2, color: colors.text, fontSize: 15 },
  statLabel: { fontSize: 9.5, color: colors.textFaint, fontWeight: '600' },

  empty: { paddingVertical: space.xxl, alignItems: 'center' },
  emptyText: { ...font.small, color: colors.textFaint, textAlign: 'center' },
});
