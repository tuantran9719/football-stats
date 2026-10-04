/**
 * Đội hình ra sân vẽ trên sân cỏ, thay cho danh sách tên dọc.
 *
 * Sân vẽ bằng View và đường viền chứ không dùng ảnh nền: nét sắc ở mọi
 * mật độ màn hình, đổi màu theo theme chỉ sửa một chỗ, và không thêm
 * một tệp ảnh nào vào gói cài đặt.
 *
 * XẾP NGƯỜI LÊN SÂN — phần khó nhất, và không thể chỉ dựa vào một
 * trường dữ liệu:
 *
 *   - Số thứ tự trong sơ đồ mà nguồn trả về (`formationPlace`) KHÔNG
 *     chạy theo hàng. Một trận 4-2-3-1 thật trả về số 4 cho tiền vệ
 *     trái và số 5 cho trung vệ — xếp theo số là hàng thủ có tiền vệ
 *     đứng lẫn vào.
 *   - Nên hàng được suy từ VỊ TRÍ ("CD-L", "AM-R", "RB"), còn chuỗi sơ
 *     đồ ("4-2-3-1") quyết định mỗi hàng có mấy người.
 *   - Hậu tố -L / -R và các mã LB/RB cho biết ai đứng biên nào, nhờ vậy
 *     hậu vệ trái không bị vẽ sang cánh phải.
 *
 * Thiếu dữ liệu thì tự lùi: không có sơ đồ hoặc xếp không khớp thì trả
 * về null để bên gọi hiện danh sách như cũ, chứ không vẽ một sân sai.
 */
import React from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { LineupPlayer, TeamLineup } from '../types';
import { colors, font, radius } from '../theme';

/** Độ sâu của một vị trí trên sân: 0 là thủ môn, lớn dần về phía khung thành đối phương. */
function depth(position?: string | null): number {
  const p = (position || '').toUpperCase();
  if (p.startsWith('G')) return 0;
  if (p.startsWith('SW')) return 1;
  if (p.startsWith('CD') || p.startsWith('LB') || p.startsWith('RB')
      || p.startsWith('LWB') || p.startsWith('RWB') || p === 'D') return 1;
  if (p.startsWith('DM')) return 2;
  if (p.startsWith('AM')) return 4;
  if (p.startsWith('F') || p.startsWith('ST') || p.startsWith('CF')
      || p.startsWith('LW') || p.startsWith('RW')) return 5;
  if (p.startsWith('M') || p.startsWith('LM') || p.startsWith('RM')) return 3;
  return 3;
}

/** Vị trí ngang: âm là cánh trái, dương là cánh phải. */
function lane(position?: string | null): number {
  const p = (position || '').toUpperCase();
  if (p.startsWith('LB') || p.startsWith('LWB')) return -2;
  if (p.startsWith('RB') || p.startsWith('RWB')) return 2;
  if (p.endsWith('-L')) return -1;
  if (p.endsWith('-R')) return 1;
  if (p.startsWith('LM') || p.startsWith('LW')) return -1.5;
  if (p.startsWith('RM') || p.startsWith('RW')) return 1.5;
  return 0;
}

/**
 * Chia 11 người vào các hàng theo sơ đồ.
 *
 * Trả về null khi không chia được, để bên gọi lùi về danh sách thường.
 */
export function buildRows(lineup: TeamLineup): LineupPlayer[][] | null {
  const starters = lineup.starters.filter((p) => p.starter);
  if (starters.length < 7) return null;

  const counts = (lineup.formation || '')
    .split('-')
    .map((n) => parseInt(n, 10))
    .filter((n) => Number.isFinite(n) && n > 0);
  if (counts.length === 0) return null;

  const keeper = starters.find((p) => depth(p.position) === 0);
  const outfield = starters.filter((p) => p !== keeper);
  if (!keeper || outfield.length !== counts.reduce((a, b) => a + b, 0)) return null;

  // Sắp theo độ sâu rồi cắt thành từng hàng đúng số người sơ đồ yêu cầu.
  const sorted = [...outfield].sort((a, b) => depth(a.position) - depth(b.position));
  const rows: LineupPlayer[][] = [];
  let i = 0;
  for (const n of counts) {
    const row = sorted.slice(i, i + n);
    if (row.length !== n) return null;
    row.sort((a, b) => lane(a.position) - lane(b.position));
    rows.push(row);
    i += n;
  }
  // Hàng gần khung thành nhà vẽ trước, nên đảo lại để tiền đạo ở trên.
  return [[keeper], ...rows].reverse();
}

function Badge({ name, tone }: { name: React.ComponentProps<typeof Ionicons>['name']; tone: string }) {
  return (
    <View style={[s.badge, { backgroundColor: tone }]}>
      <Ionicons name={name} size={9} color="#0B1220" />
    </View>
  );
}

