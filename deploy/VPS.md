# Dựng Football Stats trên VPS

Máy chủ chỉ chạy **hai container**: Python (API) và Caddy (web tĩnh +
HTTPS). Không có Node trên máy chủ — bản web build ở máy bạn rồi đẩy
lên, vì Metro cần 1–1,5 GB RAM lúc đóng gói.

## Cấu hình máy nên mua

| | |
|---|---|
| CPU | **1 nhân là đủ** — đo được: học lại mô hình tốn ~2 phút CPU mỗi 6 tiếng, còn lại gần như chỉ nằm chờ mạng |
| RAM | **2 GB** — app chỉ dùng 40 MB, phần còn lại để Docker và bộ đệm đĩa thở |
| Đĩa | 20 GB trở lên (thực dùng dưới 1 GB) |
| Hệ điều hành | Ubuntu 24.04 LTS |

**Cần một tên miền.** Android chặn kết nối không mã hoá, nên app trên CH
Play bắt buộc gọi qua HTTPS, mà HTTPS thì phải có tên miền. Tên miền
`.com` khoảng 10 đô/năm; muốn rẻ hơn thì `.xyz` hay `.id.vn` đều dùng
được. Trỏ bản ghi A của tên miền về địa chỉ IP của VPS trước khi làm
bước 4, vì Caddy cần nó để xin chứng chỉ.

## 1. Khoá máy lại trước đã

Đăng nhập lần đầu bằng root rồi làm ngay, đừng để sau:

```bash
adduser deploy
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy

# Tắt đăng nhập bằng mật khẩu — máy chủ mở ra internet sẽ bị dò mật khẩu
# liên tục trong vòng vài phút sau khi bật.
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart ssh

ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
```

Mở một cửa sổ terminal MỚI và thử `ssh deploy@<ip>` trước khi đóng cửa
sổ root đang mở. Sai cấu hình SSH mà đã đóng hết phiên là mất máy.

## 2. Cài Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy
```

Đăng xuất rồi vào lại để quyền có hiệu lực.

## 3. Thêm swap

Máy 2 GB không có swap sẽ bị nhân hệ điều hành giết tiến trình khi có
đỉnh bộ nhớ bất ngờ. 2 GB swap là bảo hiểm rẻ.

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 4. Khai cấu hình

```bash
sudo mkdir -p /opt/football-stats && sudo chown deploy:deploy /opt/football-stats
cd /opt/football-stats
mkdir -p data logs
```

Tạo `/opt/football-stats/.env` cho Docker Compose:

```
DOMAIN=stats.tenmiencuaban.com
```

Và `/opt/football-stats/backend/.env` cho app:

```
FEEDBACK_SMTP_HOST=smtp.gmail.com
FEEDBACK_SMTP_PORT=587
FEEDBACK_SMTP_USER=...
FEEDBACK_SMTP_PASS=...
FEEDBACK_TO=...
```

File `backend/.env` **không nằm trong git** và script đẩy cũng cố tình bỏ
qua nó, nên bạn phải tạo tay trên máy chủ đúng một lần.

## 5. Đẩy lên

Từ máy bạn:

```bash
./deploy/deploy.sh deploy@<ip-cua-vps>
```

Script sẽ: build bản web ở máy → đồng bộ mã nguồn và bản web lên →
`docker compose up -d --build` → chờ tới khi `/api/health` trả lời.

Lần đầu Caddy xin chứng chỉ mất khoảng 30 giây. Sau đó mở
`https://stats.tenmiencuaban.com` là thấy app.

## 6. Sao lưu tự động

```bash
sudo cp /opt/football-stats/deploy/backup.sh /usr/local/bin/fb-backup
sudo chmod +x /usr/local/bin/fb-backup
( crontab -l 2>/dev/null; echo "0 3 * * * /usr/local/bin/fb-backup" ) | crontab -
```

Mỗi 3 giờ sáng gói `data/` lại, giữ 14 bản gần nhất.

## Việc thường ngày

```bash
# Đẩy phiên bản mới (từ máy bạn)
./deploy/deploy.sh deploy@<ip>

# Xem log (trên máy chủ)
cd /opt/football-stats && docker compose logs -f api

# Khởi động lại
docker compose restart api

# Tình trạng
curl https://stats.tenmiencuaban.com/api/health
```

## Việc phải tự nhớ, vì không ai nhắc

VPS đổi lấy giá rẻ và IP riêng bằng chính những việc này:

- **Cập nhật bảo mật**: `sudo apt update && sudo apt upgrade` mỗi tháng.
  Hoặc bật `unattended-upgrades` để máy tự làm.
- **Theo dõi**: không có ai báo khi máy chủ chết. Dựng một phép kiểm tra
  bên ngoài (UptimeRobot miễn phí) gọi `/api/health` mỗi 5 phút.
- **Kiểm tra bản sao lưu**: bản sao lưu chưa từng thử phục hồi thì coi
  như chưa có. Mỗi vài tháng giải nén thử một bản.
