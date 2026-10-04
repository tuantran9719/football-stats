/**
 * Đưa ảnh đã vẽ ra ngoài: chia sẻ qua bảng chia sẻ của hệ điều hành,
 * hoặc tải về nếu trình duyệt không hỗ trợ.
 *
 * Dùng Web Share API cấp 2 (chia sẻ kèm FILE). Đây là đường duy nhất
 * đưa thẳng ảnh sang Zalo, Facebook, Instagram mà không phải đăng ký
 * ứng dụng với từng bên: hệ điều hành mở bảng chia sẻ sẵn có, người
 * dùng chọn app nào thì ảnh sang app đó.
 *
 * Hỗ trợ thực tế: Safari trên iOS và Chrome trên Android đều có. Trình
 * duyệt máy tính phần lớn KHÔNG có, nên luôn phải có đường lùi tải về.
 */

export type ShareResult = 'shared' | 'downloaded' | 'cancelled';

function canShareFiles(files: File[]): boolean {
  const nav = navigator as Navigator & {
    canShare?: (data: { files?: File[] }) => boolean;
  };
  return typeof nav.share === 'function'
    && typeof nav.canShare === 'function'
    && nav.canShare({ files });
}

function download(file: File): void {
  const url = URL.createObjectURL(file);
  const a = document.createElement('a');
  a.href = url;
  a.download = file.name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Thu hồi muộn một nhịp: thu hồi ngay thì Safari huỷ luôn lượt tải.
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export async function shareOrDownload(
  blob: Blob, fileName: string, title: string,
): Promise<ShareResult> {
  const file = new File([blob], fileName, { type: 'image/png' });

  if (canShareFiles([file])) {
    try {
      await navigator.share({ files: [file], title });
      return 'shared';
    } catch (err) {
      // Người dùng bấm huỷ cũng ném lỗi AbortError — đó không phải sự
      // cố, đừng lùi về tải file khiến máy tự tải một tấm ảnh họ vừa
      // từ chối chia sẻ.
      if (err instanceof Error && err.name === 'AbortError') return 'cancelled';
    }
  }

  download(file);
  return 'downloaded';
}
