"""Chay backend LOCAL cho muc dich chay Golden Set/eval — nap API key tu
.env goc (OPENAI/GEMINI/COHERE_API_KEY) nhung GHI DE DATABASE_URL/STORAGE_*
ve dung Docker local (edututor-pg cong 5432, edututor-minio cong 9010) thay
vi gia tri production trong .env (Neon/Backblaze) — dung nguyen tac da chot
trong session: khong bao gio de backend local tro vao service production
khi chay eval.

Dat EVAL_TRACE=1 de bat instrumentation debug trong app/llm/rag.py (ghi
draft_answer/raw_verdict/diem retrieval vao eval/trace.jsonl) phuc vu
attribution.

Chay: python eval/scripts/run_local_backend.py
"""
import os
import sys

from dotenv import load_dotenv

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..", "..")

load_dotenv(os.path.join(ROOT, ".env"))

# Ghi de ve local Docker — KHONG dung DATABASE_URL/STORAGE_* production tu .env.
os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
os.environ["STORAGE_ENDPOINT_URL"] = "http://localhost:9010"
os.environ["STORAGE_ACCESS_KEY_ID"] = "testkey"
os.environ["STORAGE_SECRET_ACCESS_KEY"] = "testsecret"
os.environ["STORAGE_BUCKET_NAME"] = "edututor-uploads"
os.environ["EVAL_TRACE"] = "1"

os.chdir(os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "backend"))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
