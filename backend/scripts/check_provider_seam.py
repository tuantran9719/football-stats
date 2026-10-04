#!/usr/bin/env python3
"""
Chốt chặn: không file nào ngoài `app/providers/` được nhắc tên nguồn.

Vì sao cần một kiểm tra tự động thay vì chỉ dặn nhau: ranh giới kiểu
này luôn mục dần. Một lần ai đó (kể cả tôi) viết nhanh `f"espn:{id}"`
cho xong việc, lỗi không hiện ra ngay — mọi thứ vẫn chạy đúng vì đang
dùng ESPN. Nó chỉ nổ vào đúng ngày phải đổi nguồn, tức ngày tệ nhất.

Chạy: python3 scripts/check_provider_seam.py
Trả mã khác 0 nếu có rò rỉ, để cắm vào CI hay git hook được.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
ALLOWED_DIR = APP / "providers"

# Tên các nguồn đã biết. Thêm nguồn mới thì thêm vào đây.
NAMES = ("espn", "demo")

# Chỉ soi mã thật, không soi chú thích và chuỗi tài liệu: chú thích
# được phép nhắc tên nguồn để giải thích lịch sử.
COMMENT = re.compile(r"#.*$")


def code_lines(path: Path):
    text = path.read_text(encoding="utf-8")
    in_doc = False
    for n, raw in enumerate(text.splitlines(), 1):
        line = COMMENT.sub("", raw)
        ticks = line.count('"""') + line.count("'''")
        if in_doc:
            in_doc = ticks % 2 == 0
            continue
        if ticks:
            in_doc = ticks % 2 == 1
            # Phần trước dấu mở ngoặc vẫn là mã.
            line = line.split('"""')[0].split("'''")[0]
        yield n, line


def main() -> int:
    bad: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        if ALLOWED_DIR in path.parents or path == ALLOWED_DIR:
            continue
        if "__pycache__" in path.parts:
            continue
        for n, line in code_lines(path):
            low = line.lower()
            for name in NAMES:
                if name in low:
                    bad.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()}")
                    break

    if bad:
        print("Rò rỉ tên nguồn ra ngoài app/providers/:\n")
        for b in bad:
            print("  " + b)
        print(
            "\nHãy dùng providers.team_ref() / providers.leagues_map() /"
            "\nget_provider() thay vì gọi thẳng tên nguồn."
        )
        return 1

    print(f"Sạch: không file nào ngoài app/providers/ nhắc tới {', '.join(NAMES)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
