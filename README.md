# EduTutor — F1 + F2 + F3 + F4 (một phần)

Nền tảng hỗ trợ học tập cá nhân hóa dùng LLM + RAG, theo đúng thiết kế trong `PRD-nen-tang-ho-tro-hoc-tap-ca-nhan-hoa.md` và `architecture-diagrams.md`.

Đã triển khai: **F1** (quản lý tài liệu), **F2** (hỏi đáp RAG có trích dẫn + verifier), **F3** (sinh Quiz trắc nghiệm có verifier từng câu), và phần lõi của **F4** (công thức tính mastery rule-based + cập nhật khi nộp bài quiz). Chưa làm: giao diện dashboard tổng hợp mastery theo chủ đề, Flashcard, F5 (lập kế hoạch học tập).

## ⚠️ Tình trạng kiểm thử — đọc trước khi tin tưởng code này

Sandbox dùng để viết code này **không có kết nối mạng**, nên không cài được các thư viện cần thiết (`fastapi`, `sentence-transformers`, `faiss-cpu`, `google-generativeai`...). Vì vậy:

| Module | Trạng thái |
| --- | --- |
| `app/ingestion/chunker.py` | ✅ **Đã viết test và chạy thật, pass 6/6** (`tests/test_chunker.py`) — chỉ dùng thư viện chuẩn Python |
| `app/ingestion/parser.py` (nhánh DOCX) | ✅ **Đã viết test và chạy thật, pass** — dùng `python-docx` (có sẵn trong sandbox) |
| `app/ingestion/parser.py` (nhánh PDF) | ⚠️ Có implementation, **chưa test tích hợp được** (không tạo được PDF fixture hợp lệ mà không cần thêm thư viện). **Cần bạn tự test với file PDF thật trước khi tin tưởng.** |
| `app/llm/rag.py` (logic generator + verifier F2) | ✅ **Đã viết test và chạy thật, pass 5/5** (`tests/test_rag.py`) — dùng fake LLM client, không cần gọi API thật |
| `app/llm/quiz_generator.py` (logic generator + verifier F3) | ✅ **Đã viết test và chạy thật, pass 7/7** (`tests/test_quiz_generator.py`) — dùng fake LLM client |
| `app/mastery.py` (công thức tính mastery F4) | ✅ **Đã viết test và chạy thật, pass 6/6** (`tests/test_mastery.py`) — thuần Python, không phụ thuộc gì |
| `app/ingestion/embedder.py`, `app/vectorstore/faiss_store.py`, `app/llm/gemini_client.py` | ❌ **Chưa chạy được** — cần `pip install` các thư viện tương ứng và (với Gemini) một API key thật |
| `app/routers/*.py`, `app/main.py`, `app/models.py`, `app/database.py` | ❌ **Chưa chạy được** — cần `pip install fastapi sqlalchemy ...` |
| `frontend/` | ❌ **Chưa chạy được** — cần `npm install` |

**Tổng cộng 28/28 test đã viết đều pass thật** — nhưng đó là các test cho phần logic thuần túy (chunking, RAG orchestration, quiz orchestration, mastery, parse DOCX). Toàn bộ phần cần thư viện ngoài (embedding thật, FAISS thật, Gemini thật, FastAPI server thật, React build thật) **bạn cần tự cài đặt và chạy thử ở máy local** — đừng coi đây là "đã hoàn thành và chạy được", mà là "logic cốt lõi đã được kiểm chứng, phần còn lại đã viết sẵn và cần bạn xác nhận chạy được ở môi trường có mạng".

## Cài đặt (chạy ở máy có mạng)

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Mở .env, dán GEMINI_API_KEY lấy miễn phí tại https://aistudio.google.com/apikey

# Chạy lại toàn bộ test (bao gồm cả phần chưa chạy được trong sandbox)
python3 -m unittest discover -s tests -v

# Chạy server
uvicorn app.main:app --reload
# API chạy ở http://localhost:8000, xem docs tự động ở http://localhost:8000/docs
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# Mở http://localhost:5173
```

### 3. Thử luồng end-to-end

1. Vào trang **Tài liệu**, tải lên 1 file PDF hoặc DOCX + nhập tên môn học.
2. Đợi trạng thái chuyển từ "đang xử lý" → "sẵn sàng" (lần đầu sẽ chậm hơn vì phải tải model embedding về máy).
3. Sang trang **Hỏi đáp**, hỏi một câu liên quan đến nội dung tài liệu vừa tải — câu trả lời sẽ kèm nguồn trích (tên tài liệu + vị trí).
4. Thử hỏi một câu **không có trong tài liệu** — hệ thống phải trả lời "Nội dung này chưa có trong tài liệu bạn đã tải lên" thay vì bịa câu trả lời.
5. Sang trang **Quiz**, chọn tài liệu đã sẵn sàng, nhập tên chủ đề (tuỳ chọn), bấm "Tạo quiz" — hệ thống sinh 5 câu hỏi trắc nghiệm đã qua verifier. Trả lời từng câu để xem đáp án đúng/sai kèm giải thích.

## Cấu trúc dự án

```
backend/
  app/
    models.py, database.py       # SQLite qua SQLAlchemy
    ingestion/
      parser.py                   # PDF/DOCX -> sections (đã test nhánh DOCX)
      chunker.py                  # sections -> chunks (đã test đầy đủ)
      embedder.py                 # chunks -> vector (sentence-transformers, local)
      pipeline.py                 # nối parser -> chunker -> embedder -> vector store
    vectorstore/
      faiss_store.py              # FAISS local, mỗi user 1 index riêng
    llm/
      rag.py                      # F2 — generator + verifier hỏi đáp (đã test đầy đủ)
      quiz_generator.py            # F3 — generator + verifier từng câu quiz (đã test đầy đủ)
      gemini_client.py            # implementation thật gọi Gemini API
    mastery.py                     # F4 — công thức mastery rule-based (đã test đầy đủ)
    routers/
      documents.py                 # F1 — upload, list, xử lý nền
      chat.py                       # F2 — hỏi đáp RAG
      quiz.py                       # F3 — sinh quiz, nộp bài, trigger cập nhật mastery (F4)
    main.py
  tests/
    test_chunker.py, test_parser.py, test_rag.py,
    test_quiz_generator.py, test_mastery.py        # 28 test, tất cả pass
frontend/
  src/
    api.js
    pages/UploadPage.jsx, ChatPage.jsx, QuizPage.jsx
```

## Bước tiếp theo (chưa làm)

- **Dashboard tiến độ (phần còn lại của F4)** — hiện `MasteryScore` đã được tính và lưu mỗi khi nộp quiz, nhưng chưa có trang frontend hiển thị tổng quan theo chủ đề. Cần thêm route `GET /mastery?user_id=...` và trang `MasteryDashboard.jsx`.
- **Flashcard (phần còn lại của F3)** — có thể tái dùng gần như nguyên `quiz_generator.py`, chỉ đổi prompt/output shape (front/back thay vì question/options).
- **F5** — Lập kế hoạch học tập, phụ thuộc dữ liệu `MasteryScore` đã có sẵn từ F4.

Mỗi bước nên tiếp tục theo TDD: viết test cho phần logic thuần túy trước (giống `chunker.py`/`rag.py`/`quiz_generator.py`/`mastery.py`), phần cần thư viện ngoài (router, model) viết sau và tự chạy thử ở máy có mạng.
