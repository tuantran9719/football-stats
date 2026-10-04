"""
Chuyển con số của mô hình thành câu chữ cho giao diện.

Giao diện hiện có hai khối chữ vốn do AI sinh ra: một đoạn nhận định và
một dòng ghi chú dưới tỉ số dự đoán. Để giữ nguyên giao diện mà bỏ được
AI, phần này dựng câu từ chính kết quả mô hình theo khuôn mẫu.

Đổi lại còn được hai thứ mà AI không cho:
  - Câu chữ LUÔN khớp với con số hiển thị, vì cùng một nguồn.
  - Không tốn hạn mức, không có ngày "hết lượt gọi" nên mục nhận định
    biến mất.

Dịch sẵn 12 ngôn ngữ, không gọi dịch vụ dịch thuật nào.
"""
from __future__ import annotations

from .model import Prediction

# {h} đội nhà, {a} đội khách, {ph}/{pd}/{pa} phần trăm thắng/hoà/thua,
# {g} tổng bàn kỳ vọng, {o} phần trăm trên 2.5 bàn, {b} phần trăm cả hai
# đội cùng ghi bàn, {n} số trận đã dùng để học.
_ANALYSIS = {
    "vi": "Mô hình đánh giá {h} thắng {ph}%, hoà {pd}%, {a} thắng {pa}%. "
          "Kỳ vọng {g} bàn cả trận — khả năng trên 2,5 bàn là {o}%, "
          "hai đội cùng ghi bàn {b}%. Học từ {n} trận đã đá của giải.",
    "en": "The model gives {h} {ph}%, draw {pd}%, {a} {pa}%. "
          "Expected {g} goals — {o}% chance of over 2.5, "
          "{b}% both teams to score. Learned from {n} completed matches.",
    "es": "El modelo da {h} {ph}%, empate {pd}%, {a} {pa}%. "
          "Se esperan {g} goles — {o}% de más de 2,5, "
          "{b}% ambos marcan. Aprendido de {n} partidos jugados.",
    "pt": "O modelo dá {h} {ph}%, empate {pd}%, {a} {pa}%. "
          "Esperam-se {g} golos — {o}% de mais de 2,5, "
          "{b}% ambas marcam. Aprendido com {n} jogos disputados.",
    "fr": "Le modèle donne {h} {ph}%, nul {pd}%, {a} {pa}%. "
          "{g} buts attendus — {o}% de plus de 2,5, "
          "{b}% les deux marquent. Appris sur {n} matchs joués.",
    "de": "Das Modell gibt {h} {ph}%, Unentschieden {pd}%, {a} {pa}%. "
          "Erwartet {g} Tore — {o}% für über 2,5, "
          "{b}% beide treffen. Gelernt aus {n} gespielten Partien.",
    "it": "Il modello dà {h} {ph}%, pareggio {pd}%, {a} {pa}%. "
          "Attesi {g} gol — {o}% di over 2,5, "
          "{b}% entrambe segnano. Appreso da {n} partite giocate.",
    "id": "Model memberi {h} {ph}%, seri {pd}%, {a} {pa}%. "
          "Perkiraan {g} gol — peluang over 2,5 sebesar {o}%, "
          "{b}% kedua tim mencetak gol. Dipelajari dari {n} laga.",
    "th": "โมเดลให้ {h} {ph}% เสมอ {pd}% {a} {pa}% "
          "คาดว่ามี {g} ประตู — โอกาสสูงกว่า 2.5 ประตูคือ {o}% "
          "ยิงได้ทั้งสองทีม {b}% เรียนรู้จาก {n} นัดที่แข่งจบ",
    "ja": "モデルの評価は {h} {ph}%、引き分け {pd}%、{a} {pa}%。"
          "予想得点は {g}、2.5ゴール オーバーの確率 {o}%、"
          "両チーム得点 {b}%。消化済み {n} 試合から学習。",
    "ko": "모델 예측: {h} {ph}%, 무승부 {pd}%, {a} {pa}%. "
          "예상 득점 {g}골 — 2.5골 오버 확률 {o}%, "
          "양 팀 득점 {b}%. 종료된 {n}경기로 학습했습니다.",
    "zh": "模型给出 {h} {ph}%、平局 {pd}%、{a} {pa}%。"
          "预期进球 {g} — 大于2.5球的概率为 {o}%，"
          "双方均进球 {b}%。基于 {n} 场已结束的比赛学习。",
}

_NOTE = {
    "vi": "Tỉ số khả dĩ nhất ({p}%). Tính bằng mô hình Poisson học từ {n} trận",
    "en": "Most likely score ({p}%). From a Poisson model trained on {n} matches",
    "es": "Resultado más probable ({p}%). Modelo de Poisson con {n} partidos",
    "pt": "Resultado mais provável ({p}%). Modelo de Poisson com {n} jogos",
    "fr": "Score le plus probable ({p}%). Modèle de Poisson sur {n} matchs",
    "de": "Wahrscheinlichstes Ergebnis ({p}%). Poisson-Modell aus {n} Spielen",
    "it": "Risultato più probabile ({p}%). Modello di Poisson su {n} partite",
    "id": "Skor paling mungkin ({p}%). Model Poisson dari {n} laga",
    "th": "สกอร์ที่เป็นไปได้มากที่สุด ({p}%) จากโมเดล Poisson ที่เรียนรู้จาก {n} นัด",
    "ja": "最も可能性の高いスコア({p}%)。{n} 試合で学習したポアソンモデル",
    "ko": "가장 가능성 높은 스코어 ({p}%). {n}경기로 학습한 푸아송 모델",
    "zh": "最可能的比分（{p}%）。基于 {n} 场比赛训练的泊松模型",
}


def _pick(table: dict[str, str], lang: str) -> str:
    return table.get(lang) or table["en"]


def analysis(
    p: Prediction, home_name: str, away_name: str, matches: int, lang: str,
) -> str:
    return _pick(_ANALYSIS, lang).format(
        h=home_name, a=away_name,
        ph=round(p.prob_home * 100), pd=round(p.prob_draw * 100),
        pa=round(p.prob_away * 100),
        g=f"{p.expected_goals:.1f}",
        o=round(p.prob_over25 * 100), b=round(p.prob_btts * 100),
        n=matches,
    )


def note(p: Prediction, matches: int, lang: str) -> str:
    return _pick(_NOTE, lang).format(p=round(p.top_score_prob * 100), n=matches)
