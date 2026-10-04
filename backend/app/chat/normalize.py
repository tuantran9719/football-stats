"""
Chuẩn hoá câu người dùng gõ trước khi phân loại.

Người Việt gõ nhanh trên điện thoại thì bỏ dấu, viết tắt, và sai chính
tả là chuyện thường: "tran nay co nhieu ban ko", "ti so bn v", "trên
2.5 ăn ko". Nếu so chữ nguyên văn thì mỗi biến thể là một câu khác
nhau và bộ phân loại phải học lại từ đầu cho từng biến thể.

Cách xử lý: ép mọi câu về một dạng chuẩn duy nhất — bỏ dấu, viết
thường, giãn các từ viết tắt ra — rồi mới so. Nhờ vậy "trận này mấy
bàn", "tran nay may ban" và "tran nay may ban?" là CÙNG một câu với
bộ phân loại, và một câu mẫu dạy được cho cả chục cách gõ.

Bỏ dấu tiếng Việt nghe có vẻ làm mất thông tin, nhưng trong miền hẹp
này gần như không có cặp từ nào phân biệt nhau chỉ bằng dấu mà lại
khác ý: "bàn" và "bán", "thẻ" và "thế" không bao giờ cùng xuất hiện
trong một câu hỏi bóng đá theo cách gây nhầm.
"""
from __future__ import annotations

import re
import unicodedata

# Viết tắt hay gặp, tra theo dạng ĐÃ bỏ dấu. Chỉ nhận những chữ mà
# trong ngữ cảnh hỏi bóng đá chỉ có một nghĩa — "v" (và / với / vậy)
# hay "m" thì cố tình bỏ qua vì đoán sai còn hại hơn không đoán.
_ABBREV = {
    "ko": "khong", "k": "khong", "kg": "khong", "hok": "khong",
    "hong": "khong", "khg": "khong", "kh": "khong",
    "dc": "duoc", "đc": "duoc", "dk": "duoc khong",
    "bn": "bao nhieu", "bnhieu": "bao nhieu",
    "ntn": "nhu the nao", "tn": "the nao",
    "tl": "ty le", "tle": "ty le",
    "ts": "ty so", "tiso": "ty so", "tyso": "ty so",
    "dd": "doi dau", "h2h": "doi dau",
    "pd": "phong do",
    "trc": "truoc", "sau": "sau",
    "j": "gi", "z": "gi",
    "cthuong": "chan thuong", "ct": "chan thuong",
    "pg": "phat goc", "gc": "phat goc",
    "tv": "the vang", "td": "the do",
    "h1": "hiep 1", "h2": "hiep 2",
    "ou": "over under", "o/u": "over under",
    "sl": "so luong",
    "dhinh": "doi hinh", "dh": "doi hinh",
    "bxh": "bang xep hang",
    "cb": "ca hai", "2d": "hai doi",
}


# Các cách viết khác nhau của cùng một từ, gộp lại sau khi đã bỏ dấu.
# Tiếng Việt cho phép cả "tỉ" lẫn "tỷ", và cả hai đều đúng chính tả.
_PHRASES = [
    ("ti so", "ty so"),
    ("ti le", "ty le"),
    ("ti  so", "ty so"),
    ("ban thang", "ban"),
    ("qua phat goc", "phat goc"),
    ("goc phat", "phat goc"),
    ("sach luoi", "giu sach luoi"),
    ("giu giu sach luoi", "giu sach luoi"),
]


def strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt. 'đ' phải xử lý riêng vì nó không phải d + dấu."""
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def normalize(text: str) -> str:
    """Đưa câu về dạng chuẩn: thường, không dấu, không viết tắt."""
    text = strip_accents(text.lower())

    # "2,5" là cách viết số thập phân của tiếng Việt; đổi sang dấu chấm
    # để phần rút số chỉ phải xử lý một dạng. Chỉ đổi khi dấu phẩy nằm
    # giữa hai chữ số, để không phá dấu phẩy ngăn vế câu.
    text = re.sub(r"(\d),(\d)", r"\1.\2", text)

    # Giữ lại chữ, số, dấu chấm trong số, và dấu trừ của mốc chấp âm.
    text = re.sub(r"[^a-z0-9.\-\s]", " ", text)
    # Dấu chấm chỉ có nghĩa khi nằm giữa hai chữ số ("2.5"), còn lại là
    # dấu câu.
    text = re.sub(r"\.(?!\d)", " ", text)
    text = re.sub(r"(?<!\d)\.", " ", text)
    # Dấu trừ cũng vậy: "-1.5" giữ, "doi-nha" tách ra.
    text = re.sub(r"-(?!\d)", " ", text)
    text = re.sub(r"(?<![\s\d])-", " ", text)

    words = [_ABBREV.get(w, w) for w in text.split()]
    out = " ".join(" ".join(words).split())
    for src_phrase, dst in _PHRASES:
        out = out.replace(src_phrase, dst)
    return " ".join(out.split())


def tokens(text: str) -> list[str]:
    """Các từ của câu đã chuẩn hoá."""
    return normalize(text).split()


def features(text: str) -> list[str]:
    """
    Đặc trưng để phân loại: từng từ, và từng cặp từ liền nhau.

    Cặp từ là thứ phân biệt được những câu mà nếu chỉ nhìn từng từ rời
    thì giống hệt nhau: "trên 2.5 bàn" với "dưới 2.5 bàn" khác nhau ở
    đúng một từ, nhưng "hiệp 1" với "hiệp 2" thì chỉ cặp từ mới thấy.
    """
    toks = tokens(text)
    out = [f"w:{t}" for t in toks]
    out += [f"b:{a}_{b}" for a, b in zip(toks, toks[1:])]

    # Mẩu ba ký tự của từng từ dài. Đây là cách rẻ nhất để "card" và
    # "cards", "injury" và "injured", "thang" và "thắng" chia sẻ được
    # phần đã học, thay vì mỗi biến thể là một từ hoàn toàn mới. Cũng
    # nhờ vậy mà gõ sai một chữ cái vẫn còn phần lớn mẩu khớp.
    for t in toks:
        if len(t) >= 4:
            padded = f"<{t}>"
            out += [f"c:{padded[i:i + 3]}" for i in range(len(padded) - 2)]
    return out
