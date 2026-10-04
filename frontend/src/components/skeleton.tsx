/**
 * Khung xương lấp lánh khi đang tải, thay cho vòng xoay đơn điệu cũ.
 *
 * Mỗi khối nhấp nháy độ mờ lên xuống liên tục (kiểu "thở"), và có hình
 * dạng gần giống nội dung thật sắp hiện ra, nên người dùng cảm giác trang
 * đang tải nhanh hơn thực tế. Đây là mẫu phổ biến ở các app hiện đại,
 * thay cho ActivityIndicator một mình giữa màn hình trống.
 */
import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View } from 'react-native';
import { colors, radius, shadow, space } from '../theme';

/** Một khối chữ nhật bo góc, nhấp nháy độ mờ. Đơn vị dựng mọi khung xương khác. */
export function Bone({
  width, height = 14, radius: r = 6, style,
}: { width: number | `${number}%`; height?: number; radius?: number; style?: object }) {
  const pulse = useRef(new Animated.Value(0.35)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 0.75, duration: 700, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.35, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  return (
    <Animated.View
      style={[
        { width, height, borderRadius: r, backgroundColor: 'rgba(255,255,255,0.12)', opacity: pulse },
        style,
      ]}
    />
  );
}

/** Khung xương cho một thẻ trận ở màn hình chính. */
export function MatchCardSkeleton() {
  return (
    <View style={s.card}>
      <View style={s.cardTop}>
        <Bone width={90} height={11} />
        <Bone width={64} height={20} radius={10} />
      </View>
      <View style={s.teamsBlock}>
        <View style={s.teamRow}>
          <Bone width={30} height={30} radius={15} />
          <Bone width="55%" height={14} style={{ marginLeft: space.md }} />
        </View>
        <View style={s.teamRow}>
          <Bone width={30} height={30} radius={15} />
          <Bone width="45%" height={14} style={{ marginLeft: space.md }} />
        </View>
      </View>
    </View>
  );
}

export function MatchListSkeleton({ count = 4 }: { count?: number }) {
  return (
    <View style={{ gap: space.md }}>
      {Array.from({ length: count }).map((_, i) => <MatchCardSkeleton key={i} />)}
    </View>
  );
}

/** Khung xương cho một dòng trong bảng lịch sử theo trận. */
export function MatchRowSkeleton() {
  return (
    <View style={s.card}>
      <Bone width={80} height={10} />
      <View style={[s.midRow, { marginTop: space.sm }]}>
        <Bone width={26} height={26} radius={13} />
        <Bone width={54} height={17} radius={8} />
        <Bone width={26} height={26} radius={13} />
      </View>
      <View style={s.statsStrip}>
        {[0, 1, 2, 3].map((i) => <Bone key={i} width={28} height={20} radius={6} />)}
      </View>
    </View>
  );
}

export function MatchRowListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <View style={{ gap: space.sm }}>
      {Array.from({ length: count }).map((_, i) => <MatchRowSkeleton key={i} />)}
    </View>
  );
}

/** Khung xương cho một thẻ chỉ số (phong độ đội). */
export function StatCardSkeleton() {
  return (
    <View style={[s.card, { gap: space.md }]}>
      <View style={s.cardTop}>
        <Bone width={110} height={14} />
        <Bone width={48} height={22} radius={6} />
      </View>
      <View style={{ gap: space.sm }}>
        {[0, 1, 2].map((i) => (
          <View key={i} style={s.midRow}>
            <Bone width={44} height={10} />
            <Bone width="70%" height={7} radius={4} />
          </View>
        ))}
      </View>
    </View>
  );
}

export function StatListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <View style={{ gap: space.md }}>
      {Array.from({ length: count }).map((_, i) => <StatCardSkeleton key={i} />)}
    </View>
  );
}

/** Khung xương cho một dòng đội trong danh sách chọn (tab Đối đầu). */
export function TeamRowSkeleton() {
  return (
    <View style={[s.card, s.teamListItem]}>
      <Bone width={30} height={30} radius={15} />
      <Bone width="50%" height={14} style={{ marginLeft: space.md }} />
    </View>
  );
}

export function TeamListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <View style={{ gap: space.sm }}>
      {Array.from({ length: count }).map((_, i) => <TeamRowSkeleton key={i} />)}
    </View>
  );
}

/** Khung xương cho một thẻ tin tức. */
export function NewsCardSkeleton() {
  return (
    <View style={s.card}>
      <Bone width="100%" height={140} radius={12} />
      <Bone width="90%" height={14} style={{ marginTop: space.md }} />
      <Bone width="60%" height={14} style={{ marginTop: 6 }} />
      <Bone width={70} height={10} style={{ marginTop: space.sm }} />
    </View>
  );
}

export function NewsListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <View style={{ gap: space.md }}>
      {Array.from({ length: count }).map((_, i) => <NewsCardSkeleton key={i} />)}
    </View>
  );
}

const s = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.md,
    ...shadow.card,
  },
  cardTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  teamsBlock: { marginTop: space.md, gap: space.md },
  teamRow: { flexDirection: 'row', alignItems: 'center' },
  midRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.md },
  statsStrip: {
    flexDirection: 'row', justifyContent: 'space-around',
    borderTopWidth: 1, borderTopColor: colors.hairline,
    paddingTop: space.sm, marginTop: space.sm,
  },
  teamListItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: space.md },
});
