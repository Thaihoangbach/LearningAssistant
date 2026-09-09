"""API routes cho F1 — quản lý tài liệu học tập cá nhân.

File gốc lưu trên Backblaze B2 (app/storage.py), KHÔNG còn trên đĩa local
(./data/uploads/ trước đây) — Render free tier không có đĩa bền vững, mỗi
lần container khởi động lại là mất sạch. Xử lý tài liệu (parse/chunk/embed)
vẫn cần một file THẬT trên đĩa cho pypdf/python-docx — `_run_processing_job`
tải file từ B2 về một file TẠM, xử lý xong thì xoá file tạm đó (không phải
bản lưu trữ lâu dài).
"""

import logging
import os
import tempfile
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import storage
from app.database import SessionLocal, ensure_user, get_db
from app.ingestion.outline import extract_outline
from app.ingestion.pipeline import process_document
from app.models import Document, DocumentTopic, Topic
from app.services.document_cleanup import cleanup_document_topics
from app.vectorstore.pgvector_store import PgVectorStore

logger = logging.getLogger("edututor")

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_MB = 30
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def _storage_key(document_id: str, ext: str) -> str:
    return f"{document_id}{ext}"


def _save_outline(db: Session, document_id: str, user_id: str, file_path: str, course_name: str | None):
    """Lưu dàn ý chủ đề và tạo sẵn Topic tương ứng.

    Tạo Topic ngay tại đây là có chủ đích: trước kia Topic chỉ ra đời khi người
    dùng tự gõ tên chủ đề lúc sinh quiz, nên kế hoạch ôn tập và mastery không
    có gì để bám vào cho tới lúc đó. Topic mới chưa có điểm nào, và
    app/services/study_planner.py coi chủ đề chưa có điểm là "chưa học" nên tự
    động xếp lên trước — đúng hành vi mong muốn.

    Không rút được dàn ý (tài liệu không có heading) thì bỏ qua, KHÔNG bịa ra
    chủ đề."""
    # Dọn dàn ý cũ của CHÍNH tài liệu này trước, để xử lý lại một tài liệu
    # không sinh ra dàn ý trùng lặp.
    cleanup_document_topics(db, document_id=document_id, user_id=user_id)

    entries = extract_outline(file_path)
    if not entries:
        return

    for entry in entries:
        db.add(
            DocumentTopic(
                document_id=document_id,
                user_id=user_id,
                title=entry.title,
                position_ref=entry.position_ref,
                order_index=entry.order,
            )
        )
        existing = (
            db.query(Topic).filter(Topic.user_id == user_id, Topic.name == entry.title).first()
        )
        if not existing:
            db.add(Topic(user_id=user_id, name=entry.title, course_name=course_name))
    db.commit()


def _run_processing_job(document_id: str, storage_key: str, ext: str, document_name: str, user_id: str):
    # MỞ SESSION RIÊNG — không dùng lại Session của request (bản trước truyền
    # thẳng `db: Session = Depends(get_db)` vào đây qua BackgroundTasks).
    # SQLAlchemy Session không an toàn khi dùng đồng thời từ nhiều thread;
    # BackgroundTasks chạy job này trên MỘT thread pool riêng, khác thread đã
    # tạo/dùng Session đó trong thân request — hoạt động "được" hiện tại chỉ
    # vì không có gì thật sự dùng chung ĐỒNG THỜI, không phải vì an toàn.
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        try:
            # pypdf/python-docx (app/ingestion/parser.py, outline.py) cần một
            # file THẬT trên đĩa — tải về file TẠM của riêng lượt xử lý này,
            # không phải bản lưu trữ lâu dài (đó là B2, key=storage_key).
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(storage.read_file(storage_key))
                file_path = tmp.name
            try:
                process_document(
                    db=db,
                    file_path=file_path,
                    document_id=document_id,
                    document_name=document_name,
                    user_id=user_id,
                )
                _save_outline(db, document_id, user_id, file_path, doc.course_name if doc else None)
            finally:
                os.remove(file_path)
            doc.status = "sẵn sàng"
            db.commit()
        except Exception as e:  # noqa: BLE001 - phải bắt mọi lỗi để cập nhật status, đúng AC F1
            # Không lưu str(e) NGUYÊN VĂN vào error_reason — trường này được
            # GET /documents trả thẳng cho client, có thể lộ đường dẫn cục bộ/
            # chi tiết thư viện. Ghi log đầy đủ ở server, chỉ lưu thông báo
            # chung cho client (cùng nguyên tắc đã áp dụng cho
            # app/main.py::unhandled_exception_handler).
            logger.exception("Xử lý tài liệu %s thất bại", document_id)
            doc.status = "lỗi"
            doc.error_reason = "Không xử lý được tài liệu này. Thử tải lại, hoặc kiểm tra định dạng file."
            db.commit()
    finally:
        db.close()


