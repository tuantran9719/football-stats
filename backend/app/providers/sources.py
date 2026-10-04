"""
TOÀN BỘ CẤU HÌNH NGUỒN DỮ LIỆU NẰM Ở ĐÂY.

Muốn đổi URL, đổi nhà cung cấp, hay thêm giải đấu thì chỉ sửa file này.
Mọi mã ESPN dưới đây đã kiểm chứng thực tế, gọi thật và có dữ liệu trả về.
"""
from typing import Optional

# Tên ở đây là TÊN GỐC QUỐC TẾ, không dịch.
#
# App tự dịch những giải có tên tiếng Việt quen dùng ("Ngoại hạng Anh",
# "Hạng Nhất Anh") trong src/i18n; số còn lại là danh từ riêng, giữ
# nguyên ở mọi ngôn ngữ. Để tên tiếng Việt ở đây thì người dùng tiếng
# Anh sẽ thấy "VĐQG Argentina".
# Tên ở đây là TÊN GỐC QUỐC TẾ, không dịch.
#
# App tự dịch những giải có tên tiếng Việt quen dùng ("Ngoại hạng Anh",
# "Hạng Nhất Anh") trong src/i18n; số còn lại là danh từ riêng nên giữ
# nguyên ở mọi ngôn ngữ. Để tên tiếng Việt ở đây thì người dùng tiếng
# Anh sẽ thấy "VĐQG Argentina".
LEAGUES: dict[str, str] = {
    "EPL": "Premier League",
    "LALIGA": "La Liga",
    "SERIEA": "Serie A",
    "BUNDES": "Bundesliga",
    "LIGUE1": "Ligue 1",
    "UCL": "Champions League",
    "UEL": "Europa League",
    "UECL": "Conference League",
    "EFLCHAMP": "EFL Championship",
    "EREDIV": "Eredivisie",
    "PRIMEIRA": "Primeira Liga",
    "BRASILEIRAO": "Brasileirão",

    # --- Châu Á ------------------------------------------------------
    "JLEAGUE": "J1 League",
    "CSL": "Chinese Super League",
    "ALEAGUE": "A-League",

    # --- Châu Âu, giải vô địch -----------------------------------------
    "SUPERLIG": "Süper Lig",
    "BELPRO": "Belgian Pro League",
    "SCOPREM": "Scottish Premiership",
    "AUTBUND": "Austrian Bundesliga",
    "GREECE": "Super League Greece",
    "ALLSVENSK": "Allsvenskan",
    "ELITESERIEN": "Eliteserien",
    "SUPERLIGAEN": "Superliga Đan Mạch",
    "RUSPREM": "Russian Premier League",

    # --- Châu Âu, hạng nhì ---------------------------------------------
    "BUNDES2": "2. Bundesliga",
    "LIGUE2": "Ligue 2",
    "SERIEB": "Serie B",
    "LALIGA2": "LaLiga 2",
    "EERSTE": "Eerste Divisie",
    "EFL1": "EFL League One",
    "EFL2": "EFL League Two",

    # --- Châu Mỹ --------------------------------------------------------
    "MLS": "MLS",
    "ARGLIGA": "Liga Profesional Argentina",
    "COLPRIM": "Primera A Colombia",
    "CHIPRIM": "Primera División Chile",
    "URUPRIM": "Primera División Uruguay",
    "BRASILB": "Brasileirão Série B",
    "LIBERTADORES": "Copa Libertadores",
    "SUDAMERICANA": "Copa Sudamericana",

    # --- Toàn cầu --------------------------------------------------------
}

# Các giải cúp, CHỈ dùng cho phần đối đầu.
#
# Cố ý tách khỏi LEAGUES: cúp đấu loại trực tiếp không có bảng xếp hạng,
# lịch rải rác vài vòng mỗi mùa, đưa vào menu chính thì rỗng gần như
# quanh năm. Nhưng với đối đầu thì đây đúng là thứ còn thiếu — hai đội
# cùng thành phố gặp nhau ở cúp quốc gia hay giải bang nhiều hơn hẳn so
# với ở giải vô địch.
#
# Tên để nguyên gốc, không dịch: đều là danh từ riêng và người hâm mộ
# nhận ra ngay ở mọi ngôn ngữ.
CUP_LEAGUES: dict[str, str] = {
    "FACUP": "FA Cup",
    "EFLCUP": "EFL Cup",
    "COPADELREY": "Copa del Rey",
    "COPPAITALIA": "Coppa Italia",
    "DFBPOKAL": "DFB-Pokal",
    "COUPEFRANCE": "Coupe de France",
    "TACAPORTUGAL": "Taça de Portugal",
    "KNVBBEKER": "KNVB Beker",
    "COPADOBRASIL": "Copa do Brasil",
    "PAULISTA": "Campeonato Paulista",
    "USOPEN": "US Open Cup",
    "COPAARG": "Copa Argentina",
}

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# Bảng xếp hạng nằm ở một nhánh API khác (apis/v2 thay vì apis/site/v2).
# Đường dẫn apis/site/v2/.../standings có tồn tại nhưng trả về đối tượng
# rỗng, đã thử. Đừng gộp hai cái làm một.
ESPN_V2_BASE = "https://site.api.espn.com/apis/v2/sports/soccer"

