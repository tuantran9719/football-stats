/**
 * Context quản lý ngôn ngữ.
 *
 * Lần đầu mở app: đoán theo ngôn ngữ máy, chỉ nhận vi hoặc en, còn lại
 * mặc định tiếng Anh. Người dùng đổi tay thì lưu lại, mở app lần sau
 * dùng đúng lựa chọn đó chứ không đoán lại.
 */
import React, {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from 'react';
import * as Localization from 'expo-localization';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { type Dict, type Lang, LANGUAGES, translations } from './translations';

const STORAGE_KEY = 'football-app:lang';

function isLang(value: unknown): value is Lang {
  return LANGUAGES.some((l) => l.code === value);
}

function detectDeviceLang(): Lang {
  try {
    // Mã máy trả về có thể là 'zh-Hans', 'pt-BR'... nên chỉ so phần đầu.
    const tag = Localization.getLocales()[0]?.languageCode?.slice(0, 2).toLowerCase();
    return isLang(tag) ? tag : 'en';
  } catch {
    return 'en';
  }
}

interface Ctx {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: Dict;
  /** Tên hiển thị của ngôn ngữ hiện tại, dùng cho nhãn nút đổi. */
  ready: boolean;
}

const LangContext = createContext<Ctx | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>('vi');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const saved = await AsyncStorage.getItem(STORAGE_KEY);
        if (isLang(saved)) {
          setLangState(saved);
        } else {
          setLangState(detectDeviceLang());
        }
      } catch {
        setLangState(detectDeviceLang());
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    AsyncStorage.setItem(STORAGE_KEY, l).catch(() => {});
  }, []);

  const value = useMemo<Ctx>(() => ({
    lang, setLang, t: translations[lang], ready,
  }), [lang, setLang, ready]);

  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

/** Hook chính, dùng trong mọi màn hình: const { t, lang, setLang } = useI18n(); */
export function useI18n(): Ctx {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error('useI18n phải được gọi bên trong LanguageProvider');
  return ctx;
}

export type { Lang } from './translations';
