/**
 * Context quản lý đội bóng yêu thích.
 *
 * Lưu ngay trên máy (AsyncStorage), không cần tài khoản hay backend. Trận
 * của đội yêu thích được ưu tiên lên đầu danh sách trên trang chính, và có
 * thể lọc riêng chỉ xem trận của các đội đã chọn.
 */
import React, {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = 'football-app:favorites';

export interface FavTeam {
  id: string;
  name: string;
  logoUrl?: string;
}

interface Ctx {
  favorites: FavTeam[];
  isFavorite: (id: string) => boolean;
  toggleFavorite: (team: FavTeam) => void;
  ready: boolean;
}

const FavoritesContext = createContext<Ctx | null>(null);

export function FavoritesProvider({ children }: { children: React.ReactNode }) {
  const [map, setMap] = useState<Record<string, FavTeam>>({});
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const saved = await AsyncStorage.getItem(STORAGE_KEY);
        if (saved) setMap(JSON.parse(saved));
      } catch {
        // bỏ qua, coi như chưa có đội yêu thích nào
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const toggleFavorite = useCallback((team: FavTeam) => {
    setMap((prev) => {
      const next = { ...prev };
      if (next[team.id]) {
        delete next[team.id];
      } else {
        next[team.id] = team;
      }
      AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next)).catch(() => {});
      return next;
    });
  }, []);

  const isFavorite = useCallback((id: string) => Boolean(map[id]), [map]);

  const value = useMemo<Ctx>(() => ({
    favorites: Object.values(map),
    isFavorite,
    toggleFavorite,
    ready,
  }), [map, isFavorite, toggleFavorite, ready]);

  return <FavoritesContext.Provider value={value}>{children}</FavoritesContext.Provider>;
}

export function useFavorites(): Ctx {
  const ctx = useContext(FavoritesContext);
  if (!ctx) throw new Error('useFavorites phải được gọi bên trong FavoritesProvider');
  return ctx;
}
