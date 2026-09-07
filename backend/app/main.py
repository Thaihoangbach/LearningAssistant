"""Entrypoint FastAPI — walking skeleton F1 + F2.

Chạy: uvicorn app.main:app --reload
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger("edututor")

from app.routers import (
    chat,
    documents,
    flashcard,
    mastery,
    memory,
    profile,
    quiz,
    study_plan,
)

app = FastAPI(
    title="EduTutor API",
    version="0.1.0",
)

# ============================================================
# CORS
# ============================================================

_DEV_ORIGIN = "http://localhost:5173"


def compute_allowed_origins(frontend_url: str | None) -> list[str]:
    """`frontend_url` không có giá trị mặc định — cần phân biệt "chưa cấu
    hình gì" (dev cục bộ, chỉ cần localhost) với "đã cấu hình một domain
    production" (Vercel...). Bản trước LUÔN thêm localhost:5173 vào
    allow_origins bất kể FRONTEND_URL là gì, cùng với allow_credentials=True
    — nghĩa là một request có nguồn gốc localhost:5173 trên MÁY CỦA NGƯỜI
    DÙNG vẫn được backend production tin tưởng kèm cookie/credential, dù
    chẳng ai triển khai frontend thật ở địa chỉ đó. Giờ chỉ thêm localhost
    khi KHÔNG có domain production nào được khai báo."""
    origins = [frontend_url] if frontend_url else [_DEV_ORIGIN]
    return list(dict.fromkeys(o for o in origins if o))


# `FRONTEND_URL` không có giá trị mặc định ở đây (khác bản trước) — xem
# docstring compute_allowed_origins().
FRONTEND_URL = os.getenv("FRONTEND_URL")
ALLOWED_ORIGINS = compute_allowed_origins(FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Routers
# ============================================================

app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(quiz.router)
app.include_router(mastery.router)
app.include_router(flashcard.router)
app.include_router(memory.router)
app.include_router(study_plan.router)
app.include_router(profile.router)

# ============================================================
# Exception handler
# ============================================================

@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
):
    # str(exc) trước đây được trả THẲNG cho client — lỗi DB (connection string,
    # tên cột), lỗi thư viện bên thứ ba (stack trace nội bộ, đường dẫn trên máy
    # chủ)... đều lộ ra ngoài trên MỌI exception không bắt được. Ghi log đầy đủ
    # ở server, chỉ trả một thông báo chung cho client — client vẫn cần biết
    # request đã lỗi, không cần biết lỗi gì.
    logger.exception("Lỗi không xử lý được tại %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Đã xảy ra lỗi hệ thống. Vui lòng thử lại sau."},
    )

# ============================================================
# Health
#
# Schema không còn tự tạo lúc app khởi động (bản trước gọi init_db() ở đây,
# Base.metadata.create_all() trên SQLite). Postgres + Alembic cần chạy
# `alembic upgrade head` như một BƯỚC DEPLOY riêng, TRƯỚC khi tiến trình
# uvicorn khởi động (xem docker-entrypoint.sh) — không phải việc app tự làm
# mỗi lần một worker process khởi động, để nhiều worker/lần restart không
# tranh nhau chạy migration cùng lúc.
# ============================================================

@app.get("/health")
def health():
    return {"status": "ok"}