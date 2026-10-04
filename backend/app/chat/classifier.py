"""
Bộ phân loại ý định. Hồi quy logistic đa lớp, tự viết, không thư viện.

Vì sao không dùng AI: bài toán ở đây là chọn một trong 17 nhóm từ một
câu ngắn trong miền cực hẹp. Đó là bài toán phân loại văn bản kinh
điển, giải tốt từ trước khi có mô hình ngôn ngữ lớn. Dùng AI cho việc
này vừa tốn tiền theo từng câu hỏi, vừa chậm hơn, mà lại thêm rủi ro
nó trả lời chệch ra ngoài phạm vi.

Vì sao không dùng numpy: cả bộ từ vựng chỉ vài nghìn đặc trưng, huấn
luyện xong trong vài chục mili-giây. Giữ được máy chủ triển khai nhẹ,
giống lý do mô hình Poisson cũng tự viết.

Điểm quan trọng nhất của lớp này KHÔNG phải là đoán đúng, mà là biết
lúc nào mình không chắc. Câu hỏi ngoài phạm vi phải rơi xuống dưới
ngưỡng để bot hỏi lại, chứ không được gán bừa vào nhóm gần nhất.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .normalize import features
from .intents import ALL_INTENTS, UNKNOWN


@dataclass
class Model:
    """Trọng số đã học. Đủ nhỏ để lưu thẳng ra JSON."""
    weights: dict[str, dict[str, float]] = field(default_factory=dict)
    bias: dict[str, float] = field(default_factory=dict)
    intents: list[str] = field(default_factory=list)
    """Số câu đã dùng để học, và độ chính xác đo trên phần giữ lại."""
    trained_on: int = 0
    accuracy: float = 0.0
    """Các câu bị đoán sai ở phần giữ lại. Chỉ để soi lúc chỉnh câu mẫu,
    không lưu ra file."""
    errors: list[tuple[str, str, str]] = field(default_factory=list)

    def known_feature(self, f: str) -> bool:
        return any(f in w for w in self.weights.values())


def _softmax(scores: dict[str, float]) -> dict[str, float]:
    top = max(scores.values())
    exp = {k: math.exp(v - top) for k, v in scores.items()}
    total = sum(exp.values()) or 1.0
    return {k: v / total for k, v in exp.items()}


def _scores(model: Model, feats: list[str]) -> dict[str, float]:
    out = {}
    for intent in model.intents:
        w = model.weights.get(intent, {})
        s = model.bias.get(intent, 0.0)
        for f in feats:
            s += w.get(f, 0.0)
        out[intent] = s
    return out


def train(
    examples: list[tuple[str, str]],
    epochs: int = 260,
    lr: float = 0.35,
    reg: float = 0.0009,
    holdout: float = 0.2,
    seed: int = 7,
) -> Model:
    """
    Học từ danh sách (câu, ý định).

    Chia một phần dữ liệu ra để CHẤM chứ không học, giống hệt cách
    trainer của mô hình Poisson chấm bằng điểm Brier. Con số chính xác
    đo được là thứ quyết định có nhận mô hình mới hay không khi về sau
    nó học thêm từ câu hỏi thật của người dùng — không có nó thì dữ
    liệu rác lẳng lặng làm bot dốt đi mà không ai biết.
    """
    rng = random.Random(seed)
    data = [(text, features(text), intent) for text, intent in examples if text.strip()]
    data = [(t, f, i) for t, f, i in data if f]
    if not data:
        return Model()

    intents = sorted({i for _, _, i in data})

    # Chia theo TỪNG ý định để phần giữ lại không bị thiếu hẳn một
    # nhóm — với nhóm chỉ có hơn chục câu, chia ngẫu nhiên cả đống dễ
    # bỏ sót nguyên một ý định và làm con số chính xác vô nghĩa.
    by_intent: dict[str, list[tuple[str, list[str]]]] = {i: [] for i in intents}
    for text, feats, intent in data:
        by_intent[intent].append((text, feats))

    train_set: list[tuple[str, list[str], str]] = []
    test_set: list[tuple[str, list[str], str]] = []
    for intent, items in by_intent.items():
        rng.shuffle(items)
        cut = max(1, int(len(items) * (1 - holdout))) if len(items) > 2 else len(items)
        train_set += [(t, f, intent) for t, f in items[:cut]]
        test_set += [(t, f, intent) for t, f in items[cut:]]

    model = Model(
        weights={i: {} for i in intents},
        bias={i: 0.0 for i in intents},
        intents=intents,
    )

    order = list(range(len(train_set)))
    for epoch in range(epochs):
        rng.shuffle(order)
        # Bước học nhỏ dần về cuối: đi nhanh lúc đầu rồi hạ xuống để
        # không nảy quanh nghiệm.
        step = lr * (1.0 - 0.7 * epoch / max(1, epochs - 1))
        for idx in order:
            _, feats, gold = train_set[idx]
            probs = _softmax(_scores(model, feats))
            for intent in intents:
                err = (1.0 if intent == gold else 0.0) - probs[intent]
                if abs(err) < 1e-9:
                    continue
                w = model.weights[intent]
                model.bias[intent] += step * err
                for f in feats:
                    w[f] = w.get(f, 0.0) + step * (err - reg * w.get(f, 0.0))

    # Cắt bỏ trọng số gần như bằng không: giảm hẳn kích thước file lưu
    # mà không đổi kết quả.
    for intent in intents:
        model.weights[intent] = {
            f: round(v, 5) for f, v in model.weights[intent].items() if abs(v) > 0.01
        }

    if test_set:
        hit = 0
        for text, feats, gold in test_set:
            got = _best(model, feats)[0]
            if got == gold:
                hit += 1
            else:
                model.errors.append((text, gold, got))
        model.accuracy = hit / len(test_set)
    model.trained_on = len(data)
    return model


def _best(model: Model, feats: list[str]) -> tuple[str, float]:
    probs = _softmax(_scores(model, feats))
    intent = max(probs, key=lambda k: probs[k])
    return intent, probs[intent]


def classify(model: Model, text: str) -> tuple[str, float, list[tuple[str, float]]]:
    """
    Trả về (ý định, độ tin cậy, ba lựa chọn hàng đầu).

    Câu không có lấy một từ nào từng gặp thì trả UNKNOWN với độ tin cậy
    0 ngay, không qua softmax: khi mọi đặc trưng đều lạ thì điểm của
    mọi nhóm đều bằng bias, softmax cho ra một phân phối gần đều nhưng
    vẫn có nhóm cao nhất — đủ để lọt ngưỡng một cách vô nghĩa.
    """
    if not model.intents:
        return UNKNOWN, 0.0, []

    all_feats = features(text)
    feats = [f for f in all_feats if model.known_feature(f)]
    if not feats:
        return UNKNOWN, 0.0, []

    probs = _softmax(_scores(model, feats))
    ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)

    # Hạ độ tin cậy theo tỉ lệ từ KHÔNG nhận ra trong câu.
    #
    # Softmax chỉ so các nhóm với nhau, nó không có cách nào biểu đạt
    # "câu này phần lớn là chữ lạ". Một câu mười từ mà chỉ hai từ từng
    # gặp vẫn có thể cho ra 90% cho một nhóm nào đó, vì tám từ kia
    # không bỏ phiếu. Nhân thêm độ phủ để câu càng lạ thì càng dễ rơi
    # xuống dưới ngưỡng và được hỏi lại.
    words = [f for f in all_feats if f.startswith("w:")]
    if words:
        known = sum(1 for f in words if model.known_feature(f))
        coverage = known / len(words)
        damp = 0.45 + 0.55 * coverage
    else:
        damp = 0.45
    ranked = [(i, p * damp) for i, p in ranked]
    return ranked[0][0], ranked[0][1], ranked[:3]


def seed_model() -> Model:
    """Mô hình học từ câu mẫu viết sẵn, chưa có gì từ người dùng thật."""
    from .intents import SEEDS
    # Bỏ câu trùng: viết tay nhiều đợt nên có câu lặp, mà câu lặp thì
    # được học hai lần và kéo lệch trọng số về phía nó.
    seen: set[str] = set()
    examples: list[tuple[str, str]] = []
    for intent, texts in SEEDS.items():
        for text in texts:
            key = text.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            examples.append((text, intent))
    return train(examples)
