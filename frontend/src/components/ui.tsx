/**
 * Bộ thành phần giao diện dùng chung.
 */
import React from 'react';
import {
  ActivityIndicator, Animated, Image, Modal, Pressable, ScrollView, StyleSheet, Text, View,
  type StyleProp, type ViewStyle,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { colors, font, gradients, radius, shadow, space } from '../theme';

/** Khoảng cách giữa các ô của Segmented. Viên nền trượt phải cộng đúng
 *  con số này vào vị trí, nên để một chỗ thay vì viết rải rác. */
const SEG_GAP = 3;
import { useI18n, type Lang } from '../i18n';
import { LANGUAGES } from '../i18n/translations';

// ------------------------------------------------------------ Chữ

export function Label({ children }: { children: React.ReactNode }) {
  return <Text style={s.label}>{String(children).toUpperCase()}</Text>;
}

// ------------------------------------------------------------ Khối

export function Card({
  children, style, padded = true,
}: { children: React.ReactNode; style?: StyleProp<ViewStyle>; padded?: boolean }) {
  return (
    <View style={[s.card, padded && { padding: space.lg }, style]}>
      <LinearGradient
        colors={gradients.card}
        start={{ x: 0, y: 0 }}
        end={{ x: 0.7, y: 1 }}
        style={StyleSheet.absoluteFill}
        pointerEvents="none"
      />
      {children}
    </View>
  );
}

/** Nền chuyển sắc ở đầu trang, tạo chiều sâu cho toàn màn hình. */
export function HeaderGlow() {
  return (
    <LinearGradient
      colors={gradients.header}
      style={s.glow}
      pointerEvents="none"
    />
  );
}

/**
 * Nút đổi ngôn ngữ ở góc trên bên phải. Từ khi có 12 ngôn ngữ, không còn
 * đủ chỗ cho hai nút VI/EN cạnh nhau nữa, nên nút chỉ hiện mã ngôn ngữ
 * đang dùng và mở bảng chọn đầy đủ khi bấm. Cùng danh sách này còn nằm ở
 * mục Cài đặt trong menu hamburger.
 */
export function LangSwitch() {
  const { lang, setLang, t } = useI18n();
  const [open, setOpen] = React.useState(false);
  const current = LANGUAGES.find((l) => l.code === lang);

  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        style={({ pressed }) => [s.langWrap, s.langBtn, pressed && { opacity: 0.6 }]}
      >
        <Text style={s.langText}>{current?.short ?? lang.toUpperCase()}</Text>
        <Text style={s.langChevron}>▾</Text>
      </Pressable>

      <LanguagePicker
        visible={open}
        onClose={() => setOpen(false)}
        value={lang}
        onChange={setLang}
        title={t.menu.language}
      />
    </>
  );
}

/** Bảng chọn ngôn ngữ dùng chung cho nút góc phải và mục Cài đặt. */
export function LanguagePicker({
  visible, onClose, value, onChange, title,
}: {
  visible: boolean;
  onClose: () => void;
  value: Lang;
  onChange: (l: Lang) => void;
  title: string;
}) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={s.langOverlay} onPress={onClose}>
        <Pressable style={s.langSheet} onPress={(e) => e.stopPropagation()}>
          <Text style={s.langSheetTitle}>{title}</Text>
          <ScrollView showsVerticalScrollIndicator={false}>
            {LANGUAGES.map((l) => {
              const active = l.code === value;
              return (
                <Pressable
                  key={l.code}
                  onPress={() => { onChange(l.code); onClose(); }}
                  style={({ pressed }) => [
                    s.langRow, active && s.langRowActive, pressed && { opacity: 0.7 },
                  ]}
                >
                  <Text style={[s.langRowText, active && s.langRowTextActive]}>{l.label}</Text>
                  {active && <Text style={s.langCheck}>✓</Text>}
                </Pressable>
              );
            })}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

