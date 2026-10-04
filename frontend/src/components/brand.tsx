/**
 * Logo và chữ hiệu của app.
 *
 * Dựng bằng View + gradient chứ không dùng ảnh hay thư viện SVG: nét
 * luôn sắc ở mọi mật độ màn hình, không thêm phụ thuộc, và đổi màu theo
 * theme chỉ bằng cách sửa một chỗ trong theme.ts.
 *
 * Tên thương hiệu "Football Stats" CỐ TÌNH không dịch. Tên sản phẩm giữ
 * nguyên ở mọi ngôn ngữ mới nhận ra được; phần mô tả bên dưới tiêu đề
 * vẫn dịch bình thường nên người dùng không mất thông tin gì.
 */
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { colors, font, gradients, radius } from '../theme';

/** Ba cột tăng dần trong khung bo tròn — đọc ra ngay là "thống kê". */
export function BrandMark({ size = 34 }: { size?: number }) {
  // Mọi số đo tính theo size để logo co giãn mà tỉ lệ không đổi.
  const pad = size * 0.24;
  const gap = size * 0.09;
  const barW = (size - pad * 2 - gap * 2) / 3;
  const heights = [0.3, 0.55, 0.82];

  return (
    <View style={[s.mark, { width: size, height: size, borderRadius: size * 0.29 }]}>
      <LinearGradient
        colors={gradients.electric}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={StyleSheet.absoluteFill}
      />
      <View style={[s.bars, { paddingHorizontal: pad, paddingBottom: pad, gap }]}>
        {heights.map((h, i) => (
          <View
            key={h}
            style={{
              width: barW,
              height: (size - pad * 2) * h,
              borderRadius: barW / 2,
              backgroundColor: '#FFFFFF',
              // Cột thấp mờ hơn một chút để mắt đọc được chiều tăng dần
              // ngay cả khi logo nhỏ.
              opacity: 0.62 + i * 0.19,
            }}
          />
        ))}
      </View>
    </View>
  );
}

/** Logo đầy đủ: khung biểu tượng cộng chữ "Football Stats". */
export function BrandLockup({ size = 34 }: { size?: number }) {
  return (
    <View style={s.lockup}>
      <BrandMark size={size} />
      <Text style={s.word} numberOfLines={1}>
        <Text style={s.wordA}>Football</Text>
        <Text style={s.wordB}> Stats</Text>
      </Text>
    </View>
  );
}

const s = StyleSheet.create({
  mark: { overflow: 'hidden', justifyContent: 'flex-end' },
  bars: { flexDirection: 'row', alignItems: 'flex-end', flex: 1 },

  lockup: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  // letterSpacing âm kéo hai chữ sát lại thành một khối, đúng kiểu chữ
  // hiệu; để mặc định thì trông như một dòng tiêu đề bình thường.
  word: { ...font.display, fontSize: 25, letterSpacing: -0.9 },
  wordA: { color: colors.text },
  wordB: { color: colors.accent },
});
