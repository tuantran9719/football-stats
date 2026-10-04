"""
Chọn nguồn dữ liệu đang dùng.

Đổi nguồn = đặt biến môi trường `DATA_PROVIDER`, KHÔNG sửa mã:

    DATA_PROVIDER=espn    (mặc định)
    DATA_PROVIDER=demo    (dữ liệu đóng gói sẵn, không gọi mạng)

Thêm một nguồn mới: viết `app/providers/<tên>.py` có một lớp thoả
`FootballProvider` trong base.py, rồi thêm đúng một dòng vào `_FACTORIES`
bên dưới. Không có file nào khác trong dự án được phép nhắc tên nguồn.

Nạp theo kiểu lười (chỉ import khi được chọn) để một nguồn thiếu thư
viện hay hỏng cú pháp không làm sập cả server khi nó không được dùng.
"""
from __future__ import annotations

import os
from typing import Callable, Optional

from .base import FootballProvider, LeagueCatalogue

_provider: Optional[FootballProvider] = None


def _make_espn() -> FootballProvider:
    from .espn import EspnProvider
    return EspnProvider()


def _make_demo() -> FootballProvider:
    from .demo import DemoProvider
    return DemoProvider()


_FACTORIES: dict[str, Callable[[], FootballProvider]] = {
    "espn": _make_espn,
    "demo": _make_demo,
}

DEFAULT_PROVIDER = "espn"


def provider_name() -> str:
    return (os.getenv("DATA_PROVIDER") or DEFAULT_PROVIDER).strip().lower()


def get_provider() -> FootballProvider:
    global _provider
    if _provider is None:
        name = provider_name()
        factory = _FACTORIES.get(name)
        if factory is None:
            raise RuntimeError(
                f"DATA_PROVIDER={name!r} không có. Chọn một trong: "
                f"{', '.join(sorted(_FACTORIES))}"
            )
        _provider = factory()
    return _provider


def reset_provider() -> None:
    """Quên nguồn đang giữ. Dùng trong kiểm thử khi đổi DATA_PROVIDER."""
    global _provider
    _provider = None


def team_ref(external_id: str) -> str:
    """
    Mã đội đầy đủ, có tiền tố nguồn: "espn:359".

    Trước đây mỗi chỗ cần mã đều tự nối chuỗi "espn:" — bảy chỗ trong
    service.py và một chỗ trong giao diện. Đổi nguồn là phải đi sửa từng
    chỗ, và sót một chỗ thì lỗi không lộ ra ngay mà biểu hiện thành "đội
    yêu thích tự nhiên mất".
    """
    return f"{get_provider().prefix}:{external_id}"


def strip_ref(value: str) -> str:
    """Bỏ tiền tố nguồn khỏi mã, trả lại mã thô của nhà cung cấp."""
    return value.split(":", 1)[1] if ":" in value else value


def catalogue() -> LeagueCatalogue:
    return get_provider().catalogue()


def leagues_map() -> dict[str, str]:
    """Mã giải -> tên hiển thị, của nguồn đang chạy."""
    return catalogue().leagues


def cup_leagues_map() -> dict[str, str]:
    return catalogue().cups


def league_display_name(code: str) -> str:
    return catalogue().display_name(code)


def league_logo_url(code: str) -> Optional[str]:
    return catalogue().logo_url(code)
