/**
 * Danh sách giải đấu và logo của chúng, lấy từ backend.
 *
 * Tải một lần cho cả phiên rồi giữ trong bộ nhớ. Danh sách giải gần như
 * không bao giờ đổi nên không cần làm mới, và backend cũng cache sẵn.
 *
 * Không nhúng cứng đường dẫn ở đây dù chúng có quy luật: để một chỗ duy
 * nhất giữ bản đồ mã giải -> logo (backend/app/providers/sources.py),
 * thêm giải mới chỉ phải sửa một nơi.
 *
 * Riêng các dòng đối đầu thì backend đã gửi kèm logo sẵn trong từng dòng,
 * vì ở đó còn có cả giải cúp vốn không nằm trong danh sách giải chính.
 */
import { useEffect, useState } from 'react';
import { api } from './api';
import type { LeagueDto } from './types';

type LogoMap = Record<string, string>;

let cache: LeagueDto[] | null = null;
let inflight: Promise<LeagueDto[]> | null = null;

async function fetchLeagues(): Promise<LeagueDto[]> {
  if (cache) return cache;
  if (!inflight) {
    inflight = api.leagues()
      .then((list) => { cache = list; return list; })
      .catch(() => {
        // Hỏng thì coi như chưa có danh sách: giao diện tự lùi về danh
        // sách tối thiểu nhúng sẵn, không có màn hình nào chết vì nó.
        cache = [];
        return cache;
      })
      .finally(() => { inflight = null; });
  }
  return inflight;
}

/**
 * Toàn bộ giải backend đang phục vụ.
 *
 * Lấy từ API chứ không nhúng cứng trong app: thêm giải mới chỉ phải sửa
 * một chỗ ở backend, người dùng thấy ngay mà không cần cập nhật app qua
 * cửa hàng. Trả về [] cho tới khi tải xong — bên gọi tự lùi về danh
 * sách tối thiểu.
 */
export function useLeagues(): LeagueDto[] {
  const [list, setList] = useState<LeagueDto[]>(() => cache ?? []);

  useEffect(() => {
    if (cache) return undefined;
    let alive = true;
    void fetchLeagues().then((l) => { if (alive) setList(l); });
    return () => { alive = false; };
  }, []);

  return list;
}

/** Bản đồ mã giải -> logo. Trả về {} cho tới khi tải xong. */
export function useLeagueLogos(): LogoMap {
  const leagues = useLeagues();
  const map: LogoMap = {};
  for (const l of leagues) {
    if (l.logoUrl) map[l.code] = l.logoUrl;
  }
  return map;
}
