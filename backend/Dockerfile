# Backend Football Stats.
#
# Ảnh "slim" chứ không phải "alpine": alpine dùng musl libc, các gói
# Python có phần biên dịch sẵn phải build lại từ mã nguồn, chậm hơn
# nhiều mà chẳng tiết kiệm được bao nhiêu.
FROM python:3.13-slim

# Không ghi file .pyc, và không đệm đầu ra để log hiện ngay trong
# `docker compose logs` thay vì kẹt trong bộ đệm.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

WORKDIR /app

# Cài phụ thuộc trước, chép mã sau: sửa mã mà không đổi requirements
# thì Docker dùng lại lớp đã cài, build lại chỉ mất vài giây.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# Chạy bằng người dùng thường, không phải root. Container bị chiếm thì
# kẻ tấn công cũng không có quyền root bên trong.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data && chown -R appuser:appuser /data /app
USER appuser

EXPOSE 4000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:4000/api/health',timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4000"]
