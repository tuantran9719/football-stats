/**
 * Vẽ thẻ tỉ số thành ảnh để chia sẻ.
 *
 * Vẽ thẳng lên canvas chứ không chụp màn hình giao diện. Ba lý do:
 *   - Ảnh ra đúng kích thước mạng xã hội cần (1080 rộng), không phụ
 *     thuộc màn hình người dùng đang to hay nhỏ.
 *   - Bố cục riêng cho ảnh vuông và ảnh dọc, không phải bản thu nhỏ của
 *     giao diện vốn thiết kế cho việc cuộn.
 *   - Không thêm thư viện chụp màn hình nào.
 *
 * CHỈ CHẠY TRÊN WEB. Bản chạy trên điện thoại (native) không có canvas
 * của trình duyệt; khi nào đóng gói lên store thì thay phần này bằng
 * react-native-view-shot, phần dữ liệu và bố cục bên dưới giữ nguyên.
 *
 * Ảnh logo của ESPN có Access-Control-Allow-Origin: * (đã kiểm chứng)
 * nên vẽ lên canvas không làm canvas bị "nhiễm" và vẫn xuất ra được.
 */

export type ShareFormat = 'story' | 'square';

export interface ShareCardData {
  leagueName: string;
  leagueLogoUrl?: string | null;
  kickoffUtc: string;
  status: string;
  homeName: string;
  homeShort?: string | null;
  homeLogoUrl?: string | null;
  awayName: string;
  awayShort?: string | null;
  awayLogoUrl?: string | null;
  homeScore?: number | null;
  awayScore?: number | null;
  /** Tỉ số hiệp một, hiện dưới tỉ số chính khi có. */
  htHome?: number | null;
  htAway?: number | null;
  /** Ba ô số liệu dưới cùng. Trận chưa đá thì là con số kỳ vọng. */
  stats: Array<{ label: string; value: string }>;
  /** Dòng nhỏ nhất dưới cùng, ví dụ "Số liệu tham khảo". */
  note?: string;
}

const W = 1080;
const H = { story: 1920, square: 1080 } as const;

const FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

/** Màu lấy từ theme để ảnh và app nhìn là một. */
const C = {
  bg0: '#0B1226',
  bg1: '#05070D',
  text: '#FFFFFF',
  soft: '#C7D0E8',
  dim: '#8590B5',
  faint: '#4A5478',
  accent: '#2E7BFF',
  accent2: '#7C5CFF',
  line: 'rgba(255,255,255,0.10)',
  card: 'rgba(255,255,255,0.045)',
};

function roundRect(
  ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number,
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/**
 * Tải ảnh cho canvas. Trả về null thay vì ném lỗi: thiếu một cái logo
 * thì bỏ trống chỗ đó, không được làm hỏng cả tấm ảnh.
 */
function loadImage(url?: string | null): Promise<HTMLImageElement | null> {
  if (!url) return Promise.resolve(null);
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = url;
  });
}

function drawImageFit(
  ctx: CanvasRenderingContext2D, img: HTMLImageElement | null,
  cx: number, cy: number, box: number,
) {
  if (!img) return;
  const scale = Math.min(box / img.width, box / img.height);
  const w = img.width * scale;
  const h = img.height * scale;
  ctx.drawImage(img, cx - w / 2, cy - h / 2, w, h);
}

