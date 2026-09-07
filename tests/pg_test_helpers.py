"""Fixture dùng chung cho mọi test cần Postgres THẬT (pgvector, full-text
search) — không mock được vì cả hai đều là hành vi CỦA POSTGRES, không phải
logic thuần của app.

Cần một Postgres có extension pgvector đang chạy, trỏ qua TEST_DATABASE_URL
(mặc định khớp `docker run` trong README, mục Deploy/Phát triển cục bộ).
Test dùng chung 1 database, mỗi test class tự `drop_all`+`create_all` trong
setUp để đảm bảo bảng sạch — chấp nhận được vì unittest chạy các test TUẦN
TỰ trong cùng tiến trình (trừ các test TỰ Ý dựng nhiều thread để kiểm tra
concurrency, các test đó tự chịu trách nhiệm cô lập dữ liệu bằng khoá chính
ngẫu nhiên thay vì bảng riêng)."""
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5433/edututor_test"
)


def fresh_test_session_factory():
    """Tạo lại TOÀN BỘ schema từ đầu (drop rồi create theo models.py hiện
    tại) và trả về (engine, sessionmaker) — dùng khi test cần bảng ĐÚNG
    THEO CODE hiện tại, không qua Alembic (nhanh hơn, và test không nên phụ
    thuộc thứ tự migration đã áp dụng)."""
    from app.models import Base

    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_document_chunks_text_fts ON document_chunks "
                "USING gin (to_tsvector('simple', text))"
            )
        )
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)
