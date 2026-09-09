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
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

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


def ensure_user(db: Session, user_id: str) -> None:
    """Tạo hàng `users` cho `user_id` nếu chưa có — KHÔNG tự commit, chỉ flush,
    để lời gọi này nằm CHUNG transaction với write theo sau (vd tạo Document,
    Conversation) thay vì phải commit riêng.

    Cần thiết vì MỌI bảng khác đều có FK bắt buộc trỏ về `users.id` (xem
    app/models.py), nhưng chưa có màn hình đăng ký thật (F5) — frontend luôn
    gửi lên đúng một `user_id` cố định (`demo-user`, xem frontend/src/api.js)
    mà không có bước nào tạo trước hàng `users` tương ứng. Trên một DB mới
    migrate xong, hàng đó chưa tồn tại, nên INSERT đầu tiên tham chiếu tới nó
    (Document, Conversation, LearningProfile...) sẽ luôn thất bại với
    ForeignKeyViolation — đã tái hiện được lỗi này khi test trực tiếp backend
    đã deploy. Import `User` ở đây (không phải đầu file) để tránh vòng lặp
    import với models.py, vốn không cần biết gì về database.py."""
    from app.models import User

    stmt = (
        insert(User)
        .values(id=user_id, email=f"{user_id}@local.invalid", display_name=user_id)
        .on_conflict_do_nothing(index_elements=["id"])
    )
    db.execute(stmt)
    db.flush()
