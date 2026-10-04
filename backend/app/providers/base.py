"""
Hợp đồng mà mọi nguồn dữ liệu phải đáp ứng.

Đây là RANH GIỚI của hệ thống. Mọi thứ bên trên nó — tính toán thống kê,
mô hình dự đoán, bộ hỏi đáp, cache, API, giao diện — không được biết dữ
liệu đến từ đâu. Đổi nhà cung cấp phải là việc viết thêm MỘT file trong
thư mục này rồi đổi một biến môi trường, không phải đi sửa khắp nơi.

Vì sao điều này quan trọng với chính dự án này: nguồn đang dùng (ESPN)
là endpoint nội bộ của họ, không có tài liệu, không có cam kết. Họ đã
đổi tên trường một lần và trả về hai hình dạng dữ liệu khác nhau cho
giải quốc nội với giải cúp — cả hai lần đều làm hỏng app. Giả định đúng
đắn là ngày nào đó nguồn này sẽ hỏng hẳn hoặc bị chặn, nên đường thoát
phải được dựng sẵn và phải được KIỂM CHỨNG, chứ không phải một lời hứa
trong tài liệu.

Mã đội và mã trận do mỗi nguồn tự đặt, không trùng nhau giữa các nguồn.
Vì vậy mỗi nguồn khai một `prefix` riêng và mọi mã đi ra ngoài đều mang
tiền tố đó ("espn:359"). Tiền tố cho biết mã này của ai, và quan trọng
hơn: đổi nguồn thì mã cũ lưu trên máy người dùng (đội yêu thích) tự động
không khớp nữa thay vì khớp nhầm sang một đội hoàn toàn khác.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from ..models import (
    Match, MatchDetail, NewsItem, StandingGroup, Team,
)


class ProviderBusy(Exception):
    """
    Nguồn đang từ chối phục vụ (429, quá tải, đang nghỉ hồi).

    Khác hẳn lỗi lập trình: không có gì hỏng, chỉ là phải chờ. Tầng API
    biến nó thành HTTP 503 kèm câu giải thích, thay vì 500 trống khiến
    app hiện "Unexpected token I, Internal S... is not valid JSON".
    """


@dataclass(frozen=True)
class LeagueCatalogue:
    """
    Những giải mà một nguồn phục vụ được.

    Gói chung thành một giá trị thay vì bốn hàm rời, để hợp đồng không
    phình ra: nguồn mới chỉ phải trả về một thứ này.

    `cups` tách khỏi `leagues` vì giải đấu loại trực tiếp không có bảng
    xếp hạng; chúng chỉ dùng khi dò hai đội từng gặp nhau ở giải nào.
    """
    leagues: dict[str, str] = field(default_factory=dict)
    cups: dict[str, str] = field(default_factory=dict)
    logos: dict[str, str] = field(default_factory=dict)

    def display_name(self, code: str) -> str:
        return self.leagues.get(code) or self.cups.get(code) or code

    def logo_url(self, code: str) -> Optional[str]:
        return self.logos.get(code)

    def knows(self, code: str) -> bool:
        return code in self.leagues or code in self.cups


@runtime_checkable
class FootballProvider(Protocol):
    """
    Tám hàm. Thêm hàm thứ chín nghĩa là mọi nguồn khác đều phải viết
    thêm — hãy cân nhắc trước khi mở rộng.
    """

    name: str
    """Tiền tố gắn vào mọi mã do nguồn này sinh ra, ví dụ "espn"."""
    prefix: str

    def catalogue(self) -> LeagueCatalogue:
        """Các giải nguồn này phục vụ. Danh mục KHÔNG còn nằm cứng ở tầng
        trên: nguồn khác phủ giải khác là chuyện bình thường."""
        ...

    async def list_matches(self, league: str, date: Optional[str] = None) -> list[Match]: ...

    async def list_upcoming_matches(self, league: str, limit: int = 12) -> list[Match]: ...

    async def list_calendar(self, league: str) -> list[str]:
        """Các ngày có trận, dạng YYYYMMDD theo giờ UTC. Rỗng cũng hợp lệ."""
        ...

    async def list_teams(self, league: str) -> list[Team]: ...

    async def list_team_matches(
        self, league: str, team_external_id: str, seasons: list[str],
    ) -> list[Match]: ...

    async def list_standings(
        self, league: str,
    ) -> tuple[Optional[str], list[StandingGroup]]: ...

    async def list_news(self, league: str, limit: int = 20) -> list[NewsItem]: ...

    async def get_match_detail(self, league: str, external_id: str) -> MatchDetail: ...

    def health(self) -> dict:
        """Tình trạng nguồn, hiện ở /api/health. Hình dạng tuỳ nguồn."""
        ...

    async def aclose(self) -> None: ...
