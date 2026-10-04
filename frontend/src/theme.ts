/**
 * Hệ thống thiết kế.
 *
 * Định hướng: tối, sâu, nhiều tầng. Số liệu là nhân vật chính nên được
 * đặt ở cỡ lớn và tương phản cao, mọi thứ khác lùi về sau.
 *
 * Theme "Xanh dương điện" — hướng lạnh, sắc nét, gần với phong cách đồ
 * hoạ truyền hình thể thao (Sky Sports, ESPN). Chọn sau khi so sánh trực
 * tiếp ba hướng màu trên app thật.
 */
export const colors = {
  // Nền lạnh, ngả xanh dương đậm thay vì xanh lục.
  bg: '#05070D',
  bgElev: '#0A0F1C',
  card: '#0E1526',
  cardHi: '#141D33',
  cardPressed: '#1A2540',

  // Viền
  hairline: 'rgba(255,255,255,0.06)',
  border: 'rgba(255,255,255,0.10)',
  borderBright: 'rgba(255,255,255,0.18)',

  // Chữ
  text: '#FFFFFF',
  textSoft: '#C7D0E8',
  textDim: '#8590B5',
  textFaint: '#4A5478',

  // Nhấn — xanh dương điện ghép tím, phong cách đồ hoạ truyền hình thể thao.
  accent: '#2E7BFF',
  accent2: '#7C5CFF',
  accentSoft: 'rgba(46,123,255,0.14)',
  accentLine: 'rgba(46,123,255,0.35)',

  // Đội nhà và đội khách. Đội nhà dùng xanh ngọc để không trùng với màu
  // nhấn xanh dương của theme này (trước đây home vốn cũng là xanh dương).
  home: '#2DD4BF',
  homeSoft: 'rgba(45,212,191,0.16)',
  away: '#FFB020',
  awaySoft: 'rgba(255,176,32,0.16)',

  // Trạng thái và thẻ phạt
  live: '#FF4D5E',
  liveSoft: 'rgba(255,77,94,0.15)',
  card_yellow: '#FFCE38',
  card_red: '#FF4D5E',
  purple: '#A98BFF',

  // Bề mặt kính mờ (glass), dùng với expo-blur cho thanh tab nổi và các
  // lớp phủ nổi trên nội dung.
  glassTint: 'rgba(10,15,28,0.6)',
  glassBorder: 'rgba(255,255,255,0.12)',
} as const;

/** Dải màu dùng cho nền đầu trang và các điểm nhấn gradient. */
export const gradients = {
  header: ['#16224A', '#0A1226', '#05070D'] as const,
  card: ['rgba(255,255,255,0.05)', 'rgba(255,255,255,0.012)'] as const,
  accent: ['#2E7BFF', '#245FCC'] as const,
  // Gradient "điện" hai tông xanh dương–tím.
  electric: ['#2E7BFF', '#7C5CFF'] as const,
};

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 22, xxl: 30 } as const;
export const radius = { sm: 10, md: 14, lg: 18, xl: 24, pill: 999 } as const;

export const font = {
  display: { fontSize: 30, fontWeight: '800' as const, letterSpacing: -0.8 },
  title: { fontSize: 21, fontWeight: '800' as const, letterSpacing: -0.4 },
  score: { fontSize: 28, fontWeight: '800' as const, letterSpacing: -1 },
  stat: { fontSize: 23, fontWeight: '800' as const, letterSpacing: -0.6 },
  h2: { fontSize: 15, fontWeight: '700' as const, letterSpacing: -0.1 },
  body: { fontSize: 14, fontWeight: '600' as const },
  small: { fontSize: 12.5, fontWeight: '600' as const },
  tiny: { fontSize: 11, fontWeight: '600' as const },
  label: { fontSize: 10, fontWeight: '800' as const, letterSpacing: 1.3 },
} as const;

/** Bóng đổ nhẹ, dùng cho thẻ nổi. */
export const shadow = {
  card: {
    shadowColor: '#000',
    shadowOpacity: 0.35,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 6 },
    elevation: 6,
  },
} as const;