function PlayerSpot({ p }: { p: LineupPlayer }) {
  const label = p.shortName || p.name;
  // Mốc màu đặt quanh điểm nền 6,0 chứ không đặt ở giữa thang điểm:
  // phần lớn cầu thủ không có chỉ số nào nên đứng đúng 6,0, tô vàng
  // hay đỏ ở mức đó là đang chê người ta vì nguồn thiếu dữ liệu.
  const tone = p.rating == null ? colors.textFaint
    : p.rating >= 7 ? colors.home
      : p.rating >= 6 ? 'rgba(255,255,255,0.86)'
        : colors.card_red;

  // Nguồn thiếu ảnh khá nhiều cầu thủ; ô trống trông như lỗi tải, nên
  // lùi về số áo trên nền đậm — vẫn nhận ra người, không giả vờ có ảnh.
  const [broken, setBroken] = React.useState(false);
  const showPhoto = !!p.photoUrl && !broken;

  return (
    <View style={s.spot}>
      <View style={s.avatarWrap}>
        {showPhoto ? (
          <Image
            source={{ uri: p.photoUrl as string }}
            style={s.avatar}
            resizeMode="cover"
            onError={() => setBroken(true)}
          />
        ) : (
          <View style={[s.avatar, s.avatarBlank]}>
            <Text style={s.avatarJersey}>{p.jersey ?? '–'}</Text>
          </View>
        )}

        {/* Thẻ phạt và mũi tên rời sân nằm ở hai góc trên, giống cách
            các app bóng đá quen thuộc đặt, để liếc là thấy. */}
        {p.redCards > 0 && <View style={[s.corner, s.cornerRight, { backgroundColor: colors.card_red }]} />}
        {p.redCards === 0 && p.yellowCards > 0 && (
          <View style={[s.corner, s.cornerRight, { backgroundColor: colors.card_yellow }]} />
        )}
        {p.subbedOut && <Badge name="arrow-down" tone={colors.card_red} />}
        {p.goals > 0 && (
          <View style={[s.goal]}>
            <Ionicons name="football" size={11} color="#0B1220" />
          </View>
        )}
      </View>

      {p.rating != null && (
        <View style={[s.rating, { backgroundColor: tone }]}>
          <Text style={s.ratingText}>{p.rating.toFixed(1)}</Text>
        </View>
      )}

      {/* Hai dòng và chiều cao cố định: tên dài ("A. Mac Allister") bị
          cắt mất một nửa thì không nhận ra ai, còn để co giãn tự do thì
          các hàng trên sân lệch nhau. */}
      <Text style={s.name} numberOfLines={2}>
        {p.jersey ? `${p.jersey} ` : ''}{label}
      </Text>
    </View>
  );
}

export function LineupPitch({ lineup }: { lineup: TeamLineup }) {
  const rows = buildRows(lineup);
  if (!rows) return null;

  return (
    <View style={s.pitch}>
      {/* Vạch sân: chỉ vẽ những nét người ta thực sự nhận ra sân bóng
          qua đó, thêm nữa chỉ làm rối phía sau các ô cầu thủ. */}
      <View style={s.halfway} />
      <View style={s.circle} />
      <View style={s.box} />
      <View style={s.sixYard} />

      <View style={s.rows}>
        {rows.map((row, ri) => (
          <View key={ri} style={s.row}>
            {row.map((p, pi) => <PlayerSpot key={`${ri}-${pi}`} p={p} />)}
          </View>
        ))}
      </View>
    </View>
  );
}

const PITCH = 'rgba(255,255,255,0.14)';

const s = StyleSheet.create({
  pitch: {
    borderRadius: radius.lg,
    overflow: 'hidden',
    paddingVertical: 14,
    // Xanh đậm thay vì xanh cỏ tươi: nền app tối, một mảng xanh sáng
    // chói mắt và làm ảnh cầu thủ chìm nghỉm.
    backgroundColor: '#12402F',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.07)',
  },
  halfway: {
    position: 'absolute', left: 0, right: 0, top: 0,
    height: 1, backgroundColor: PITCH,
  },
  circle: {
    position: 'absolute', alignSelf: 'center', top: -46,
    width: 92, height: 92, borderRadius: 46,
    borderWidth: 1, borderColor: PITCH,
  },
  box: {
    position: 'absolute', alignSelf: 'center', bottom: -1,
    width: '56%', height: 74,
    borderWidth: 1, borderColor: PITCH, borderBottomWidth: 0,
  },
  sixYard: {
    position: 'absolute', alignSelf: 'center', bottom: -1,
    width: '26%', height: 30,
    borderWidth: 1, borderColor: PITCH, borderBottomWidth: 0,
  },

  rows: { gap: 10 },
  row: { flexDirection: 'row', justifyContent: 'space-evenly', alignItems: 'flex-start' },

  spot: { alignItems: 'center', width: 72 },
  avatarWrap: { width: 38, height: 38 },
  avatar: {
    width: 38, height: 38, borderRadius: 12,
    backgroundColor: 'rgba(0,0,0,0.25)',
  },
  avatarBlank: {
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.22)',
    backgroundColor: 'rgba(0,0,0,0.35)',
    alignItems: 'center', justifyContent: 'center',
  },
  avatarJersey: { ...font.small, color: '#FFFFFF', fontWeight: '900', fontSize: 14 },

  corner: {
    position: 'absolute', width: 9, height: 12, borderRadius: 2,
    top: -3, zIndex: 2,
  },
  cornerRight: { right: -4 },
  badge: {
    position: 'absolute', left: -5, top: -4,
    width: 15, height: 15, borderRadius: 8,
    alignItems: 'center', justifyContent: 'center', zIndex: 2,
  },
  goal: {
    position: 'absolute', right: -5, bottom: -3,
    width: 16, height: 16, borderRadius: 8,
    backgroundColor: '#FFFFFF',
    alignItems: 'center', justifyContent: 'center', zIndex: 2,
  },

  rating: {
    marginTop: -7, paddingHorizontal: 5, paddingVertical: 1,
    borderRadius: 5, zIndex: 3,
  },
  ratingText: { ...font.tiny, color: '#0B1220', fontWeight: '900', fontSize: 10.5 },

  name: {
    ...font.tiny, color: '#FFFFFF', fontSize: 9,
    marginTop: 3, textAlign: 'center', fontWeight: '700',
    lineHeight: 11, height: 22,
  },
});
