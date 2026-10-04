/**
 * Vòng lặp cập nhật tỉ số trực tiếp.
 *
 * Nguyên tắc: chỉ hỏi khi có cái để hỏi. ESPN là API không chính thức,
 * gọi dày là ăn 429 cho cả IP, nên vòng lặp này tự tắt trong ba trường
 * hợp và không có cách nào bật lại ngoài ba điều kiện đó:
 *
 *   1. Danh sách đang xem không có trận nào đang đá và cũng không có
 *      trận nào sắp bắt đầu. Đêm khuya mở app thì không có lượt gọi nào.
 *   2. App bị đưa xuống nền hoặc tab trình duyệt bị ẩn. Điện thoại nằm
 *      trong túi thì không việc gì phải cập nhật.
 *   3. Màn hình bị gỡ hoặc người dùng đổi giải — lượt đang bay bị hủy.
 *
 * Nhịp hỏi do server quyết định qua pollAfterSeconds chứ không cố định ở
 * client, để sau này muốn giãn nhịp lúc tải cao thì sửa một chỗ.
 */
import { useEffect, useRef } from 'react';
import { AppState } from 'react-native';
import { api } from './api';
import type { LiveMatch, Match } from './types';

/** Bắt đầu theo dõi từ trước giờ bóng lăn chừng này, để bắt được lúc
 *  trận chuyển sang đang đá mà không cần người dùng làm mới tay. */
const LEAD_MS = 10 * 60 * 1000;
/** Trận quá giờ bóng lăn nhưng ESPN còn ghi "chưa đá" thì vẫn theo dõi
 *  trong khoảng này — độ trễ cập nhật trạng thái bên ESPN. */
const LAG_MS = 30 * 60 * 1000;

const NEVER_FASTER_THAN = 10;

export function isLiveStatus(s: Match['status']): boolean {
  return s === 'live' || s === 'halftime';
}

/** Có đáng để chạy vòng lặp không. Tách riêng để test được bằng tay. */
export function shouldPoll(matches: Match[] | null | undefined): boolean {
  if (!matches || matches.length === 0) return false;
  const now = Date.now();
  return matches.some((m) => {
    if (isLiveStatus(m.status)) return true;
    if (m.status !== 'scheduled') return false;
    const untilKickoff = new Date(m.kickoffUtc).getTime() - now;
    return untilKickoff < LEAD_MS && untilKickoff > -LAG_MS;
  });
}

export function useLiveScores(
  league: string,
  matches: Match[] | null,
  onUpdate: (updates: Map<string, LiveMatch>) => void,
): void {
  // Giữ callback trong ref: màn hình tạo hàm mới mỗi lần render, nếu đưa
  // thẳng vào mảng phụ thuộc thì vòng lặp bị dựng lại liên tục và nhịp
  // hỏi mất kiểm soát.
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const active = shouldPoll(matches);

  useEffect(() => {
    if (!active) return undefined;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const ctrl = new AbortController();

    const schedule = (seconds: number) => {
      if (cancelled) return;
      timer = setTimeout(() => { void tick(); }, Math.max(NEVER_FASTER_THAN, seconds) * 1000);
    };

    const tick = async () => {
      if (cancelled) return;
      if (AppState.currentState !== 'active') {
        // Không gọi mạng khi đang ở nền; chỉ ngó lại sau một lúc phòng
        // khi sự kiện quay lại tiền cảnh không bắn (một số trình duyệt).
        schedule(60);
        return;
      }
      try {
        const res = await api.live(league, ctrl.signal);
        if (cancelled) return;
        onUpdateRef.current(new Map(res.matches.map((m) => [m.id, m])));
        schedule(res.pollAfterSeconds);
      } catch {
        // Mạng chập hoặc server đang bị ESPN chặn: lùi lại một nhịp dài
        // thay vì thử lại ngay, và tuyệt đối không hiện lỗi ra màn hình —
        // dữ liệu cũ vẫn đang hiển thị bình thường.
        schedule(60);
      }
    };

    // Lần hỏi đầu tiên vẫn chờ hết một nhịp: dữ liệu vừa được tải xong
    // ngay trước đó nên hỏi lại lập tức là thừa.
    schedule(20);

    // Quay lại từ nền thì cập nhật ngay, đừng bắt người dùng chờ hết nhịp.
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active' && !cancelled) {
        if (timer) clearTimeout(timer);
        void tick();
      }
    });

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      ctrl.abort();
      sub.remove();
    };
  }, [active, league]);
}

/** Ghép bản cập nhật gọn vào danh sách đầy đủ. Trả về chính mảng cũ khi
 *  không có gì đổi, để React bỏ qua được lần render thừa. */
export function mergeLive(
  list: Match[] | null, updates: Map<string, LiveMatch>,
): Match[] | null {
  if (!list) return list;
  let changed = false;
  const next = list.map((m) => {
    const u = updates.get(m.id);
    if (!u) return m;
    const same = u.status === m.status
      && u.clock === (m.clock ?? null)
      && (u.score?.home ?? null) === (m.score?.home ?? null)
      && (u.score?.away ?? null) === (m.score?.away ?? null);
    if (same) return m;
    changed = true;
    return { ...m, status: u.status, score: u.score, clock: u.clock, period: u.period };
  });
  return changed ? next : list;
}
