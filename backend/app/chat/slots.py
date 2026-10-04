"""
Rút các tham số cụ thể ra khỏi câu hỏi.

Biết người dùng hỏi về "trên/dưới" mới là một nửa việc; nửa còn lại là
mốc bao nhiêu và hỏi về đội nào. "Trên 2.5 bàn" và "trên 3.5 bàn" cùng
một ý định nhưng hai câu trả lời khác hẳn.

Phần này cố ý KHÔNG đoán khi không chắc: không thấy mốc thì trả về
None để answer.py dùng mốc mặc định và NÓI RÕ là đang dùng mốc nào.
Thà trả lời mốc 2.5 và ghi rõ "mốc 2.5" còn hơn đoán bừa ra mốc 3.5
rồi người đọc tưởng mình hỏi gì được nấy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .normalize import normalize, strip_accents

# Từ báo hiệu người dùng hỏi phía "dưới mốc" thay vì "trên mốc".
_UNDER = {"duoi", "xiu", "under", "below", "it", "itnhat", "duoimuc"}
_OVER = {"tren", "tai", "hon", "over", "above", "vuot"}

# Từ chỉ đội theo vị trí, không cần biết tên.
_HOME_WORDS = {"nha", "chunha", "home"}
_AWAY_WORDS = {"khach", "away", "doikhach"}

# Những chữ có trong tên CLB nhưng không giúp phân biệt đội nào, vì
# hàng chục đội cùng mang. Bỏ đi để "united" trong "Manchester United"
# không khớp nhầm sang "Newcastle United".
_WEAK_NAME_WORDS = {
    "fc", "cf", "sc", "ac", "as", "cd", "ca", "club", "city", "united",
    "real", "athletic", "atletico", "sporting", "deportivo", "football",
    "de", "do", "da", "the", "and", "team", "doi",
}


@dataclass
class Slots:
    """Mốc số, hướng hỏi, và đội được nhắc tới. Thiếu thì để None."""
    line: Optional[float] = None
    under: bool = False
    side: Optional[str] = None
    """True khi người dùng gõ rõ một con số, để câu trả lời biết mình
    đang dùng mốc người ta hỏi hay mốc mặc định."""
    line_given: bool = False


def _numbers(text: str) -> list[float]:
    out = []
    for raw in re.findall(r"-?\d+(?:\.\d+)?", text):
        try:
            out.append(float(raw))
        except ValueError:
            pass
    return out


def _name_tokens(*names: Optional[str]) -> set[str]:
    """Các chữ đủ đặc trưng để nhận ra một đội."""
    out: set[str] = set()
    for name in names:
        if not name:
            continue
        for tok in strip_accents(name.lower()).replace("-", " ").split():
            tok = re.sub(r"[^a-z0-9]", "", tok)
            if len(tok) >= 3 and tok not in _WEAK_NAME_WORDS:
                out.add(tok)
    return out


def _side_from_names(
    words: list[str],
    home_tokens: set[str],
    away_tokens: set[str],
) -> Optional[str]:
    """
    Đoán đội theo tên xuất hiện trong câu.

    Chỉ nhận khi đúng MỘT đội khớp. Hai đội cùng khớp nghĩa là câu hỏi
    nhắc cả hai ("Arsenal gặp Leeds ai thắng") — đó là câu hỏi về cả
    trận chứ không về riêng đội nào.
    """
    hit_home = any(w in home_tokens for w in words)
    hit_away = any(w in away_tokens for w in words)

    # Khớp một phần đầu từ, để "mancity", "arsen", "barca" vẫn nhận ra.
    if not hit_home:
        hit_home = any(len(w) >= 4 and any(t.startswith(w) or w.startswith(t)
                       for t in home_tokens) for w in words)
    if not hit_away:
        hit_away = any(len(w) >= 4 and any(t.startswith(w) or w.startswith(t)
                       for t in away_tokens) for w in words)

    if hit_home and not hit_away:
        return "home"
    if hit_away and not hit_home:
        return "away"
    return None


def extract(
    text: str,
    home_name: Optional[str] = None,
    away_name: Optional[str] = None,
    home_short: Optional[str] = None,
    away_short: Optional[str] = None,
) -> Slots:
    norm = normalize(text)
    words = norm.split()
    slots = Slots()

    nums = _numbers(norm)
    if nums:
        slots.line = nums[0]
        slots.line_given = True

    if any(w in _UNDER for w in words):
        slots.under = True
    elif any(w in _OVER for w in words):
        slots.under = False

    # Vị trí ("đội nhà" / "đội khách") được ưu tiên hơn tên đội: người
    # gõ rõ "đội khách" thì không còn gì phải đoán.
    joined = "".join(words)
    if any(w in _HOME_WORDS for w in words) or "doinha" in joined or "sannha" in joined:
        slots.side = "home"
    elif any(w in _AWAY_WORDS for w in words) or "doikhach" in joined:
        slots.side = "away"
    else:
        slots.side = _side_from_names(
            words, _name_tokens(home_name, home_short), _name_tokens(away_name, away_short),
        )

    return slots
