"""Kết nối PostgreSQL (+ pgvector) qua SQLAlchemy.

Trước đây dùng SQLite local — đơn giản để chạy máy cá nhân nhưng không có
kiểu vector (buộc embedding phải sống trong file FAISS riêng, xem lịch sử
app/vectorstore/faiss_store.py đã gỡ bỏ) và không deploy được lên host chỉ
có đĩa tạm (Render free tier...). Postgres + pgvector gộp cả hai lại một
chỗ: dữ liệu quan hệ VÀ vector embedding trong CÙNG một transaction.

Migration schema giờ qua Alembic (`alembic/`) — không còn `create_all()` +
danh sách CREATE INDEX thủ công. Chạy `alembic upgrade head` trước khi khởi
động app (xem README, mục Deploy).
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "Thiếu DATABASE_URL. Cần một Postgres có sẵn extension pgvector, dạng "
        "postgresql+psycopg://user:password@host:port/dbname — chạy cục bộ "
        "bằng `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres "
        "pgvector/pgvector:pg16` rồi đặt DATABASE_URL vào .env."
    )

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