# Mã giải nội bộ -> mã của ESPN
ESPN_LEAGUE_CODES: dict[str, str] = {
    "EPL": "eng.1",
    "LALIGA": "esp.1",
    "SERIEA": "ita.1",
    "BUNDES": "ger.1",
    "LIGUE1": "fra.1",
    "UCL": "uefa.champions",
    "UEL": "uefa.europa",
    "UECL": "uefa.europa.conf",
    "EFLCHAMP": "eng.2",
    "EREDIV": "ned.1",
    "PRIMEIRA": "por.1",
    "BRASILEIRAO": "bra.1",

    # Cúp — xem ghi chú ở CUP_LEAGUES. Mọi mã dưới đây đã gọi thử và có
    # dữ liệu trả về; vài biến thể tên khác trả 404 nên đừng đoán lại.
    "FACUP": "eng.fa",
    "EFLCUP": "eng.league_cup",
    "COPADELREY": "esp.copa_del_rey",
    "COPPAITALIA": "ita.coppa_italia",
    "DFBPOKAL": "ger.dfb_pokal",
    "COUPEFRANCE": "fra.coupe_de_france",
    "TACAPORTUGAL": "por.taca.portugal",
    "KNVBBEKER": "ned.cup",
    "COPADOBRASIL": "bra.copa_do_brazil",
    "PAULISTA": "bra.camp.paulista",
    "JLEAGUE": "jpn.1",
    "CSL": "chn.1",
    "ALEAGUE": "aus.1",
    "SUPERLIG": "tur.1",
    "BELPRO": "bel.1",
    "SCOPREM": "sco.1",
    "AUTBUND": "aut.1",
    "GREECE": "gre.1",
    "ALLSVENSK": "swe.1",
    "ELITESERIEN": "nor.1",
    "SUPERLIGAEN": "den.1",
    "RUSPREM": "rus.1",
    "BUNDES2": "ger.2",
    "LIGUE2": "fra.2",
    "SERIEB": "ita.2",
    "LALIGA2": "esp.2",
    "EERSTE": "ned.2",
    "EFL1": "eng.3",
    "EFL2": "eng.4",
    "MLS": "usa.1",
    "ARGLIGA": "arg.1",
    "COLPRIM": "col.1",
    "CHIPRIM": "chi.1",
    "URUPRIM": "uru.1",
    "BRASILB": "bra.2",
    "LIBERTADORES": "conmebol.libertadores",
    "SUDAMERICANA": "conmebol.sudamericana",

    # Cúp bổ sung, chỉ dùng cho phần đối đầu.
    "USOPEN": "usa.open",
    "COPAARG": "arg.copa",
}

# Logo giải, dùng cho biểu tượng nhỏ cạnh tên giải khắp app.
#
# Đường dẫn dựng sẵn thay vì gọi API: mã logo của ESPN cố định theo giải,
# và nhúng cứng ở đây thì không tốn lượt gọi nào chỉ để lấy một tấm ảnh.
# Mọi mã dưới đây lấy từ trường leagues[0].logos của scoreboard.
#
# Ưu tiên bản "500-dark" vì nền app tối; giải nào ESPN không có bản tối
# thì dùng bản thường. Taça de Portugal hiện không có logo nào — giao
# diện tự bỏ qua, không hiện ô trống.
_LOGO_IDS: dict[str, tuple[str, bool]] = {
    # mã giải: (mã logo ESPN, có bản nền tối không)
    "EPL": ("23", True),
    "LALIGA": ("15", True),
    "SERIEA": ("12", True),
    "BUNDES": ("10", True),
    "LIGUE1": ("9", True),
    "UCL": ("2", True),
    "UEL": ("2310", True),
    "UECL": ("20296", True),
    "EFLCHAMP": ("24", True),
    "EREDIV": ("11", True),
    "PRIMEIRA": ("14", True),
    "BRASILEIRAO": ("85", True),
    "FACUP": ("40", True),
    "EFLCUP": ("41", True),
    "COPADELREY": ("80", True),
    "COPPAITALIA": ("2192", False),
    "DFBPOKAL": ("2061", True),
    "COUPEFRANCE": ("182", True),
    "KNVBBEKER": ("2196", True),
    "COPADOBRASIL": ("528", True),
    "PAULISTA": ("2322", True),
    "JLEAGUE": ("2199", True),
    "CSL": ("2350", True),
    "ALEAGUE": ("1308", True),
    "SUPERLIG": ("18", True),
    "BELPRO": ("6", True),
    "SCOPREM": ("45", True),
    "AUTBUND": ("5", True),
    "GREECE": ("98", False),
    "ALLSVENSK": ("16", False),
    "RUSPREM": ("106", True),
    "BUNDES2": ("97", False),
    "LIGUE2": ("96", True),
    "SERIEB": ("99", False),
    "LALIGA2": ("107", True),
    "EERSTE": ("105", True),
    "EFL1": ("25", True),
    "EFL2": ("26", True),
    "MLS": ("19", True),
    "ARGLIGA": ("1", True),
    "COLPRIM": ("1543", True),
    "CHIPRIM": ("86", True),
    "URUPRIM": ("1592", True),
    "BRASILB": ("2299", True),
    "LIBERTADORES": ("58", True),
    "SUDAMERICANA": ("1208", True),
    "USOPEN": ("69", True),
    "COPAARG": ("2320", True),
    # ELITESERIEN và SUPERLIGAEN: ESPN không có logo giải, giao diện tự
    # bỏ qua chứ không vẽ ô trống.
}


def league_logo_url(code: str) -> Optional[str]:
    entry = _LOGO_IDS.get(code)
    if not entry:
        return None
    logo_id, has_dark = entry
    folder = "500-dark" if has_dark else "500"
    return f"https://a.espncdn.com/i/leaguelogos/soccer/{folder}/{logo_id}.png"


def league_display_name(code: str) -> str:
    """Tên hiển thị cho cả giải vô địch lẫn cúp."""
    return LEAGUES.get(code) or CUP_LEAGUES.get(code) or code
