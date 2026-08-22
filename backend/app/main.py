"""Entrypoint FastAPI — walking skeleton F1 + F2.

Chạy: uvicorn app.main:app --reload
CHƯA CHẠY ĐƯỢC TRONG SANDBOX NÀY: cần `pip install -r requirements.txt`.
"""

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import init_db
from app.routers import chat, documents, flashcard, mastery, profile, quiz, study_plan

app = FastAPI(title="EduTutor API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(quiz.router)
app.include_router(mastery.router)
app.include_router(flashcard.router)
app.include_router(study_plan.router)
app.include_router(profile.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Starlette's CORSMiddleware chỉ gắn header CORS vào response bình thường,
    # KHÔNG gắn được vào response mà ServerErrorMiddleware tự tạo khi exception
    # thoát khỏi toàn bộ middleware stack. Không có handler này, mọi lỗi 500
    # (vd. thiếu GEMINI_API_KEY) sẽ bị trình duyệt chặn vì thiếu CORS header
    # và JS chỉ thấy "Failed to fetch" thay vì thông báo lỗi thật.
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