@router.post("")
async def upload_document(
    file: UploadFile,
    user_id: str,
    course_name: str | None = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(400, "Thiếu tên file.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Định dạng {ext} không được hỗ trợ. Chỉ chấp nhận PDF/DOCX.")

    document_id = str(uuid.uuid4())
    storage_key = _storage_key(document_id, ext)

    # Kiểm giới hạn dung lượng TRONG lúc ĐỌC (chưa tới 30MB nên gom hẳn vào bộ
    # nhớ trước khi upload R2 một lần — không cần multipart upload), không
    # phải sau khi đã nhận hết toàn bộ payload rồi mới kiểm: một client
    # (không xác thực — CURRENT_USER_ID cố định ở frontend, xem README) gửi
    # payload nhiều GB vẫn phải dừng SỚM, không được đọc hết vào RAM/đĩa rồi
    # mới từ chối.
    max_bytes = MAX_FILE_MB * 1024 * 1024
    buffer = bytearray()
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise HTTPException(400, f"File vượt quá {MAX_FILE_MB}MB.")

    storage.save_file(storage_key, bytes(buffer))

    # Versioning (TC20) — upload lại cùng file_name+course_name thì đánh dấu bản
    # cũ is_latest=False thay vì ghi đè/xoá, để hỏi đáp/quiz chỉ dùng bản mới
    # nhất (xem app/routers/chat.py, app/routers/quiz.py) nhưng vẫn giữ lịch sử.
    previous_latest = (
        db.query(Document)
        .filter(
            Document.user_id == user_id,
            Document.file_name == file.filename,
            Document.course_name == course_name,
            Document.is_latest == True,
        )
        .first()
    )
    version = 1
    if previous_latest:
        previous_latest.is_latest = False
        version = previous_latest.version + 1
        db.add(previous_latest)
        # Bản cũ không còn được dùng để hỏi đáp nữa nên dàn ý của nó cũng phải
        # gỡ đi, tránh chủ đề trùng lặp giữa các phiên bản.
        cleanup_document_topics(db, document_id=previous_latest.id, user_id=user_id)

    ensure_user(db, user_id)
    doc = Document(
        id=document_id,
        user_id=user_id,
        file_name=file.filename,
        course_name=course_name,
        status="đang xử lý",
        version=version,
        is_latest=True,
    )
    db.add(doc)
    db.commit()

    background_tasks.add_task(
        _run_processing_job, document_id, storage_key, ext, file.filename, user_id
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
            "version": d.version,
            "is_latest": d.is_latest,
        }
        for d in docs
    ]


MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/{document_id}/outline")
def get_document_outline(document_id: str, user_id: str, db: Session = Depends(get_db)):
    """Dàn ý chủ đề của tài liệu — để người dùng biết tài liệu gồm những gì
    trước khi phải tự nghĩ ra câu hỏi."""
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    if not doc:
        raise HTTPException(404, "Không tìm thấy tài liệu.")

    entries = (
        db.query(DocumentTopic)
        .filter(DocumentTopic.document_id == document_id, DocumentTopic.user_id == user_id)
        .order_by(DocumentTopic.order_index.asc())
        .all()
    )
    return {
        "document_id": document_id,
        "file_name": doc.file_name,
        "topics": [
            {"title": e.title, "position_ref": e.position_ref, "order": e.order_index}
            for e in entries
        ],
    }


@router.get("/{document_id}/file")
def get_document_file(document_id: str, user_id: str, db: Session = Depends(get_db)):
    """Trả file gốc để người dùng mở đúng trang từ một citation (spec mục 4.3,
    lớp 3). Với PDF, frontend gắn thêm '#page=N' bóc từ position_ref.

    Kiểm tra quyền sở hữu bằng user_id trước khi trả file — nếu không, bất kỳ
    ai biết document_id đều tải được tài liệu của người khác."""
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    if not doc:
        raise HTTPException(404, "Không tìm thấy tài liệu.")

    ext = os.path.splitext(doc.file_name)[1].lower()
    try:
        content = storage.read_file(_storage_key(document_id, ext))
    except Exception as exc:  # noqa: BLE001 — B2 trả lỗi khi object không tồn tại
        raise HTTPException(404, "File gốc của tài liệu này không còn trên kho lưu trữ.") from exc

    return Response(
        content=content,
        media_type=MEDIA_TYPES.get(ext, "application/octet-stream"),
        headers={"Content-Disposition": f'inline; filename="{doc.file_name}"'},
    )


@router.delete("/{document_id}")
def delete_document(document_id: str, user_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    if not doc:
        raise HTTPException(404, "Không tìm thấy tài liệu.")

    # Dọn dàn ý và những chủ đề nó tạo ra mà người học chưa từng dùng — nếu
    # không, kế hoạch ôn tập vẫn xếp lịch cho chủ đề của tài liệu đã xoá.
    cleanup_document_topics(db, document_id=document_id, user_id=user_id)

    # remove_document() chỉ flush(), KHÔNG tự commit (xem docstring
    # PgVectorStore) — xoá chunk và xoá Document giờ chung MỘT db.commit()
    # cuối cùng bên dưới: cùng-thành-công hoặc cùng-rollback, thay vì 2 lượt
    # commit rời nhau như bản trước (ARCH-3 — lỗi giữa chừng từng có thể để
    # lại Document đã xoá dở trong khi chunk vẫn còn nguyên, hoặc ngược lại).
    PgVectorStore(db=db, user_id=user_id).remove_document(document_id)

    db.delete(doc)
    db.commit()

    # B2 KHÔNG transactional CHUNG với Postgres — xoá SAU khi DB đã commit
    # thành công, không phải trước: nếu db.commit() ở trên thất bại, file gốc
    # trên B2 vẫn còn (đúng, vì Document/chunk cũng chưa thật sự bị xoá). Lỗi
    # xoá B2 chỉ log, không raise — với người dùng, tài liệu ĐÃ xoá xong
    # (không còn trong DB/truy hồi được nữa); một object rác còn sót trên B2
    # ít hại hơn nhiều so với việc báo "xoá thất bại" cho một thao tác đã
    # thành công ở phần quan trọng.
    ext = os.path.splitext(doc.file_name)[1].lower()
    try:
        storage.delete_file(_storage_key(document_id, ext))
    except Exception:  # noqa: BLE001
        logger.exception("Xoá file gốc trên B2 thất bại cho document %s", document_id)

    return {"status": "deleted", "document_id": document_id}
