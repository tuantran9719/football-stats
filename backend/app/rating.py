"""
Điểm số liệu của từng cầu thủ sau trận. Tự tính, không lấy từ đâu.

PHẢI ĐỌC TRƯỚC KHI DÙNG: đây KHÔNG phải điểm đánh giá màn trình diễn
như Sofascore hay WhoScored. Nguồn dữ liệu chỉ ghi nhận 15 chỉ số, và
trong đó KHÔNG có số đường chuyền, tỉ lệ chuyền chính xác, tắc bóng,
cắt bóng, tranh chấp tay đôi, hay số phút thi đấu.

Hệ quả phải nói thẳng: một trung vệ chơi hay cả trận mà không ghi bàn,
không phạm lỗi thì không có gì được ghi nhận, nên điểm đúng bằng điểm
nền. Điểm này phân biệt tốt "có đóng góp đo được" với "không có gì đo
được", chứ không phân biệt được "chơi hay" với "chơi dở" ở các vị trí
mà đóng góp chính không nằm trong 15 chỉ số đó.

Vì vậy giao diện luôn hiện kèm lời giải thích, và tuyệt đối không gọi
nó là "điểm phong độ" hay "chấm điểm cầu thủ".

Cách tính cố ý đơn giản và cộng trừ thẳng: ai cũng tự kiểm lại được
bằng tay từ bảng số liệu ngay bên cạnh. Một công thức tinh vi mà không
giải thích nổi thì tệ hơn hẳn, vì người đọc không có cách nào biết nó
đúng hay sai.
"""
from __future__ import annotations

from typing import Optional

from .models import LineupPlayer

# Điểm nền của một cầu thủ có ra sân mà chưa có gì được ghi nhận.
BASE = 6.0

MIN_SCORE = 3.0
MAX_SCORE = 10.0


def _is_keeper(player: LineupPlayer) -> bool:
    pos = (player.position or "").upper()
    return pos.startswith("G")


def _is_defender(player: LineupPlayer) -> bool:
    pos = (player.position or "").upper()
    return pos.startswith(("D", "CD", "LB", "RB", "SW"))


def score(player: LineupPlayer, team_conceded: Optional[int] = None) -> Optional[float]:
    """
    Điểm 3-10 cho một cầu thủ đã ra sân.

    `team_conceded` là số bàn đội nhà lọt lưới cả trận, dùng để thưởng
    cho thủ môn và hậu vệ giữ sạch lưới — thứ duy nhất đo được công của
    hàng thủ trong bộ chỉ số ít ỏi này.
    """
    if not player.starter and not player.subbedIn:
        return None

    s = BASE

    # Đóng góp tấn công, tính cho mọi vị trí. Hậu vệ ghi bàn hiếm hơn
    # nên cùng số điểm nhưng hiếm khi xảy ra, không cần hệ số riêng.
    s += 1.30 * player.goals
    s += 0.90 * player.assists
    s += 0.18 * player.shotsOnTarget
    s += 0.05 * max(0, player.shots - player.shotsOnTarget)

    # Kỷ luật.
    s += 0.04 * player.foulsSuffered
    s -= 0.07 * player.foulsCommitted
    s -= 0.05 * player.offsides
    s -= 0.40 * player.yellowCards
    s -= 1.50 * player.redCards
    s -= 1.60 * player.ownGoals

    if _is_keeper(player):
        # Cứu thua là chỉ số DUY NHẤT đo được công của thủ môn, nên hệ
        # số cao hơn hẳn; bàn thua trừ điểm nhưng không trừ nặng vì
        # phần lớn bàn thua không phải lỗi thủ môn.
        s += 0.30 * player.saves
        s -= 0.45 * player.goalsConceded
        if player.goalsConceded == 0 and player.starter:
            s += 0.70
    elif _is_defender(player) and team_conceded == 0 and player.starter:
        s += 0.50

    # Vào sân từ ghế dự bị thì số liệu ít đi theo số phút, nên kéo về
    # gần điểm nền: không phạt ai vì đá có 10 phút, cũng không thưởng
    # quá tay cho một pha chạm bóng.
    if player.subbedIn and not player.starter:
        s = BASE + (s - BASE) * 0.75

    return round(max(MIN_SCORE, min(MAX_SCORE, s)), 1)


def apply_to(lineups: list, home_score: Optional[int], away_score: Optional[int]) -> None:
    """
    Gán điểm cho mọi cầu thủ trong hai đội hình, tại chỗ.

    Trận chưa đá (chưa có tỉ số) thì bỏ qua hẳn: chấm điểm một trận chưa
    diễn ra là vô nghĩa.
    """
    if home_score is None or away_score is None:
        return
    for team in lineups:
        conceded = away_score if team.side == "home" else home_score
        for player in (*team.starters, *team.bench):
            player.rating = score(player, conceded)
