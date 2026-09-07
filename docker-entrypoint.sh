#!/bin/sh
# Chạy migration TRƯỚC khi tiến trình uvicorn nhận request nào — một bước
# DEPLOY riêng, không phải việc app tự làm mỗi lần khởi động (xem
# backend/app/main.py, mục Health). `set -e` dừng ngay và KHÔNG khởi động
# server nếu migration thất bại, thay vì chạy một server trỏ vào schema cũ.
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