function text(
  ctx: CanvasRenderingContext2D, value: string,
  x: number, y: number,
  size: number, weight: number, color: string,
  align: CanvasTextAlign = 'center', spacing = 0,
) {
  ctx.fillStyle = color;
  ctx.font = `${weight} ${size}px ${FONT}`;
  ctx.textAlign = align;
  ctx.textBaseline = 'alphabetic';
  if (spacing !== 0 && 'letterSpacing' in ctx) {
    (ctx as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing = `${spacing}px`;
  }
  ctx.fillText(value, x, y);
  if (spacing !== 0 && 'letterSpacing' in ctx) {
    (ctx as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing = '0px';
  }
}

/** Thu nhỏ cỡ chữ cho tới khi tên đội vừa bề ngang cho phép. */
function fitText(
  ctx: CanvasRenderingContext2D, value: string, maxW: number,
  start: number, weight: number,
): number {
  let size = start;
  while (size > 22) {
    ctx.font = `${weight} ${size}px ${FONT}`;
    if (ctx.measureText(value).width <= maxW) break;
    size -= 2;
  }
  return size;
}

export async function drawShareCard(
  data: ShareCardData, format: ShareFormat,
): Promise<Blob> {
  const h = H[format];
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Trình duyệt không hỗ trợ canvas');

  // ---- Nền: dốc màu chéo cộng một quầng sáng phía sau tỉ số, để khối
  // tỉ số nổi lên mà không cần khung viền.
  const bg = ctx.createLinearGradient(0, 0, W, h);
  bg.addColorStop(0, C.bg0);
  bg.addColorStop(1, C.bg1);
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, h);

  const midY = format === 'story' ? h * 0.42 : h * 0.44;
  const glow = ctx.createRadialGradient(W / 2, midY, 0, W / 2, midY, W * 0.75);
  glow.addColorStop(0, 'rgba(46,123,255,0.20)');
  glow.addColorStop(1, 'rgba(46,123,255,0)');
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, W, h);

  const [leagueImg, homeImg, awayImg] = await Promise.all([
    loadImage(data.leagueLogoUrl),
    loadImage(data.homeLogoUrl),
    loadImage(data.awayLogoUrl),
  ]);

  const pad = 80;
  const topY = format === 'story' ? 250 : 130;

  // ---- Hàng giải đấu
  const leagueSize = 52;
  ctx.font = `800 30px ${FONT}`;
  const nameW = ctx.measureText(data.leagueName.toUpperCase()).width;
  const rowW = (leagueImg ? leagueSize + 18 : 0) + nameW;
  let cursor = W / 2 - rowW / 2;
  if (leagueImg) {
    drawImageFit(ctx, leagueImg, cursor + leagueSize / 2, topY - 10, leagueSize);
    cursor += leagueSize + 18;
  }
  text(ctx, data.leagueName.toUpperCase(), cursor, topY, 30, 800, C.accent, 'left', 2);

  const when = new Date(data.kickoffUtc);
  const dd = String(when.getDate()).padStart(2, '0');
  const mm = String(when.getMonth() + 1).padStart(2, '0');
  const hh = String(when.getHours()).padStart(2, '0');
  const mi = String(when.getMinutes()).padStart(2, '0');
  text(ctx, `${dd}/${mm}/${when.getFullYear()} · ${hh}:${mi}`, W / 2, topY + 52, 28, 600, C.dim);

  // ---- Khối tỉ số
  const logoBox = format === 'story' ? 190 : 150;
  const sideX = format === 'story' ? 232 : 220;
  const logoY = midY - (format === 'story' ? 60 : 40);

  drawImageFit(ctx, homeImg, sideX, logoY, logoBox);
  drawImageFit(ctx, awayImg, W - sideX, logoY, logoBox);

  const played = data.homeScore !== null && data.homeScore !== undefined
    && data.awayScore !== null && data.awayScore !== undefined;
  const scoreText = played ? `${data.homeScore} - ${data.awayScore}` : 'VS';
  const scoreSize = format === 'story' ? 130 : 108;
  text(ctx, scoreText, W / 2, logoY + scoreSize * 0.35, scoreSize, 900, C.text);

  if (played && data.htHome !== null && data.htHome !== undefined
      && data.htAway !== null && data.htAway !== undefined) {
    text(ctx, `HT ${data.htHome}-${data.htAway}`, W / 2, logoY + scoreSize * 0.35 + 46, 28, 700, C.faint);
  }

  // Tên đội đặt dưới logo, tự thu nhỏ nếu dài.
  const nameY = logoY + logoBox / 2 + 62;
  const maxNameW = sideX * 1.75;
  const hName = data.homeName;
  const aName = data.awayName;
  const hSize = fitText(ctx, hName, maxNameW, 38, 800);
  const aSize = fitText(ctx, aName, maxNameW, 38, 800);
  text(ctx, hName, sideX, nameY, hSize, 800, C.text);
  text(ctx, aName, W - sideX, nameY, aSize, 800, C.text);

  // ---- Dải số liệu
  const boxH = format === 'story' ? 210 : 170;
  // Ảnh vuông thấp hơn nhiều nên dải số liệu phải lên cao hơn theo tỉ
  // lệ, nếu không nó chạm vào chữ hiệu ở đáy.
  const boxY = format === 'story' ? h * 0.66 : h * 0.63;
  roundRect(ctx, pad, boxY, W - pad * 2, boxH, 36);
  ctx.fillStyle = C.card;
  ctx.fill();
  ctx.strokeStyle = C.line;
  ctx.lineWidth = 2;
  ctx.stroke();

  const cells = data.stats.slice(0, 3);
  const cellW = (W - pad * 2) / Math.max(1, cells.length);
  cells.forEach((cell, i) => {
    const cx = pad + cellW * i + cellW / 2;
    text(ctx, cell.value, cx, boxY + boxH * 0.52, format === 'story' ? 62 : 54, 900, C.text);
    text(ctx, cell.label.toUpperCase(), cx, boxY + boxH * 0.80, 24, 700, C.dim, 'center', 1.5);
    if (i > 0) {
      ctx.strokeStyle = C.line;
      ctx.beginPath();
      ctx.moveTo(pad + cellW * i, boxY + 36);
      ctx.lineTo(pad + cellW * i, boxY + boxH - 36);
      ctx.stroke();
    }
  });

  if (data.note) {
    text(ctx, data.note, W / 2, boxY + boxH + 52, 24, 500, C.faint);
  }

  // ---- Chữ hiệu dưới cùng: khung bo tròn gradient với ba cột tăng dần,
  // đúng logo trong app.
  const brandY = h - (format === 'story' ? 150 : 96);
  const markSize = 54;
  ctx.font = `900 40px ${FONT}`;
  const wordW = ctx.measureText('Football Stats').width;
  const brandW = markSize + 20 + wordW;
  let bx = W / 2 - brandW / 2;

  const markGrad = ctx.createLinearGradient(bx, brandY - markSize, bx + markSize, brandY);
  markGrad.addColorStop(0, C.accent);
  markGrad.addColorStop(1, C.accent2);
  roundRect(ctx, bx, brandY - markSize, markSize, markSize, markSize * 0.29);
  ctx.fillStyle = markGrad;
  ctx.fill();

  const barPad = markSize * 0.24;
  const barGap = markSize * 0.09;
  const barW = (markSize - barPad * 2 - barGap * 2) / 3;
  [0.3, 0.55, 0.82].forEach((frac, i) => {
    const bh = (markSize - barPad * 2) * frac;
    const bxx = bx + barPad + (barW + barGap) * i;
    ctx.globalAlpha = 0.62 + i * 0.19;
    roundRect(ctx, bxx, brandY - barPad - bh, barW, bh, barW / 2);
    ctx.fillStyle = '#FFFFFF';
    ctx.fill();
  });
  ctx.globalAlpha = 1;

  bx += markSize + 20;
  ctx.font = `900 40px ${FONT}`;
  ctx.textAlign = 'left';
  ctx.fillStyle = C.text;
  ctx.fillText('Football', bx, brandY - 8);
  const fw = ctx.measureText('Football').width;
  ctx.fillStyle = C.accent;
  ctx.fillText(' Stats', bx + fw, brandY - 8);

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('Không tạo được ảnh'))),
      'image/png',
    );
  });
}
