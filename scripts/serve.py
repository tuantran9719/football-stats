"""
Máy chủ cho bản build web, kiêm luôn việc chuyển tiếp API.

Hai việc nó làm khác python -m http.server:

  1. KHÔNG cho trình duyệt cache index.html. Tệp JS có mã băm trong tên
     nên cache thoải mái, riêng index.html phải luôn tải lại — nếu không,
     build xong mở trang vẫn ra bản cũ vì index.html trong cache trỏ tới
     tệp JS cũ. Đã gặp đúng lỗi này khi kiểm thử.

  2. Chuyển tiếp mọi đường dẫn /api/* sang backend ở cổng 4000.

Việc thứ hai mới là quan trọng. Trước đây web và backend là hai địa chỉ
khác nhau, nên chia sẻ ra ngoài phải dựng HAI đường hầm và phải nhúng
sẵn địa chỉ backend vào bundle lúc build. Hệ quả: đường hầm đổi URL là
phải build lại toàn bộ, và chỉ cần quên cờ --clear một lần là bundle giữ
địa chỉ cũ — đúng cái lỗi từng làm link gửi bạn bè bị hỏng.

Gộp về cùng một gốc thì chỉ cần một đường hầm, và bundle không còn chứa
địa chỉ nào cả: nó gọi /api trên chính trang đang mở, ở đâu cũng đúng —
localhost, IP trong mạng LAN, hay một tên miền công khai.
"""
import sys
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

BACKEND = "http://127.0.0.1:4000"
# Trang soi kèo phải chờ tải phong độ hai đội, đo được tới 6 giây khi
# cache nguội; để dư ra cho chắc.
TIMEOUT = 90


class Handler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy()
            return
        super().do_GET()

    def do_HEAD(self):
        if self.path.startswith("/api/"):
            self._proxy(body=False)
            return
        super().do_HEAD()

    def do_POST(self):
        # Hộp thư góp ý gửi bằng POST. Thiếu hàm này thì trình duyệt nhận
        # 501 và người dùng chỉ thấy "không gửi được" mà không rõ vì sao.
        if self.path.startswith("/api/"):
            self._proxy(method="POST")
            return
        self.send_error(405)

    def do_OPTIONS(self):
        # Preflight của CORS. Cùng gốc thì trình duyệt không hỏi, nhưng
        # trả lời sẵn để mở trang bằng địa chỉ khác vẫn chạy.
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, ngrok-skip-browser-warning")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _proxy(self, body: bool = True, method: str = "GET") -> None:
        url = BACKEND + self.path

        payload = None
        if method == "POST":
            length = int(self.headers.get("Content-Length") or 0)
            payload = self.rfile.read(length) if length else b""

        req = urllib.request.Request(url, data=payload, method=method)
        if method == "POST":
            req.add_header(
                "Content-Type", self.headers.get("Content-Type", "application/json"),
            )
        # Chuyển tiếp Accept-Language để backend chọn đúng ngôn ngữ nếu
        # sau này cần; các header khác (Host, cookie) cố tình bỏ đi.
        lang = self.headers.get("Accept-Language")
        if lang:
            req.add_header("Accept-Language", lang)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
                payload = res.read()
                self.send_response(res.status)
                self.send_header("Content-Type", res.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                if body:
                    self.wfile.write(payload)
        except urllib.error.HTTPError as e:
            # Giữ nguyên mã lỗi và phần thân của backend: frontend đọc
            # trường detail trong đó để hiện thông báo cho đúng.
            payload = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if body:
                self.wfile.write(payload)
        except Exception as exc:
            payload = f'{{"detail":"backend không phản hồi: {exc}"}}'.encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if body:
                self.wfile.write(payload)

    def end_headers(self):
        path = self.path.split("?")[0]
        if path.endswith("/") or path.endswith(".html") or path == "":
            self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    directory = sys.argv[1]
    port = int(sys.argv[2])
    ThreadingHTTPServer(
        ("0.0.0.0", port), partial(Handler, directory=directory),
    ).serve_forever()
