"""
Thiết lập chung cho toàn bộ kiểm thử.

Hai nguyên tắc:

  1. KHÔNG GỌI MẠNG. Mọi bài chạy với nguồn dữ liệu mẫu (`demo`). Bài
     kiểm thử phụ thuộc internet thì sẽ đỏ vào những hôm nhà cung cấp
     chặn tần suất — và lúc đó không ai còn tin nó nữa.

  2. KHÔNG ĐỤNG DỮ LIỆU THẬT. Mỗi lần chạy dùng một thư mục dữ liệu
     tạm riêng, nên không thể vô tình ghi đè hệ số mô hình hay bộ phân
     loại đã học.
"""
from __future__ import annotations

import os
import tempfile

import pytest

# Phải đặt TRƯỚC khi import app: paths.py đọc DATA_DIR lúc nạp mô-đun,
# còn providers/__init__ đọc DATA_PROVIDER lúc tạo nguồn lần đầu.
_TMP = tempfile.mkdtemp(prefix="fb-test-")
os.environ["DATA_DIR"] = _TMP
os.environ["DATA_PROVIDER"] = "demo"


@pytest.fixture(scope="session")
def data_dir() -> str:
    return _TMP


@pytest.fixture(scope="session")
def client():
    """Gọi API trực tiếp qua ASGI, không mở cổng mạng nào."""
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
