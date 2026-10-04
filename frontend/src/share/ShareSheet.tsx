/**
 * Cửa sổ xem trước và chia sẻ ảnh trận đấu.
 *
 * Luôn cho xem trước trước khi chia sẻ: ảnh sẽ được đăng lên trang cá
 * nhân của người dùng nên họ cần thấy chính xác cái mình sắp gửi đi.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator, Image, Modal, Platform, Pressable, StyleSheet, Text, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radius, space } from '../theme';
import { useI18n } from '../i18n';
import { drawShareCard, type ShareCardData, type ShareFormat } from './drawCard';
import { shareOrDownload } from './shareImage';

/** Chỉ web mới vẽ được canvas — xem ghi chú ở drawCard.ts. */
export const CAN_SHARE_IMAGE = Platform.OS === 'web';

export function ShareSheet({
  visible, onClose, data, fileBase,
}: {
  visible: boolean;
  onClose: () => void;
  data: ShareCardData;
  /** Tên file không kèm đuôi, ví dụ "arsenal-chelsea". */
  fileBase: string;
}) {
  const { t } = useI18n();
  const [format, setFormat] = useState<ShareFormat>('story');
  const [preview, setPreview] = useState<string | null>(null);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [error, setError] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!visible) return undefined;
    let alive = true;
    let url: string | null = null;
    setPreview(null); setBlob(null); setError(false); setNote(null);

    void (async () => {
      try {
        const out = await drawShareCard(data, format);
        if (!alive) return;
        url = URL.createObjectURL(out);
        setBlob(out);
        setPreview(url);
      } catch {
        if (alive) setError(true);
      }
    })();

    return () => {
      alive = false;
      // Thu hồi khi đóng hoặc đổi khổ ảnh, nếu không mỗi lần mở lại là
      // một tấm ảnh nữa nằm trong bộ nhớ cho tới khi tải lại trang.
      if (url) URL.revokeObjectURL(url);
    };
  }, [visible, format, data]);

  const onShare = useCallback(async () => {
    if (!blob) return;
    const res = await shareOrDownload(blob, `${fileBase}.png`, t.share.title);
    if (res === 'downloaded') setNote(t.share.saved);
  }, [blob, fileBase, t]);

  const FORMATS: Array<{ value: ShareFormat; label: string }> = [
    { value: 'story', label: t.share.story },
    { value: 'square', label: t.share.square },
  ];

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={s.backdrop}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
        <View style={s.panel}>
          <View style={s.head}>
            <Text style={s.title}>{t.share.title}</Text>
            <Pressable onPress={onClose} hitSlop={10}>
              <Ionicons name="close" size={22} color={colors.textDim} />
            </Pressable>
          </View>

          <View style={s.tabs}>
            {FORMATS.map((f) => (
              <Pressable
                key={f.value}
                onPress={() => setFormat(f.value)}
                style={[s.tab, format === f.value && s.tabActive]}
              >
                <Text style={[s.tabText, format === f.value && s.tabTextActive]}>
                  {f.label}
                </Text>
              </Pressable>
            ))}
          </View>

          <View style={[s.stage, format === 'story' ? s.stageStory : s.stageSquare]}>
            {!preview && !error && <ActivityIndicator color={colors.accent} />}
            {error && <Text style={s.err}>{t.share.failed}</Text>}
            {!!preview && (
              <Image source={{ uri: preview }} style={s.preview} resizeMode="contain" />
            )}
          </View>

          {!!note && <Text style={s.note}>{note}</Text>}

          <Pressable
            onPress={onShare}
            disabled={!blob}
            style={[s.cta, !blob && { opacity: 0.5 }]}
          >
            <Ionicons name="share-social" size={18} color="#FFFFFF" />
            <Text style={s.ctaText}>{t.share.doShare}</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  backdrop: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.72)',
    alignItems: 'center', justifyContent: 'center', padding: space.lg,
  },
  panel: {
    width: '100%', maxWidth: 420,
    backgroundColor: colors.bgElev,
    borderRadius: radius.xl,
    borderWidth: 1, borderColor: colors.hairline,
    padding: space.lg, gap: space.md,
  },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: { ...font.h2, color: colors.text, fontSize: 16 },

  tabs: {
    flexDirection: 'row', gap: 4, padding: 4,
    backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: radius.pill,
  },
  tab: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: radius.pill },
  tabActive: { backgroundColor: colors.accent },
  tabText: { ...font.small, color: colors.textDim, fontWeight: '700' },
  tabTextActive: { color: '#FFFFFF', fontWeight: '800' },

  // Khung xem trước giữ đúng tỉ lệ ảnh sẽ xuất ra, để không ai bị bất
  // ngờ vì ảnh thật khác với cái vừa nhìn.
  stage: {
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(0,0,0,0.3)', borderRadius: radius.lg,
    overflow: 'hidden',
  },
  stageStory: { aspectRatio: 1080 / 1920, alignSelf: 'center', width: '62%' },
  stageSquare: { aspectRatio: 1, alignSelf: 'center', width: '88%' },
  preview: { width: '100%', height: '100%' },

  err: { ...font.small, color: colors.live, textAlign: 'center', padding: space.lg },
  note: { ...font.tiny, color: colors.textDim, textAlign: 'center' },

  cta: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: colors.accent,
    paddingVertical: 13, borderRadius: radius.pill,
  },
  ctaText: { ...font.h2, color: '#FFFFFF', fontSize: 15 },
});
