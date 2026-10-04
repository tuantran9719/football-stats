"""
Nơi duy nhất quyết định dữ liệu ghi xuống đâu.

Chạy ở máy cá nhân thì mặc định là backend/data — giữ nguyên như cũ.
Chạy trên máy chủ thuê (Railway, Render...) thì hệ thống tệp bị xoá sạch
mỗi lần deploy lại, nên phải trỏ vào ổ đĩa gắn thêm qua biến DATA_DIR.

Mức độ thiệt hại nếu mất, xếp từ nhẹ tới nặng:
  - ai_analysis_cache.json : chỉ là cache, mất thì gọi AI lại.
  - referee_stats.json     : tự tích luỹ lại khi người dùng xem trận.
  - feedback.json          : mất là mất hẳn, NHƯNG mỗi góp ý đều đã
                             được gửi song song qua email nên vẫn còn
                             bản lưu ở hộp thư.

Vì vậy chạy không có ổ đĩa gắn thêm vẫn chấp nhận được; có thì tốt hơn.
"""
from __future__ import annotations
import os
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parent.parent / "data"

DATA_DIR = Path(os.getenv("DATA_DIR") or _DEFAULT)


def data_file(name: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / name
