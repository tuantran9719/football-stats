/**
 * Menu chọn giải đấu dạng ngăn kéo trượt từ trái, mở bằng nút hamburger.
 *
 * Dùng Modal có sẵn của React Native để chắc chắn nổi trên mọi nội dung,
 * tránh đúng loại lỗi "quên position:relative ở cha" từng gặp với các
 * phần tử position:absolute tự dựng tay trước đây.
 */
import React, { useEffect, useRef, useState } from 'react';
import {
  Animated, Modal, Pressable, ScrollView, StyleSheet, Switch, Text, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radius, shadow, space } from '../theme';
import { useI18n } from '../i18n';
import { useSettings } from '../settings';
import { LANGUAGES } from '../i18n/translations';
import { LanguagePicker, TeamLogo } from './ui';
import { useLeagueLogos } from '../leagueLogos';

export function HamburgerButton({ onPress }: { onPress: () => void }) {
  return (
    <Pressable onPress={onPress} hitSlop={10} style={({ pressed }) => [s.hbBtn, pressed && { opacity: 0.6 }]}>
      <Ionicons name="menu" size={24} color={colors.text} />
    </Pressable>
  );
}

export function LeagueMenu<T extends string>({
  visible, onClose, options, value, onChange, showAll,
}: {
  visible: boolean;
  onClose: () => void;
  options: ReadonlyArray<{ value: T; label: string }>;
  value: T | 'ALL';
  onChange: (v: T | 'ALL') => void;
  /** Có ghim mục "Tất cả các giải" lên đầu danh sách không. */
  showAll?: boolean;
}) {
  const { t, lang, setLang } = useI18n();
  const { showOdds, setShowOdds } = useSettings();
  const logos = useLeagueLogos();
  const [langOpen, setLangOpen] = useState(false);
  const currentLang = LANGUAGES.find((l) => l.code === lang);
  const slide = useRef(new Animated.Value(-320)).current;
  const backdrop = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      Animated.parallel([
        Animated.timing(backdrop, { toValue: 1, duration: 200, useNativeDriver: true }),
        Animated.spring(slide, { toValue: 0, useNativeDriver: true, speed: 16, bounciness: 4 }),
      ]).start();
    } else {
      slide.setValue(-320);
      backdrop.setValue(0);
    }
  }, [visible, slide, backdrop]);

  const close = () => {
    Animated.parallel([
      Animated.timing(backdrop, { toValue: 0, duration: 150, useNativeDriver: true }),
      Animated.timing(slide, { toValue: -320, duration: 180, useNativeDriver: true }),
    ]).start(onClose);
  };

  const pick = (v: T | 'ALL') => { onChange(v); close(); };

  return (
    <Modal visible={visible} transparent animationType="none" onRequestClose={close}>
      <View style={s.overlay}>
        <Animated.View style={[StyleSheet.absoluteFill, s.backdrop, { opacity: backdrop }]}>
          <Pressable style={StyleSheet.absoluteFill} onPress={close} />
        </Animated.View>

        <Animated.View style={[s.panel, { transform: [{ translateX: slide }] }]}>
          <View style={s.panelHead}>
            <Text style={s.panelTitle}>{t.menu.title}</Text>
            <Pressable onPress={close} hitSlop={10} style={({ pressed }) => pressed && { opacity: 0.6 }}>
              <Ionicons name="close" size={22} color={colors.textDim} />
            </Pressable>
          </View>

          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.list}>
            {showAll && (
              <Pressable
                onPress={() => pick('ALL')}
                style={({ pressed }) => [s.item, value === 'ALL' && s.itemActive, pressed && { opacity: 0.7 }]}
              >
                <View style={[s.allIcon, value === 'ALL' && s.allIconActive]}>
                  <Ionicons name="albums" size={16} color={value === 'ALL' ? '#00230F' : colors.textDim} />
                </View>
                <Text style={[s.itemText, value === 'ALL' && s.itemTextActive]}>{t.league.ALL}</Text>
                {value === 'ALL' && <Ionicons name="checkmark" size={18} color={colors.accent} />}
              </Pressable>
            )}
            {options.map((o) => {
              const active = o.value === value;
              return (
                <Pressable
                  key={o.value}
                  onPress={() => pick(o.value)}
                  style={({ pressed }) => [s.item, active && s.itemActive, pressed && { opacity: 0.7 }]}
                >
                  {/* Logo giải giúp nhận ra giải bằng mắt, nhanh hơn đọc
                      chữ — nhất là với người quen xem theo huy hiệu. */}
                  <TeamLogo uri={logos[o.value]} size={24} />
                  <Text style={[s.itemText, active && s.itemTextActive]}>{o.label}</Text>
                  {active && <Ionicons name="checkmark" size={18} color={colors.accent} />}
                </Pressable>
              );
            })}

            <View style={s.sectionDivider} />
            <Text style={s.sectionLabel}>{t.menu.settings}</Text>
            <Pressable
              onPress={() => setLangOpen(true)}
              style={({ pressed }) => [s.item, pressed && { opacity: 0.7 }]}
            >
              <Ionicons name="language" size={17} color={colors.textDim} />
              <Text style={s.itemText}>{t.menu.language}</Text>
              <Text style={s.itemValue}>{currentLang?.label ?? lang.toUpperCase()}</Text>
            </Pressable>

            {/* Vạch kèo mặc định TẮT — xem ghi chú ở src/settings.tsx. */}
            <View style={s.switchRow}>
              <Ionicons name="stats-chart" size={17} color={colors.textDim} />
              <View style={s.switchLabel}>
                <Text style={s.itemText}>{t.menu.showOdds}</Text>
                <Text style={s.switchHint}>{t.menu.showOddsHint}</Text>
              </View>
              <Switch
                value={showOdds}
                onValueChange={setShowOdds}
                trackColor={{ false: colors.hairline, true: colors.accentLine }}
                thumbColor={showOdds ? colors.accent : colors.textFaint}
              />
            </View>
          </ScrollView>

          <LanguagePicker
            visible={langOpen}
            onClose={() => setLangOpen(false)}
            value={lang}
            onChange={setLang}
            title={t.menu.language}
          />
        </Animated.View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  hbBtn: {
    width: 36, height: 36, borderRadius: radius.md,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.06)',
  },
  overlay: { flex: 1, flexDirection: 'row', position: 'relative' },
  backdrop: { backgroundColor: 'rgba(0,0,0,0.55)' },
  panel: {
    width: 300, maxWidth: '84%', height: '100%',
    backgroundColor: colors.bgElev,
    borderRightWidth: 1, borderRightColor: colors.hairline,
    paddingTop: 54,
    ...shadow.card,
  },
  panelHead: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: space.lg, paddingBottom: space.md,
    borderBottomWidth: 1, borderBottomColor: colors.hairline,
  },
  panelTitle: { ...font.h2, color: colors.text, fontSize: 16 },

  list: { padding: space.md, gap: 3 },
  item: {
    flexDirection: 'row', alignItems: 'center', gap: space.md,
    paddingHorizontal: space.md, paddingVertical: 13,
    borderRadius: radius.md,
  },
  itemActive: { backgroundColor: colors.accentSoft },
  itemText: { ...font.body, color: colors.textSoft, flex: 1, fontSize: 14.5 },
  itemTextActive: { color: colors.accent, fontWeight: '800' },
  itemValue: { ...font.small, color: colors.textFaint },

  switchRow: {
    flexDirection: 'row', alignItems: 'center', gap: space.md,
    paddingHorizontal: space.md, paddingVertical: 10,
  },
  switchLabel: { flex: 1, minWidth: 0, gap: 2 },
  switchHint: { ...font.tiny, color: colors.textFaint, fontSize: 10.5, lineHeight: 14 },

  sectionDivider: {
    height: 1, backgroundColor: colors.hairline,
    marginVertical: space.md, marginHorizontal: space.md,
  },
  sectionLabel: {
    ...font.label, color: colors.textFaint,
    paddingHorizontal: space.md, paddingBottom: 6,
  },

  allIcon: {
    width: 26, height: 26, borderRadius: 13,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.08)',
  },
  allIconActive: { backgroundColor: colors.accent },
});
