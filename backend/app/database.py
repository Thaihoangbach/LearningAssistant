"""Khởi tạo SQLite database qua SQLAlchemy — miễn phí, không cần server.

CHƯA CHẠY ĐƯỢC TRONG SANDBOX NÀY: cần `pip install sqlalchemy`.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base

DB_PATH = os.environ.get("DB_PATH", "./data/edututor.db")
os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
