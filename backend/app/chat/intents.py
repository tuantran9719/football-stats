"""
Danh sách những gì bot trả lời được, kèm câu mẫu để dạy bộ phân loại.

Đây là chỗ quyết định phạm vi của bot. Mỗi ý định phải có một hàm trả
lời tương ứng trong answer.py — thêm ý định mà quên hàm trả lời thì
kiểm thử báo lỗi ngay, cố ý để như vậy.

Vì sao chỉ chừng này ý định: trước trận người xem hỏi đi hỏi lại quanh
một nhúm chuyện. Giữ danh sách hẹp thì bộ phân loại học nhanh, ít nhầm,
và quan trọng hơn cả là nó BIẾT KHI NÀO NÓ KHÔNG BIẾT — câu ngoài danh
sách rơi xuống dưới ngưỡng tin cậy và bot hỏi lại thay vì bịa.

Câu mẫu viết như người thật gõ, kể cả sai chính tả và viết tắt, vì
normalize.py sẽ ép hết về một dạng. Không cần viết đủ mọi biến thể —
một câu mẫu có dấu đã dạy luôn được cách gõ không dấu.

Ngôn ngữ: tiếng Việt và tiếng Anh đã đủ dày để dùng thật. Mười thứ
tiếng còn lại hiện dựa vào nút bấm gợi ý (vẫn dịch đủ); thêm câu mẫu
cho chúng chỉ là nối thêm vào danh sách bên dưới, không phải sửa mã.
"""
from __future__ import annotations

# Ngưỡng tin cậy tối thiểu để dám trả lời. Dưới mức này bot hỏi lại
# kèm ba lựa chọn gần nhất — và chính cú bấm chọn đó là nhãn để học.
#
# Đặt hơi cao có chủ đích: trả lời sai một câu làm người dùng mất tin
# vào mọi con số khác trong app, còn hỏi lại chỉ tốn một lần chạm.
MIN_CONFIDENCE = 0.34

OUTCOME = "outcome"
SCORE = "score"
TOTAL_GOALS = "total_goals"
OVER_UNDER = "over_under"
BTTS = "btts"
HANDICAP = "handicap"
TEAM_GOALS = "team_goals"
CLEAN_SHEET = "clean_sheet"
CORNERS = "corners"
CARDS = "cards"
HALVES = "halves"
FORM = "form"
H2H = "h2h"
STANDINGS = "standings"
KICKOFF = "kickoff"
INJURIES = "injuries"
MODEL_INFO = "model_info"

# Nhóm "không thuộc phạm vi". Đây là một ý định THẬT chứ không phải chỗ
# chứa rác, và nó là thứ giữ cho bot trung thực.
#
# Không có nhóm này thì mọi câu đều buộc phải rơi vào một trong các
# nhóm còn lại, nên "hôm nay trời đẹp quá" vẫn được gán vào "ai thắng"
# với độ tin cậy cao — không phải vì mô hình tin, mà vì nó không có
# cửa nào khác để đi. Cho nó một cửa thoát hợp lệ thì phần xác suất
# dồn về đó và bot biết đường hỏi lại.
OTHER = "other"

UNKNOWN = "unknown"

