"""API routes cho F1 — quản lý tài liệu học tập cá nhân.

CHƯA CHẠY ĐƯỢC TRONG SANDBOX NÀY: cần `pip install fastapi python-multipart`.
"""

import glob
import os
import shutil
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.ingestion.pipeline import process_document
from app.models import Document
from app.vectorstore.faiss_store import UserVectorStore

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = "./data/uploads"
MAX_FILE_MB = 30
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def _run_processing_job(document_id: str, file_path: str, document_name: str, user_id: str, db: Session):
    doc = db.query(Document).filter(Document.id == document_id).first()
    try:
        num_chunks = process_document(
            file_path=file_path,
            document_id=document_id,
            document_name=document_name,
            user_id=user_id,
        )
        doc.status = "sẵn sàng"
        db.commit()
    except Exception as e:  # noqa: BLE001 - phải bắt mọi lỗi để cập nhật status, đúng AC F1
        doc.status = "lỗi"
        doc.error_reason = str(e)
        db.commit()


@router.post("")
async def upload_document(
    file: UploadFile,
    user_id: str,
    course_name: str | None = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Định dạng {ext} không được hỗ trợ. Chỉ chấp nhận PDF/DOCX.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    document_id = str(uuid.uuid4())
    saved_path = os.path.join(UPLOAD_DIR, f"{document_id}{ext}")

    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    size_mb = os.path.getsize(saved_path) / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        os.remove(saved_path)
        raise HTTPException(400, f"File vượt quá {MAX_FILE_MB}MB.")

    doc = Document(
        id=document_id,
        user_id=user_id,
        file_name=file.filename,
        course_name=course_name,
        status="đang xử lý",
    )
    db.add(doc)
    db.commit()

    background_tasks.add_task(
        _run_processing_job, document_id, saved_path, file.filename, user_id, db
    )

    return {"document_id": document_id, "status": "đang xử lý"}


@router.get("")
def list_documents(user_id: str, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.user_id == user_id).all()
    return [
        {
            "id": d.id,
            "file_name": d.file_name,
            "course_name": d.course_name,
            "status": d.status,
            "error_reason": d.error_reason,
            "uploaded_at": d.uploaded_at.isoformat(),
        }
        for d in docs
    ]


@router.delete("/{document_id}")
def delete_document(document_id: str, user_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    if not doc:
        raise HTTPException(404, "Không tìm thấy tài liệu.")

    UserVectorStore(user_id=user_id).remove_document(document_id)

    for path in glob.glob(os.path.join(UPLOAD_DIR, f"{document_id}.*")):
        os.remove(path)

    db.delete(doc)
    db.commit()

    return {"status": "deleted", "document_id": document_id}
