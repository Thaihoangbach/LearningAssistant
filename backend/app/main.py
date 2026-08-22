"""Entrypoint FastAPI — walking skeleton F1 + F2.

Chạy: uvicorn app.main:app --reload
"""

import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import init_db
from app.routers import (
    chat,
    documents,
    flashcard,
    mastery,
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

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173",
)

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    FRONTEND_URL,
]

ALLOWED_ORIGINS = list(
    dict.fromkeys(
        origin
        for origin in ALLOWED_ORIGINS
        if origin
    )
)

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
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )

# ============================================================
# Startup
# ============================================================

@app.on_event("startup")
def on_startup():
    init_db()

# ============================================================
# Health
# ============================================================

@app.get("/health")
def health():
    return {"status": "ok"}