export function Pill({
  text, tone = 'neutral',
}: { text: string; tone?: 'neutral' | 'live' | 'done' | 'accent' }) {
  const map = {
    neutral: { bg: 'rgba(255,255,255,0.07)', fg: colors.textDim, bd: 'transparent' },
    live: { bg: colors.liveSoft, fg: colors.live, bd: 'rgba(255,77,94,0.3)' },
    done: { bg: 'rgba(255,255,255,0.055)', fg: colors.textDim, bd: 'transparent' },
    accent: { bg: colors.accentSoft, fg: colors.accent, bd: colors.accentLine },
  } as const;
  const c = map[tone];
  return (
    <View style={[s.pill, { backgroundColor: c.bg, borderColor: c.bd }]}>
      {tone === 'live' && <View style={s.dot} />}
      <Text style={[s.pillText, { color: c.fg }]}>{text}</Text>
    </View>
  );
}

// ------------------------------------------------------------ Điều khiển

/**
 * Thanh chọn với viên nền trượt mượt theo lựa chọn, thay vì đổi màu đột
 * ngột. Viên nền đo đúng chiều rộng từng lựa chọn qua onLayout của chính
 * nó, nên vẫn đúng dù các nhãn dài ngắn khác nhau.
 */
export function Segmented<T extends string | number>({
  options, value, onChange, wrap,
}: {
  options: ReadonlyArray<{ value: T; label: string }>;
  value: T;
  onChange: (v: T) => void;
  /**
   * Chế độ nhiều lựa chọn: các ô co theo độ dài chữ và tự xuống dòng khi
   * hết chỗ, thay vì chia đều bề ngang.
   *
   * Cần đến nó vì chia đều bốn cột trên màn hình điện thoại làm nhãn dài
   * của tiếng Đức, tiếng Ý bị ngắt dòng giữa chữ. Cách đầu tiên thử là
   * bọc trong ScrollView ngang, nhưng ScrollView ngang lồng trong
   * ScrollView dọc của react-native-web bị co về bề rộng 0 và mất hết
   * chữ — đã dựng thử và chụp lại. Ở chế độ này viên nền trượt cũng bị
   * bỏ: nó dựa vào giả định mọi ô nằm trên một hàng.
   */
  wrap?: boolean;
}) {
  const [widths, setWidths] = React.useState<number[]>(() => options.map(() => 0));
  const pillX = React.useRef(new Animated.Value(0)).current;
  const pillW = React.useRef(new Animated.Value(0)).current;
  const activeIndex = options.findIndex((o) => o.value === value);
  const measured = widths.every((w) => w > 0) && widths.length === options.length;

  React.useEffect(() => {
    if (!measured || activeIndex < 0) return;
    // Cộng cả khoảng cách giữa các ô (gap 3) vào vị trí viên nền, nếu
    // không viên nền lệch dần sang trái ở các lựa chọn phía sau.
    const x = widths.slice(0, activeIndex).reduce((a, b) => a + b, 0) + activeIndex * SEG_GAP;
    Animated.spring(pillX, { toValue: x, useNativeDriver: false, speed: 18, bounciness: 6 }).start();
    Animated.spring(pillW, { toValue: widths[activeIndex]!, useNativeDriver: false, speed: 18, bounciness: 6 }).start();
  }, [activeIndex, measured, widths, pillX, pillW]);

  return (
    <View style={[s.segWrap, wrap && s.segWrapFlow]}>
      {measured && !wrap && (
        <Animated.View
          pointerEvents="none"
          style={[s.segPill, { transform: [{ translateX: pillX }], width: pillW }]}
        >
          <LinearGradient
            colors={gradients.electric}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={StyleSheet.absoluteFill}
          />
        </Animated.View>
      )}
      {options.map((o, i) => {
        const active = o.value === value;
        return (
          <Pressable
            key={String(o.value)}
            onPress={() => onChange(o.value)}
            onLayout={(e) => {
              const w = e.nativeEvent.layout.width;
              setWidths((prev) => {
                if (prev[i] === w) return prev;
                const next = [...prev];
                next[i] = w;
                return next;
              });
            }}
            style={({ pressed }) => [
              s.seg,
              wrap && s.segFlowItem,
              wrap && active && s.segFlowActive,
              pressed && !active && s.segPressed,
            ]}
          >
            <Text style={[s.segText, active && s.segTextActive]} numberOfLines={1}>
              {o.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/**
 * Thanh tab kiểu gạch chân, một hàng.
 *
 * Thay cho cách dùng Segmented (viên nền bo tròn) khi có từ bốn mục trở
 * lên: viên nền chiếm quá nhiều bề ngang, bốn mục không đủ chỗ nên phải
 * xuống dòng và thành lưới 2x2 rời rạc. Chữ trần cộng một vạch trượt
 * bên dưới gọn hơn nhiều và là cách gần như mọi app thể thao đang dùng.
 *
 * Các mục chia đều bề ngang để vạch gạch chân luôn canh đúng giữa nhãn,
 * không phụ thuộc nhãn dài hay ngắn.
 */
export function TabBar<T extends string | number>({
  options, value, onChange,
}: {
  options: ReadonlyArray<{ value: T; label: string }>;
  value: T;
  onChange: (v: T) => void;
}) {
  const [width, setWidth] = React.useState(0);
  const slide = React.useRef(new Animated.Value(0)).current;
  const activeIndex = Math.max(0, options.findIndex((o) => o.value === value));
  const itemW = options.length > 0 ? width / options.length : 0;

  React.useEffect(() => {
    if (itemW <= 0) return;
    Animated.spring(slide, {
      toValue: activeIndex * itemW,
      useNativeDriver: true, speed: 18, bounciness: 6,
    }).start();
  }, [activeIndex, itemW, slide]);

  return (
    <View
      style={s.tabWrap}
      onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
    >
      <View style={s.tabRow}>
        {options.map((o) => {
          const active = o.value === value;
          return (
            <Pressable
              key={String(o.value)}
              onPress={() => onChange(o.value)}
              style={({ pressed }) => [s.tabItem, pressed && !active && { opacity: 0.6 }]}
            >
              <Text
                style={[s.tabText, active && s.tabTextActive]}
                numberOfLines={1}
              >
                {o.label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <View style={s.tabTrack} />
      {itemW > 0 && (
        <Animated.View
          pointerEvents="none"
          style={[s.tabMark, { width: itemW, transform: [{ translateX: slide }] }]}
        >
          <View style={s.tabMarkInner}>
            <LinearGradient
              colors={gradients.electric}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={StyleSheet.absoluteFill}
            />
          </View>
        </Animated.View>
      )}
    </View>
  );
}

export function ChipRow<T extends string>({
  options, value, onChange,
}: {
  options: ReadonlyArray<{ value: T; label: string }>;
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <ScrollView
      horizontal
      style={s.chipScroll}
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={s.chipRow}
    >
      {options.map((o) => {
        const active = o.value === value;
        return (
          <Pressable
            key={o.value}
            onPress={() => onChange(o.value)}
            style={({ pressed }) => [s.chip, active && s.chipActive, pressed && { opacity: 0.65 }]}
          >
            {active && <View style={s.chipDot} />}
            <Text style={[s.chipText, active && s.chipTextActive]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

// ------------------------------------------------------------ Logo

export function TeamLogo({ uri, size = 36 }: { uri?: string; size?: number }) {
  return (
    <View style={[s.logoBox, { width: size, height: size, borderRadius: size / 2.6 }]}>
      {uri ? (
        <Image source={{ uri }} style={{ width: size * 0.78, height: size * 0.78 }} resizeMode="contain" />
      ) : null}
    </View>
  );
}

// ------------------------------------------------------------ Biểu đồ

/** Thanh so sánh hai đội, dài ngắn theo tỉ lệ nên nhìn là biết ai trội. */
export function CompareRow({
  label, home, away, suffix,
}: { label: string; home: number; away: number; suffix?: string }) {
  const total = home + away;
  const hp = total === 0 ? 0 : (home / total) * 100;
  const lead = home === away ? 'draw' : home > away ? 'home' : 'away';
  // Khi cả hai cùng bằng 0 thì không vẽ màu, vì chia đôi hai màu sẽ
  // khiến người xem tưởng có số liệu.
  const empty = total === 0;
  return (
    <View style={s.cmpRow}>
      <View style={s.cmpHead}>
        <Text style={[
          s.cmpVal,
          { color: empty ? colors.textFaint : lead === 'home' ? colors.home : colors.textDim },
        ]}>{home}{suffix}</Text>
        <Text style={s.cmpLabel}>{label}</Text>
        <Text style={[
          s.cmpVal,
          {
            color: empty ? colors.textFaint : lead === 'away' ? colors.away : colors.textDim,
            textAlign: 'right',
          },
        ]}>{away}{suffix}</Text>
      </View>
      <View style={[s.cmpTrack, empty && s.cmpTrackEmpty]}>
        {!empty && (
          <>
            <View style={[s.cmpFill, { width: `${hp}%`, backgroundColor: colors.home }]} />
            <View style={[s.cmpFill, { width: `${100 - hp}%`, backgroundColor: colors.away }]} />
          </>
        )}
      </View>
    </View>
  );
}

/** Biểu đồ cột thể hiện diễn biến qua từng trận. */
export function TrendBars({
  data, tone, formatLabel,
}: {
  data: Array<{ value: number; label: string }>;
  tone: string;
  formatLabel?: (v: number) => string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <View style={s.trend}>
      {data.map((d, i) => {
        const h = Math.max(4, (d.value / max) * 62);
        return (
          <View key={i} style={s.trendCol}>
            <Text style={s.trendValue}>{formatLabel ? formatLabel(d.value) : d.value}</Text>
            <View style={s.trendTrack}>
              <View style={[s.trendBar, { height: h, backgroundColor: tone }]} />
            </View>
            <Text style={s.trendLabel} numberOfLines={1}>{d.label}</Text>
          </View>
        );
      })}
    </View>
  );
}

export function MetricBar({ value, max, tone }: { value: number; max: number; tone: string }) {
  const pct = max <= 0 ? 0 : Math.min(100, (value / max) * 100);
  return (
    <View style={s.metricTrack}>
      <View style={[s.metricFill, { width: `${pct}%`, backgroundColor: tone }]} />
    </View>
  );
}

// ------------------------------------------------------------ Chuyển động

/**
 * Bọc quanh một phần tử để nó mờ dần và trượt nhẹ lên khi xuất hiện.
 * Đặt `index` theo thứ tự trong danh sách để tạo hiệu ứng so le, nhìn tự
 * nhiên hơn nhiều so với việc cả danh sách hiện ra cùng lúc.
 */
export function Reveal({
  children, index = 0, style,
}: { children: React.ReactNode; index?: number; style?: StyleProp<ViewStyle> }) {
  const fade = React.useRef(new Animated.Value(0)).current;
  const slide = React.useRef(new Animated.Value(12)).current;

  React.useEffect(() => {
    const delay = Math.min(index, 10) * 45;
    Animated.parallel([
      Animated.timing(fade, { toValue: 1, duration: 320, delay, useNativeDriver: true }),
      Animated.timing(slide, { toValue: 0, duration: 320, delay, useNativeDriver: true }),
    ]).start();
  }, [fade, slide, index]);

  return (
    <Animated.View style={[{ opacity: fade, transform: [{ translateY: slide }] }, style]}>
      {children}
    </Animated.View>
  );
}

/**
 * Pressable co nhẹ lại khi nhấn giữ, tạo cảm giác bấm thật thay vì chỉ đổi
 * độ mờ. Dùng cho mọi thẻ có thể chạm trong app.
 */
export function PressScale({
  children, onPress, style, onLongPress, disabled,
}: {
  children: React.ReactNode; onPress?: () => void; onLongPress?: () => void;
  style?: StyleProp<ViewStyle>; disabled?: boolean;
}) {
  const scale = React.useRef(new Animated.Value(1)).current;
  const onIn = () => Animated.spring(scale, { toValue: 0.97, useNativeDriver: true, speed: 40, bounciness: 0 }).start();
  const onOut = () => Animated.spring(scale, { toValue: 1, useNativeDriver: true, speed: 14, bounciness: 6 }).start();

  return (
    <Pressable
      onPress={onPress} onLongPress={onLongPress}
      onPressIn={onIn} onPressOut={onOut} disabled={disabled}
    >
      <Animated.View style={[{ transform: [{ scale }] }, style]}>
        {children}
      </Animated.View>
    </Pressable>
  );
}

// ------------------------------------------------------------ Trạng thái

export function Loading({ text }: { text?: string }) {
  const { t } = useI18n();
  return (
    <View style={s.center}>
      <ActivityIndicator color={colors.accent} size="large" />
      <Text style={s.centerText}>{text ?? t.common.loading}</Text>
    </View>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <Card style={{ gap: space.md }}>
      <Text style={s.errTitle}>{t.common.loadFailed}</Text>
      <Text style={s.centerText}>{message}</Text>
      {onRetry && (
        <Pressable onPress={onRetry} style={({ pressed }) => [s.retry, pressed && { opacity: 0.75 }]}>
          <LinearGradient
            colors={gradients.electric}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={StyleSheet.absoluteFill}
          />
          <Text style={s.retryText}>{t.common.retry}</Text>
        </Pressable>
      )}
    </Card>
  );
}

export function Empty({ text }: { text: string }) {
  return <View style={s.center}><Text style={s.centerText}>{text}</Text></View>;
}

export function NoData({ hint }: { hint?: string }) {
  const { t } = useI18n();
  return (
    <View style={s.noData}>
      <Text style={s.noDataText}>{t.common.noData}</Text>
      {hint ? <Text style={s.noDataHint}>{hint}</Text> : null}
    </View>
  );
}

const s = StyleSheet.create({
  label: { ...font.label, color: colors.textFaint },

  card: {
    position: 'relative',
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    overflow: 'hidden',
    ...shadow.card,
  },
  glow: { position: 'absolute', top: 0, left: 0, right: 0, height: 260 },

  pill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 9, paddingVertical: 4.5,
    borderRadius: radius.pill, borderWidth: 1,
  },
  pillText: { ...font.label, fontSize: 9.5 },
  dot: { width: 5, height: 5, borderRadius: 3, backgroundColor: colors.live },

  segWrap: {
    position: 'relative',
    flexDirection: 'row', backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: radius.pill, padding: 4, gap: SEG_GAP,
    borderWidth: 1, borderColor: colors.hairline,
  },
  segWrapFlow: { flexWrap: 'wrap', gap: 4 },
  segPill: {
    position: 'absolute', top: 4, bottom: 4, left: 0,
    borderRadius: radius.pill, overflow: 'hidden',
    ...shadow.card, shadowOpacity: 0.25, shadowColor: colors.accent,
  },
  seg: { flex: 1, paddingVertical: 10, alignItems: 'center', borderRadius: radius.pill },
  // Lưới đều thay vì để các ô co theo chữ.
  //
  // Co theo chữ thì bốn lựa chọn xếp thành 3 + 1, ô cuối nằm trơ một
  // mình bên trái và trông như lỗi hiển thị. flexBasis 40% cộng
  // flexGrow 1 ép đúng hai ô mỗi hàng rồi giãn đều ra — thành lưới 2x2
  // cân đối, và vẫn đúng với mọi ngôn ngữ dù nhãn dài ngắn khác nhau.
  //
  // KHÔNG dùng flex: 0 ở đây: trong React Native nó đặt luôn
  // flexBasis: 0% nên ô co về bề rộng 0, chỉ còn lại padding — đã đo
  // được đúng 28px với nhãn biến mất hoàn toàn.
  segFlowItem: {
    flexGrow: 1, flexShrink: 1, flexBasis: '40%',
    paddingHorizontal: 10, paddingVertical: 9,
  },
  // Không có viên nền trượt ở chế độ xuống dòng nên ô đang chọn tự tô nền.
  segFlowActive: { backgroundColor: colors.accent },
  segPressed: { backgroundColor: 'rgba(255,255,255,0.05)' },

  // Thanh tab gạch chân
  tabWrap: { position: 'relative' },
  tabRow: { flexDirection: 'row' },
  tabItem: { flex: 1, alignItems: 'center', paddingVertical: 11, paddingHorizontal: 2 },
  tabText: { ...font.small, color: colors.textDim, fontWeight: '700' },
  tabTextActive: { color: colors.text, fontWeight: '800' },
  tabTrack: { height: 1, backgroundColor: colors.hairline },
  // Vạch trượt: chiếm trọn bề ngang một mục, phần tô màu thu hẹp vào
  // giữa để trông cân với nhãn thay vì kéo dài sát mép.
  tabMark: { position: 'absolute', left: 0, bottom: 0, height: 2.5, alignItems: 'center' },
  tabMarkInner: {
    width: '58%', height: 2.5, borderRadius: 2, overflow: 'hidden',
  },
  segText: { ...font.h2, color: colors.textDim },
  segTextActive: { color: '#00230F', fontWeight: '800' },

  // Không có style này, ScrollView ngang trên web tự co chiều cao xuống
  // gần như 0 (đã đo thực tế chỉ còn 9.7px) và cắt mất chữ bên trong.
  chipScroll: { flexGrow: 0, flexShrink: 0, width: '100%' },
  chipRow: { gap: space.sm, paddingHorizontal: space.lg, paddingVertical: space.sm },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 7,
    paddingHorizontal: 14, paddingVertical: 9, borderRadius: radius.sm,
    backgroundColor: 'rgba(255,255,255,0.045)',
    borderWidth: 1, borderColor: colors.hairline,
  },
  chipActive: { backgroundColor: colors.accentSoft, borderColor: colors.accentLine },
  chipDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.accent },
  chipText: { ...font.small, color: colors.textDim },
  chipTextActive: { color: colors.accent, fontWeight: '800' },

  logoBox: {
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.06)',
  },

  cmpRow: { gap: 7 },
  cmpHead: { flexDirection: 'row', alignItems: 'center' },
  cmpVal: { ...font.h2, fontSize: 16, width: 50 },
  cmpLabel: { ...font.tiny, color: colors.textDim, flex: 1, textAlign: 'center' },
  cmpTrack: { flexDirection: 'row', height: 7, borderRadius: 4, overflow: 'hidden', gap: 2 },
  cmpTrackEmpty: { backgroundColor: 'rgba(255,255,255,0.05)' },
  cmpFill: { height: '100%', borderRadius: 4 },

  trend: { flexDirection: 'row', alignItems: 'flex-end', gap: 6, height: 104 },
  trendCol: { flex: 1, alignItems: 'center', gap: 5 },
  trendValue: { ...font.tiny, color: colors.textSoft, fontSize: 10.5 },
  trendTrack: { height: 62, justifyContent: 'flex-end' },
  trendBar: { width: 20, borderRadius: 5 },
  trendLabel: { fontSize: 9, color: colors.textFaint, fontWeight: '600' },

  metricTrack: { height: 7, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.06)', overflow: 'hidden' },
  metricFill: { height: '100%', borderRadius: 4 },

  center: { alignItems: 'center', justifyContent: 'center', padding: space.xxl, gap: space.md },
  centerText: { ...font.small, color: colors.textDim, textAlign: 'center' },
  errTitle: { ...font.h2, color: colors.text },
  retry: {
    position: 'relative', overflow: 'hidden',
    alignSelf: 'flex-start', paddingHorizontal: space.xl, paddingVertical: space.md,
    borderRadius: radius.pill,
  },
  retryText: { ...font.h2, color: '#00230F', fontWeight: '800' },

  langWrap: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: radius.pill,
    borderWidth: 1, borderColor: colors.hairline,
  },
  langBtn: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: radius.pill },
  langText: { fontSize: 10.5, fontWeight: '800', color: colors.textSoft, letterSpacing: 0.4 },
  langChevron: { fontSize: 9, color: colors.textFaint, marginTop: 1 },

  langOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.6)',
    alignItems: 'center', justifyContent: 'center', padding: space.xl,
  },
  langSheet: {
    width: '100%', maxWidth: 340, maxHeight: '75%',
    backgroundColor: colors.bgElev,
    borderRadius: radius.xl,
    borderWidth: 1, borderColor: colors.border,
    padding: space.md,
    ...shadow.card,
  },
  langSheetTitle: {
    ...font.h2, color: colors.text,
    paddingHorizontal: space.sm, paddingVertical: space.sm,
  },
  langRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: space.md, paddingVertical: 12,
    borderRadius: radius.md,
  },
  langRowActive: { backgroundColor: colors.accentSoft },
  langRowText: { ...font.body, color: colors.textSoft, fontSize: 14.5 },
  langRowTextActive: { color: colors.accent, fontWeight: '800' },
  langCheck: { color: colors.accent, fontSize: 15, fontWeight: '800' },

  noData: { gap: 3, paddingVertical: 2 },
  noDataText: { ...font.small, color: colors.textFaint, fontStyle: 'italic' },
  noDataHint: { fontSize: 10.5, color: colors.textFaint, opacity: 0.8, lineHeight: 15 },
});