SEEDS: dict[str, list[str]] = {
    OUTCOME: [
        "đội nào cửa trên", "ai nhỉnh hơn", "đội nào được đánh giá cao",
        "cơ hội thắng của hai đội", "bên nào có lợi thế",
        "đội nhà có lợi thế sân nhà không", "ai là ứng viên",
        "trận này nghiêng về đội nào", "khả năng thắng thua hoà",
        "odds of winning", "match outcome", "result prediction",
        "who is the favourite", "chances to win", "likely winner",
        "probability of each result",
        "ai thắng", "đội nào thắng", "ai sẽ thắng trận này", "bên nào thắng",
        "đội nào mạnh hơn", "đội nào được đánh giá cao hơn", "ai cửa trên",
        "tỷ lệ thắng bao nhiêu", "khả năng thắng của đội nhà",
        "trận này ai hơn", "dự đoán kết quả", "kết quả thế nào",
        "có hoà không", "khả năng hoà bao nhiêu", "hoà được không",
        "đội khách thắng được không", "đội nhà có thắng không",
        "ai thắng ai thua", "nhận định trận này", "trận này thế nào",
        "who wins", "who will win", "which team is stronger",
        "win probability", "chance of a draw", "will it be a draw",
        "match result", "predict the result",
    ],
    SCORE: [
        "trận này tỷ số bao nhiêu", "trận này mấy mấy",
        "trận này tỷ số thế nào",
        "tỷ số kết thúc là bao nhiêu", "đoán tỷ số đi",
        "ba tỷ số dễ ra nhất", "tỷ số nào hay gặp", "scoreline",
        "what will the final score be", "score prediction", "likely scores",
        "final score",
        "tỷ số bao nhiêu", "dự đoán tỷ số", "tỷ số thế nào",
        "tỷ số khả dĩ nhất", "tỷ số chính xác", "mấy mấy",
        "kết thúc mấy mấy", "trận này mấy mấy", "tỷ số dự đoán là gì",
        "các tỷ số hay xảy ra", "tỷ số nào dễ ra nhất",
        "what is the score", "predicted score", "most likely scoreline",
        "correct score", "exact score prediction",
    ],
    TOTAL_GOALS: [
        "trận này mấy bàn", "trận này bao nhiêu bàn",
        "trận này được mấy bàn", "trận này mấy trái",
        "trận này dự kiến mấy bàn",
        "trận này căng không", "trận này ít bàn không",
        "nhiều bàn thắng không", "số bàn cả trận", "tổng số bàn dự kiến",
        "trận này có nổ không", "goal expectancy", "number of goals",
        "how many goals in total", "will it be open or tight",
        "mấy bàn", "bao nhiêu bàn", "tổng bàn thắng",
        "trận này nhiều bàn không", "có nhiều bàn thắng không",
        "kỳ vọng bàn thắng", "dự đoán số bàn thắng",
        "trận này có bàn thắng không", "trận này ít bàn phải không",
        "trận này căng không", "bao nhiêu bàn cả trận",
        "how many goals", "total goals", "will there be many goals",
        "is it a high scoring match", "expected goals",
    ],
    OVER_UNDER: [
        "trên 0.5 bàn", "dưới 1.5 bàn", "trên 3 bàn", "dưới 2 bàn",
        "tổng bàn trên 2.5", "vượt mốc 2.5", "khả năng dưới 2.5",
        "over or under", "chance of under 2.5",
        "probability of over 2.5 goals", "goals over under line",
        "trên 2.5 bàn", "dưới 2.5 bàn", "trên 1.5 bàn", "dưới 3.5 bàn",
        "trên 2.5 có ăn không", "khả năng trên 2.5 bàn",
        "tài xỉu", "tài 2.5", "xỉu 2.5", "kèo tài xỉu bao nhiêu",
        "hơn 3 bàn không", "ít hơn 2 bàn",
        "trên 3.5 bàn bao nhiêu phần trăm", "vượt 2.5 bàn không",
        "over 2.5", "under 2.5", "over 1.5 goals",
        "probability of over 3.5", "over under",
    ],
    BTTS: [
        "cả hai đội có bàn không", "hai đội đều ghi không",
        "một đội trắng lưới không", "both teams score probability",
        "btts yes or no", "will both sides find the net",
        "hai đội cùng ghi bàn", "cả hai đội ghi bàn",
        "hai bên đều ghi bàn không", "cả hai cùng nổ súng",
        "có đội nào không ghi được bàn không",
        "khả năng hai đội cùng ghi bàn",
        "both teams to score", "btts", "will both teams score",
    ],
    HANDICAP: [
        "thắng đậm", "thắng cách biệt", "thắng mấy trái",
        "cách biệt bao nhiêu bàn", "chấp bao nhiêu trái",
        "đội nhà chấp mấy", "có thắng cách biệt 2 bàn không",
        "thắng trên 1 bàn không", "cover the spread", "win by two goals",
        "margin of victory", "goal difference prediction", "handicap line",
        "chấp mấy trái", "chấp 1 trái", "chấp nửa trái",
        "chấp 1.5 có qua không", "đội nhà chấp 1 được không",
        "kèo chấp bao nhiêu", "chấp -1.5",
        "thắng cách biệt 2 bàn không", "thắng đậm không",
        "handicap", "spread", "can they cover 1.5",
        "win by 2 goals", "asian handicap",
    ],
    TEAM_GOALS: [
        "đội nhà ghi bao nhiêu", "đội khách ghi bao nhiêu",
        "đội nhà có nổ súng không", "riêng đội khách ghi mấy quả",
        "đội nhà ghi trên 1.5 bàn không", "goals scored by the home side",
        "will the home team find the net", "away team goals",
        "how many will they score",
        "đội nhà ghi mấy bàn", "đội khách ghi mấy bàn",
        "đội nhà có ghi bàn không", "đội khách ghi được không",
        "đội nhà ghi từ 2 bàn không", "đội khách có nổ súng không",
        "riêng đội nhà ghi bao nhiêu",
        "how many goals for the home team", "will the away team score",
        "home team goals",
    ],
    CLEAN_SHEET: [
        "đội nào không thủng lưới",
        "có giữ được mành lưới trinh nguyên không", "trắng lưới",
        "đội khách có giữ sạch lưới không", "keep a clean sheet",
        "will they concede", "shut out",
        "giữ sạch lưới", "không thủng lưới",
        "đội nhà có giữ sạch lưới không", "đội khách thủng lưới không",
        "có đội nào không thủng lưới", "trận này có 0 bàn bên nào không",
        "clean sheet", "will they keep a clean sheet",
    ],
    CORNERS: [
        "số quả phạt góc", "phạt góc bao nhiêu trái", "trên 10 phạt góc",
        "dưới 9.5 góc", "góc nhiều không", "corner count", "total corners",
        "corners over under",
        "phạt góc", "mấy quả phạt góc", "bao nhiêu phạt góc",
        "trên 9.5 phạt góc", "số phạt góc trận này",
        "trận này nhiều góc không", "kèo phạt góc",
        "corners", "how many corners", "over 9.5 corners",
    ],
    CARDS: [
        "thẻ đỏ có không", "mấy thẻ đỏ", "số thẻ phạt", "tổng số thẻ",
        "trận này nhiều thẻ phạt không", "trọng tài rút nhiều thẻ không",
        "yellow card", "red card", "how many cards", "total cards",
        "bookings",
        "thẻ vàng", "mấy thẻ", "thẻ phạt", "bao nhiêu thẻ vàng",
        "có nhiều thẻ không", "thẻ đỏ", "trên 3.5 thẻ",
        "trận này căng thẳng nhiều thẻ không", "kèo thẻ",
        "cards", "how many yellow cards", "over 3.5 cards",
    ],
    HALVES: [
        "hiệp một nhiều bàn hay hiệp hai", "phần lớn bàn thắng ở hiệp nào",
        "hiệp 2 có bàn không", "bàn thắng hiệp một chiếm bao nhiêu",
        "goals by half", "more goals in the second half", "half time goals",
        "hiệp nào nhiều bàn hơn", "hiệp 1 hay hiệp 2",
        "bàn thắng rơi vào hiệp mấy", "hiệp 1 có bàn không",
        "hiệp 2 nhiều bàn không", "bàn thắng theo hiệp",
        "which half has more goals", "first half goals",
        "second half goals",
    ],
    FORM: [
        "phong độ đội khách", "đội nhà thắng mấy trận gần đây",
        "chuỗi trận gần nhất", "đang thắng hay thua", "đá tốt không",
        "form gần đây ra sao", "phong độ hai đội", "recent results",
        "winning streak", "how is their form", "last matches",
        "phong độ", "phong độ gần đây", "phong độ đội nhà",
        "đội khách đang đá thế nào", "10 trận gần nhất",
        "thắng mấy trận gần đây", "đang có phong độ tốt không",
        "đội nhà đá ra sao", "gần đây thế nào",
        "recent form", "last 10 matches", "how are they playing",
        "current form",
    ],
    H2H: [
        "lịch sử hai đội", "những lần gặp trước", "thành tích gặp nhau",
        "hai đội đối đầu ra sao", "gặp nhau mấy lần rồi",
        "kết quả các lần gặp", "previous meetings",
        "past matches between them", "head 2 head record",
        "meetings history",
        "đối đầu", "lịch sử đối đầu", "hai đội gặp nhau thế nào",
        "lần gặp gần nhất", "đã gặp nhau bao nhiêu lần",
        "chạm trán", "thành tích đối đầu",
        "head to head", "previous meetings", "last time they met",
    ],
    STANDINGS: [
        "thứ hạng", "vị trí hiện tại", "đang đứng hạng mấy",
        "trên bảng xếp hạng thế nào", "cách nhau mấy bậc", "table position",
        "rank in the league", "current position", "points in the table",
        "xếp hạng", "bảng xếp hạng", "đứng thứ mấy",
        "vị trí trên bảng xếp hạng", "hạng mấy", "được bao nhiêu điểm",
        "standings", "league position", "what place are they in",
        "how many points",
    ],
    KICKOFF: [
        "địa điểm thi đấu", "sân đấu ở đâu", "lịch thi đấu",
        "thi đấu lúc nào", "giờ thi đấu", "ngày giờ trận đấu", "venue",
        "kick off time", "match date", "where is it played",
        "mấy giờ đá", "khi nào đá", "trận đấu lúc nào",
        "giờ bóng lăn", "đá ngày nào", "đá ở đâu", "sân nào",
        "sân vận động nào", "trận này đá lúc mấy giờ",
        "what time is kickoff", "when does it start", "which stadium",
        "where is the match",
    ],
    INJURIES: [
        "án phạt", "vắng ai", "đội hình ra sao", "có ai nghỉ không",
        "danh sách chấn thương", "ai bị treo giò", "team news",
        "squad news", "who is out", "injury list", "suspended players",
        "line up",
        "chấn thương", "ai chấn thương", "cầu thủ nào chấn thương",
        "đội hình dự kiến", "ai vắng mặt", "cầu thủ nào không đá",
        "treo giò", "đội hình ra sân", "ai đá chính",
        "injuries", "who is injured", "predicted lineup",
        "suspensions", "starting eleven",
    ],
    OTHER: [
        "world cup", "quả bóng vàng", "cầu thủ hay nhất", "tải app",
        "download app", "tin tức chuyển nhượng", "chuyển nhượng",
        "ai sẽ về đội nào", "bạn có người yêu chưa", "đố vui",
        "mấy giờ rồi bạn", "giá bitcoin", "thời tiết hà nội",
        "dịch câu này", "sửa giúp tôi", "how do i download this",
        "transfer news", "tell me something", "sing a song",
        "what time is it now",
        "xin chào", "chào bạn", "hello", "hi", "alo",
        "bạn là ai", "bạn tên gì", "bot ơi", "giúp tôi với",
        "hôm nay trời đẹp quá", "trời mưa không", "thời tiết thế nào",
        "giá vàng hôm nay", "tỷ giá đô la", "mấy giờ rồi",
        "messi hay ronaldo giỏi hơn", "cầu thủ nào hay nhất thế giới",
        "đội nào vô địch world cup", "ai giành quả bóng vàng",
        "kể chuyện cười đi", "hát một bài", "bạn ăn cơm chưa",
        "mua vé xem trận này ở đâu", "xem trực tiếp kênh nào",
        "link xem trận này", "tải app ở đâu", "app này của ai",
        "nên đặt cược bao nhiêu tiền", "cho tôi xin số đẹp",
        "đánh con gì hôm nay", "số lô đề hôm nay",
        "tôi muốn nạp tiền", "làm sao để kiếm tiền",
        "bóng rổ", "tennis", "đua xe", "cờ vua",
        "cảm ơn bạn", "ok", "tốt", "được rồi", "ừ", "haha",
        "what is your name", "who are you", "tell me a joke",
        "what is the weather", "how are you", "thanks",
        "where can i watch this match", "how much should i stake",
        "who is the best player ever",
    ],
    MODEL_INFO: [
        "có đáng tin không", "cách tính thế nào", "mô hình gì",
        "dự đoán dựa trên gì", "nguồn dữ liệu ở đâu", "số liệu từ đâu ra",
        "mô hình học thế nào", "tỉ lệ đúng bao nhiêu",
        "how is this calculated", "what data do you use", "model accuracy",
        "is this reliable", "how do you predict",
        "mô hình tính kiểu gì", "dựa vào đâu mà dự đoán",
        "có chính xác không", "độ chính xác bao nhiêu",
        "số liệu lấy từ đâu", "tin được không",
        "học từ bao nhiêu trận", "cách tính thế nào",
        "ai dự đoán cái này", "có dùng ai không",
        "how does the model work", "how accurate is it",
        "where does the data come from", "is this reliable",
    ],
}

ALL_INTENTS = tuple(SEEDS.keys())
