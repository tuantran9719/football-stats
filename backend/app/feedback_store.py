"""
Hộp thư góp ý của người dùng.

Hai đường ra, cố tình tách rời nhau:

  1. LƯU VÀO FILE — luôn luôn chạy. Góp ý không bao giờ được mất chỉ vì
     máy chủ mail trục trặc hay chưa kịp cấu hình.
  2. GỬI EMAIL — chỉ chạy khi đã khai báo SMTP trong .env. Gửi hỏng thì
     ghi log rồi thôi, người dùng vẫn nhận được "đã gửi" vì góp ý của họ
     thực sự đã nằm an toàn trong file.

Không dùng cơ sở dữ liệu, giống các phần còn lại của backend: một file
JSON nối thêm dòng là đủ cho lượng góp ý của một app cỡ này, và đọc bằng
mắt cũng được.
"""
from __future__ import annotations
import asyncio
import json
import os
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Optional
from .paths import data_file

_FILE = data_file("feedback.json")
_lock = asyncio.Lock()

# Địa chỉ nhận góp ý — CHỈ lấy từ biến môi trường.
#
# Trước đây có một địa chỉ nhúng cứng ở đây cho tiện. Mã nguồn lên
# GitHub thì địa chỉ đó đi theo và bị máy quét thư rác nhặt được, nên
# chuyển hẳn sang cấu hình. Không đặt thì lùi về tài khoản SMTP đang
# dùng để gửi, vì gửi cho chính mình gần như luôn là ý định đúng.
DEFAULT_TO = ""

MAX_MESSAGE = 4000
MAX_CONTACT = 200


def _load() -> list[dict[str, Any]]:
    if not _FILE.exists():
        return []
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # File hỏng thì bắt đầu lại từ đầu còn hơn là làm sập cả endpoint.
        return []


def _save(items: list[dict[str, Any]]) -> None:
    tmp = _FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    # Ghi ra file tạm rồi đổi tên: mất điện giữa chừng cũng không để lại
    # file JSON dở dang.
    tmp.replace(_FILE)


def _send_email(entry: dict[str, Any]) -> Optional[str]:
    """
    Gửi một góp ý qua SMTP. Trả về None nếu xong, hoặc mô tả lỗi.

    Chưa khai báo SMTP thì trả về lý do chứ KHÔNG coi là lỗi: đó là
    trạng thái bình thường khi chạy ở máy cá nhân.
    """
    host = os.getenv("FEEDBACK_SMTP_HOST")
    user = os.getenv("FEEDBACK_SMTP_USER")
    password = os.getenv("FEEDBACK_SMTP_PASS")
    if not (host and user and password):
        return "chưa cấu hình SMTP"

    # Không khai FEEDBACK_TO thì gửi về chính tài khoản đang dùng để
    # gửi — gần như luôn là ý định đúng, và không để góp ý rơi vào hư vô.
    to_addr = os.getenv("FEEDBACK_TO") or DEFAULT_TO or user
    port = int(os.getenv("FEEDBACK_SMTP_PORT", "587"))

    msg = EmailMessage()
    msg["Subject"] = f"[Football Stats] {entry['kind']} — góp ý mới"
    msg["From"] = user
    msg["To"] = to_addr
    if entry.get("contact"):
        # Bấm Trả lời là trả lời thẳng cho người gửi góp ý.
        msg["Reply-To"] = entry["contact"]

    msg.set_content(
        f"Loại:      {entry['kind']}\n"
        f"Liên hệ:   {entry.get('contact') or '(không để lại)'}\n"
        f"Ngôn ngữ:  {entry.get('lang') or '?'}\n"
        f"Thiết bị:  {entry.get('platform') or '?'}\n"
        f"Lúc:       {entry['at']}\n"
        f"\n{'-' * 48}\n\n"
        f"{entry['message']}\n"
    )

    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
        return None
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


async def add(
    message: str, kind: str, contact: Optional[str],
    lang: Optional[str], platform: Optional[str],
) -> dict[str, Any]:
    entry = {
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "kind": kind,
        "message": message[:MAX_MESSAGE],
        "contact": (contact or "")[:MAX_CONTACT] or None,
        "lang": lang,
        "platform": platform,
    }

    async with _lock:
        items = _load()
        items.append(entry)
        _save(items)

    # Gửi mail ở luồng riêng: smtplib chặn luồng, để nguyên sẽ treo cả
    # server trong lúc chờ máy chủ mail trả lời.
    err = await asyncio.to_thread(_send_email, entry)
    if err:
        print(f"[feedback] đã lưu nhưng chưa gửi mail được: {err}")

    return {"stored": True, "emailed": err is None}


async def count() -> int:
    async with _lock:
        return len(_load())
