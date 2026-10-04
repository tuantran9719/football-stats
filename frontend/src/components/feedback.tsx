/**
 * Hộp thư góp ý.
 *
 * Đặt ngay trên thanh tiêu đề trang chủ chứ không giấu trong menu: góp ý
 * chỉ đến khi người dùng nhìn thấy chỗ gửi đúng lúc họ đang khó chịu về
 * một thứ gì đó. Chôn nó sau hai lần chạm thì gần như không ai gửi.
 *
 * Gửi hỏng vẫn báo cho người dùng biết, không nuốt lỗi — nhưng backend
 * đã lưu góp ý vào file trước khi thử gửi mail, nên "gửi thành công" là
 * đúng sự thật kể cả khi máy chủ mail chưa được cấu hình.
 */
import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Modal, Platform, Pressable, StyleSheet, Text, TextInput, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { api, ApiError } from '../api';
import { colors, font, radius, space } from '../theme';
import { useI18n } from '../i18n';

type Kind = 'bug' | 'idea' | 'other';

/** Nút mở hộp thư, dùng trên thanh tiêu đề. */
export function FeedbackButton({ onPress }: { onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      hitSlop={10}
      style={({ pressed }) => [s.btn, pressed && { opacity: 0.6 }]}
    >
      <Ionicons name="chatbubble-ellipses-outline" size={18} color={colors.accent} />
    </Pressable>
  );
}

export function FeedbackSheet({
  visible, onClose,
}: { visible: boolean; onClose: () => void }) {
  const { t, lang } = useI18n();
  const [kind, setKind] = useState<Kind>('idea');
  const [message, setMessage] = useState('');
  const [contact, setContact] = useState('');
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = useCallback(() => {
    setMessage(''); setContact(''); setKind('idea');
    setDone(false); setError(null); setSending(false);
  }, []);

  const close = useCallback(() => { reset(); onClose(); }, [reset, onClose]);

  const send = useCallback(async () => {
    const text = message.trim();
    if (text.length < 5) { setError(t.feedback.tooShort); return; }
    setSending(true); setError(null);
    try {
      await api.sendFeedback({
        message: text,
        kind,
        contact: contact.trim() || undefined,
        lang,
        platform: Platform.OS,
      });
      setDone(true);
    } catch (e) {
      setError(e instanceof ApiError && e.status === 429
        ? t.feedback.tooMany
        : t.feedback.failed);
    } finally {
      setSending(false);
    }
  }, [message, contact, kind, lang, t]);

  const KINDS: Array<{ value: Kind; label: string; icon: React.ComponentProps<typeof Ionicons>['name'] }> = [
    { value: 'bug', label: t.feedback.kindBug, icon: 'bug-outline' },
    { value: 'idea', label: t.feedback.kindIdea, icon: 'bulb-outline' },
    { value: 'other', label: t.feedback.kindOther, icon: 'ellipsis-horizontal' },
  ];

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={close}>
      <View style={s.backdrop}>
        <Pressable style={StyleSheet.absoluteFill} onPress={close} />
        <View style={s.panel}>
          {done ? (
            <View style={s.doneBox}>
              <Ionicons name="checkmark-circle" size={52} color={colors.home} />
              <Text style={s.doneText}>{t.feedback.thanks}</Text>
              <Pressable onPress={close} style={s.cta}>
                <Text style={s.ctaText}>{t.menu.close}</Text>
              </Pressable>
            </View>
          ) : (
            <>
              <View style={s.head}>
                <View style={{ flex: 1 }}>
                  <Text style={s.title}>{t.feedback.title}</Text>
                  <Text style={s.sub}>{t.feedback.sub}</Text>
                </View>
                <Pressable onPress={close} hitSlop={10}>
                  <Ionicons name="close" size={22} color={colors.textDim} />
                </Pressable>
              </View>

              <View style={s.kinds}>
                {KINDS.map((k) => {
                  const on = kind === k.value;
                  return (
                    <Pressable
                      key={k.value}
                      onPress={() => setKind(k.value)}
                      style={[s.kind, on && s.kindOn]}
                    >
                      <Ionicons
                        name={k.icon} size={15}
                        color={on ? colors.accent : colors.textDim}
                      />
                      <Text style={[s.kindText, on && s.kindTextOn]} numberOfLines={1}>
                        {k.label}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>

              <TextInput
                value={message}
                onChangeText={(v) => { setMessage(v); if (error) setError(null); }}
                placeholder={t.feedback.messagePlaceholder}
                placeholderTextColor={colors.textFaint}
                style={s.area}
                multiline
                textAlignVertical="top"
                maxLength={4000}
              />

              <View style={{ gap: 5 }}>
                <Text style={s.label}>{t.feedback.contactLabel}</Text>
                <TextInput
                  value={contact}
                  onChangeText={setContact}
                  placeholder={t.feedback.contactPlaceholder}
                  placeholderTextColor={colors.textFaint}
                  style={s.input}
                  autoCapitalize="none"
                  autoCorrect={false}
                  maxLength={200}
                />
              </View>

              {!!error && <Text style={s.err}>{error}</Text>}

              <Pressable
                onPress={send}
                disabled={sending}
                style={[s.cta, sending && { opacity: 0.6 }]}
              >
                {sending
                  ? <ActivityIndicator color="#FFFFFF" />
                  : <Ionicons name="send" size={16} color="#FFFFFF" />}
                <Text style={s.ctaText}>
                  {sending ? t.feedback.sending : t.feedback.send}
                </Text>
              </Pressable>
            </>
          )}
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  btn: {
    width: 36, height: 36, borderRadius: radius.md,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: colors.accentSoft,
    borderWidth: 1, borderColor: colors.accentLine,
  },

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
  head: { flexDirection: 'row', alignItems: 'flex-start', gap: space.sm },
  title: { ...font.h2, color: colors.text, fontSize: 16 },
  sub: { ...font.tiny, color: colors.textDim, marginTop: 4, lineHeight: 16 },

  kinds: { flexDirection: 'row', gap: 6 },
  kind: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 5, paddingVertical: 9, paddingHorizontal: 6,
    borderRadius: radius.md,
    backgroundColor: colors.card,
    borderWidth: 1, borderColor: colors.hairline,
  },
  kindOn: { backgroundColor: colors.accentSoft, borderColor: colors.accentLine },
  kindText: { ...font.tiny, color: colors.textDim, fontWeight: '700' },
  kindTextOn: { color: colors.accent, fontWeight: '800' },

  area: {
    minHeight: 120,
    backgroundColor: colors.card,
    borderRadius: radius.md,
    borderWidth: 1, borderColor: colors.hairline,
    padding: space.md,
    ...font.small, color: colors.text,
  },
  label: { ...font.tiny, color: colors.textFaint },
  input: {
    backgroundColor: colors.card,
    borderRadius: radius.md,
    borderWidth: 1, borderColor: colors.hairline,
    paddingHorizontal: space.md, paddingVertical: 10,
    ...font.small, color: colors.text,
  },
  err: { ...font.tiny, color: colors.live },

  cta: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: colors.accent,
    paddingVertical: 13, borderRadius: radius.pill,
  },
  ctaText: { ...font.h2, color: '#FFFFFF', fontSize: 15 },

  doneBox: { alignItems: 'center', gap: space.md, paddingVertical: space.md },
  doneText: { ...font.h2, color: colors.text, fontSize: 15, textAlign: 'center' },
});
