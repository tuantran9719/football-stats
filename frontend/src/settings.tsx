/**
 * Tuỳ chọn của người dùng, lưu ngay trên máy.
 *
 * Hai mục: bật/tắt phần vạch thị trường, và ghi nhớ thẻ chỉ số trước
 * trận đang mở hay đang gập.
 *
 * Vạch thị trường MẶC ĐỊNH TẮT, và đó là một quyết định có chủ đích
 * chứ không phải sở thích. Bảng phân loại độ tuổi của App Store xếp "đặt cược bằng tiền
 * thật" vào 18+, còn nội dung liên quan tới cá cược nhưng không cho đặt
 * tiền thì rơi vào nhóm nhẹ hơn (Sofascore đang là 13+ với nhãn
 * "Infrequent Simulated Gambling"). Để mặc định tắt thì bản app lúc xuất
 * xưởng không có nội dung cá cược nào, ai cần mới tự bật — khai báo lúc
 * nộp store cũng sạch sẽ hơn.
 *
 * Lưu ý cho người sửa sau: đừng bao giờ thêm đường dẫn sang nhà cái vào
 * phần này. ESPN có gửi kèm link đặt cược trong dữ liệu vạch kèo nhưng
 * backend đã lọc bỏ; có link là app bị xếp vào nhóm cờ bạc tiền thật,
 * kéo theo yêu cầu giấy phép ở từng quốc gia.
 */
import React, {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = 'football-app:settings';

interface Settings {
  showOdds: boolean;
  /** Thẻ chỉ số trước trận đang mở hay đang gập. */
  insightsOpen: boolean;
}

const DEFAULTS: Settings = { showOdds: false, insightsOpen: true };

interface Ctx extends Settings {
  setShowOdds: (v: boolean) => void;
  setInsightsOpen: (v: boolean) => void;
  ready: boolean;
}

const SettingsContext = createContext<Ctx | null>(null);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<Settings>(DEFAULTS);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const saved = await AsyncStorage.getItem(STORAGE_KEY);
        if (saved) setSettings({ ...DEFAULTS, ...JSON.parse(saved) });
      } catch {
        // Hỏng thì dùng mặc định, không cần báo gì.
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const patch = useCallback((change: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...change };
      AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next)).catch(() => {});
      return next;
    });
  }, []);

  const setShowOdds = useCallback((v: boolean) => patch({ showOdds: v }), [patch]);
  const setInsightsOpen = useCallback((v: boolean) => patch({ insightsOpen: v }), [patch]);

  const value = useMemo<Ctx>(
    () => ({ ...settings, setShowOdds, setInsightsOpen, ready }),
    [settings, setShowOdds, setInsightsOpen, ready],
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): Ctx {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings phải được gọi bên trong SettingsProvider');
  return ctx;
}
