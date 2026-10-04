/**
 * Khung hỏi đáp của một trận.
 *
 * Đặt thẳng trong trang chi tiết trận chứ không phải một tab riêng, vì
 * nó chỉ có nghĩa khi đang nhìn đúng trận đó — và vì thêm tab thứ năm
 * vào thanh tab sẽ làm chữ bị bóp lại trên màn hình hẹp.
 *
 * Hai cách hỏi, cố ý giữ cả hai:
 *   - Nút gợi ý: cho người mới biết hỏi được những gì, và bấm là ra
 *     ngay, không qua bước đoán ý nên không bao giờ hiểu sai.
 *   - Gõ tay: cho người biết mình muốn gì.
 *
 * Khi bot không chắc, nó hiện ba lựa chọn gần nhất. Người dùng chạm một
 * cái là vừa nhận được câu trả lời, vừa dạy cho bộ phân loại biết câu
 * vừa gõ thuộc nhóm nào — nhãn huấn luyện tự đến từ chính người viết
 * câu đó, không ai phải ngồi gán tay.
 */
import React, { useCallback, useRef, useState } from 'react';
import {
  ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { api, tzOffsetMinutes } from '../api';
import type { ChatIntent, ChatResponse } from '../types';
import { colors, font, radius, space } from '../theme';
import { useI18n } from '../i18n';
import { Card } from './ui';

type Turn = {
  id: number;
  role: 'user' | 'bot';
  text: string;
  suggestions?: ChatIntent[];
  action?: ChatResponse['action'];
  /** Câu gốc người dùng gõ, giữ lại để dạy bot khi họ chọn giúp.
   *  Chỉ đặt khi bot chưa chắc — trả lời chắc chắn rồi mà người dùng
   *  bấm nút tiếp theo thì đó là câu hỏi mới, không phải lời sửa. */
  pending?: string;
  /** Bot hoang mang hẳn (khác với "đã trả lời nhưng chưa chắc"). */
  lost?: boolean;
};

const FIRST_CHIPS: ChatIntent[] = [
  'outcome', 'total_goals', 'over_under', 'btts', 'corners', 'cards',
];

export function MatchChat({
  league, matchExternalId, onOpenTab,
}: {
  league: string;
  matchExternalId: string;
  /** Mở tab khác khi câu trả lời nằm ở màn hình đó. */
  onOpenTab?: (tab: 'history' | 'lineups' | 'standings') => void;
}) {
  const { t, lang } = useI18n();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [chips, setChips] = useState<ChatIntent[]>(FIRST_CHIPS);
  const nextId = useRef(1);

  const label = useCallback(
    (intent: ChatIntent) => t.chat.intents[intent] ?? intent,
    [t],
  );

  const ask = useCallback(async (
    { question, intent }: { question?: string; intent?: ChatIntent },
  ) => {
    if (busy) return;
    const shown = question ?? (intent ? label(intent) : '');
    if (!shown.trim()) return;

    // Câu hỏi đang chờ được dạy: người dùng vừa chọn giúp một gợi ý
    // sau khi bot nói "ý bạn là câu nào?".
    const waiting = turns[turns.length - 1]?.pending;
    if (intent && waiting) {
      api.teachChat(waiting, intent);
    }

    setTurns((prev) => [
      ...prev,
      { id: nextId.current++, role: 'user', text: shown },
    ]);
    setDraft('');
    setBusy(true);
    try {
      const res = await api.matchChat(matchExternalId, {
        league, question, intent, lang, tz: tzOffsetMinutes(),
      });
      setChips(res.suggestions.length ? res.suggestions : FIRST_CHIPS);
      setTurns((prev) => [...prev, {
        id: nextId.current++,
        role: 'bot',
        text: res.text,
        suggestions: res.suggestions,
        action: res.action,
        pending: (res.askingBack || res.correctable) ? question : undefined,
        lost: res.askingBack,
      }]);
    } catch {
      setTurns((prev) => [...prev, {
        id: nextId.current++, role: 'bot', text: t.chat.failed,
      }]);
    } finally {
      setBusy(false);
    }
  }, [busy, label, turns, matchExternalId, league, lang, t]);

  const last = turns[turns.length - 1];
  // Có câu đang chờ được dạy thì làm nổi hàng nút lên, vì lúc này
  // chúng không còn là "hỏi tiếp" mà là "chọn giúp mình".
  const awaitingLabel = !!last?.pending;

  return (
    <Card style={s.card}>
      <View style={s.head}>
        <View style={s.icon}>
          <Ionicons name="chatbubble-ellipses" size={15} color={colors.accent} />
        </View>
        <View style={s.headText}>
          <Text style={s.title}>{t.chat.title}</Text>
          <Text style={s.sub} numberOfLines={2}>{t.chat.sub}</Text>
        </View>
        {turns.length > 0 && (
          <Pressable
            onPress={() => { setTurns([]); setChips(FIRST_CHIPS); }}
            hitSlop={8}
            style={({ pressed }) => pressed && { opacity: 0.6 }}
          >
            <Text style={s.clear}>{t.chat.clear}</Text>
          </Pressable>
        )}
      </View>

      {turns.length > 0 && (
        <View style={s.thread}>
          {turns.map((turn) => (
            <View
              key={turn.id}
              style={[s.bubble, turn.role === 'user' ? s.bubbleUser : s.bubbleBot]}
            >
              <Text style={turn.role === 'user' ? s.textUser : s.textBot}>
                {turn.text}
              </Text>
              {/* Chỉ hai tab này nằm trong màn hình chi tiết trận. Câu
                  trả lời về bảng xếp hạng cũng kèm action, nhưng bảng
                  đó ở màn hình chính nên không dựng nút — nút bấm vào
                  không đi đâu còn tệ hơn là không có nút. */}
              {turn.action && turn.action !== 'standings' && onOpenTab && (
                <Pressable
                  onPress={() => onOpenTab(turn.action as 'history' | 'lineups' | 'standings')}
                  style={({ pressed }) => [s.openBtn, pressed && { opacity: 0.7 }]}
                >
                  <Text style={s.openText}>{t.chat.openTab}</Text>
                  <Ionicons name="arrow-forward" size={12} color={colors.accent} />
                </Pressable>
              )}
            </View>
          ))}
          {busy && (
            <View style={[s.bubble, s.bubbleBot, s.busyRow]}>
              <ActivityIndicator size="small" color={colors.textDim} />
              <Text style={s.textBot}>{t.chat.thinking}</Text>
            </View>
          )}
        </View>
      )}

      {awaitingLabel && (
        <Text style={s.askBack}>{last?.lost ? t.chat.askBack : t.chat.wrong}</Text>
      )}

      <View style={s.chips}>
        {chips.map((intent) => (
          <Pressable
            key={intent}
            onPress={() => ask({ intent })}
            disabled={busy}
            style={({ pressed }) => [
              s.chip,
              awaitingLabel && s.chipHighlight,
              (pressed || busy) && { opacity: 0.6 },
            ]}
          >
            <Text style={[s.chipText, awaitingLabel && s.chipTextHighlight]}>
              {label(intent)}
            </Text>
          </Pressable>
        ))}
      </View>

      <View style={s.inputRow}>
        <TextInput
          value={draft}
          onChangeText={setDraft}
          placeholder={t.chat.placeholder}
          placeholderTextColor={colors.textFaint}
          style={s.input}
          returnKeyType="send"
          onSubmitEditing={() => ask({ question: draft.trim() })}
          editable={!busy}
          maxLength={200}
        />
        <Pressable
          onPress={() => ask({ question: draft.trim() })}
          disabled={busy || !draft.trim()}
          style={({ pressed }) => [
            s.sendBtn,
            (!draft.trim() || busy) && s.sendBtnOff,
            pressed && { opacity: 0.7 },
          ]}
        >
          <Ionicons
            name="arrow-up"
            size={17}
            color={draft.trim() && !busy ? '#FFFFFF' : colors.textFaint}
          />
        </Pressable>
      </View>
    </Card>
  );
}

const s = StyleSheet.create({
  card: { gap: space.md },

  head: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  icon: {
    width: 28, height: 28, borderRadius: 14,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: colors.accentSoft,
  },
  headText: { flex: 1, minWidth: 0, gap: 1 },
  title: { ...font.h2, color: colors.text, fontSize: 14 },
  sub: { ...font.tiny, color: colors.textFaint, fontSize: 10.5, lineHeight: 14 },
  clear: { ...font.small, color: colors.textDim },

  thread: { gap: space.sm },
  bubble: {
    maxWidth: '92%',
    paddingHorizontal: space.md, paddingVertical: 9,
    borderRadius: radius.md,
  },
  bubbleUser: {
    alignSelf: 'flex-end',
    backgroundColor: colors.accentSoft,
    borderWidth: 1, borderColor: colors.accentLine,
  },
  bubbleBot: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(255,255,255,0.045)',
  },
  textUser: { ...font.body, color: colors.text, fontSize: 13.5 },
  textBot: { ...font.body, color: colors.textSoft, fontSize: 13.5, lineHeight: 20 },
  busyRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },

  openBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    marginTop: 7, alignSelf: 'flex-start',
  },
  openText: { ...font.small, color: colors.accent, fontWeight: '800' },

  askBack: { ...font.small, color: colors.textDim, marginTop: -2 },

  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 },
  chip: {
    paddingHorizontal: 11, paddingVertical: 7,
    borderRadius: radius.pill,
    borderWidth: 1, borderColor: colors.hairline,
    backgroundColor: 'rgba(255,255,255,0.03)',
  },
  chipHighlight: {
    borderColor: colors.accentLine,
    backgroundColor: colors.accentSoft,
  },
  chipText: { ...font.small, color: colors.textSoft, fontSize: 12 },
  chipTextHighlight: { color: colors.accent, fontWeight: '800' },

  inputRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  input: {
    flex: 1, minWidth: 0,
    paddingHorizontal: space.md, paddingVertical: 10,
    borderRadius: radius.pill,
    borderWidth: 1, borderColor: colors.hairline,
    backgroundColor: 'rgba(255,255,255,0.03)',
    color: colors.text,
    ...font.body, fontSize: 13.5,
  },
  sendBtn: {
    width: 36, height: 36, borderRadius: 18,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: colors.accent,
  },
  sendBtnOff: { backgroundColor: 'rgba(255,255,255,0.05)' },
});
