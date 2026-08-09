# EduTutor

Nền tảng hỗ trợ học tập cá nhân hóa dùng LLM + RAG: tải tài liệu học tập (PDF/DOCX), hỏi đáp có trích dẫn nguồn, tự sinh quiz trắc nghiệm để tự kiểm tra, và theo dõi mức độ thành thạo (mastery) theo từng chủ đề.

## Mục lục

- [Tổng quan](#tổng-quan)
- [Kiến trúc & công nghệ](#kiến-trúc--công-nghệ)
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [Cài đặt](#cài-đặt)
- [Sử dụng](#sử-dụng)
- [API tóm tắt](#api-tóm-tắt)
- [Chạy test](#chạy-test)
- [Chưa làm / hướng phát triển tiếp](#chưa-làm--hướng-phát-triển-tiếp)

## Tổng quan

Tính năng đã triển khai:

| Tính năng | Mô tả |
| --- | --- |
| **Quản lý tài liệu** | Tải lên PDF/DOCX theo môn học, xử lý nền (parse → chunk → embed → lưu vector), theo dõi trạng thái "đang xử lý" / "sẵn sàng" / "lỗi", xoá tài liệu. |
| **Hỏi đáp RAG** | Đặt câu hỏi về nội dung tài liệu đã tải; câu trả lời đi kèm trích dẫn nguồn (tên tài liệu + vị trí). Có bước verifier để đảm bảo không "bịa" câu trả lời khi nội dung không có trong tài liệu. Lưu lại lịch sử hội thoại, xem lại hoặc tạo cuộc hội thoại mới. |
| **Quiz tự kiểm tra** | Tự sinh 5 câu hỏi trắc nghiệm (có thể gắn theo chủ đề) từ nội dung tài liệu, mỗi câu đã qua verifier để đảm bảo đáp án đúng và giải thích khớp với tài liệu nguồn. |
| **Mastery theo chủ đề** | Chấm điểm mức độ thành thạo (0–1) theo công thức rule-based có trọng số suy giảm theo thời gian (recency-weighted, half-life 14 ngày) mỗi khi nộp bài quiz. Dashboard tổng quan hiển thị điểm mastery, số tài liệu, số quiz, tỉ lệ đúng. |

Chưa làm: Flashcard, lập kế hoạch học tập (study plan), đăng nhập/đa người dùng thật (hiện dùng `user_id` cố định `demo-user` cho walking skeleton).

## Kiến trúc & công nghệ

**Backend:** Python, FastAPI, SQLAlchemy (SQLite), sentence-transformers (embedding local), FAISS (vector store theo từng user), Google Gemini API (LLM, free tier).

**Frontend:** React 18 + Vite, React Router, Tailwind CSS, lucide-react.

Pipeline RAG là generator + verifier hai bước cố định (không phải multi-agent tự quyết định hành động): generator sinh câu trả lời/câu hỏi dựa trên chunk truy hồi được, verifier kiểm tra lại tính đúng đắn/căn cứ trước khi trả về.

## Cấu trúc dự án

```
backend/
  app/
    models.py, database.py        # SQLite qua SQLAlchemy
    ingestion/
      parser.py                   # PDF/DOCX -> sections
      chunker.py                  # sections -> chunks
      embedder.py                 # chunks -> vector (sentence-transformers, local)
      pipeline.py                 # nối parser -> chunker -> embedder -> vector store
    vectorstore/
      faiss_store.py              # FAISS local, mỗi user 1 index riêng
    llm/
      rag.py                      # hỏi đáp — generator + verifier
      quiz_generator.py           # sinh quiz — generator + verifier từng câu
      gemini_client.py            # client gọi Gemini API thật
    mastery.py                    # công thức tính mastery rule-based
    routers/
      documents.py                 # upload, list, xoá tài liệu
      chat.py                      # hỏi đáp RAG + lịch sử hội thoại
      quiz.py                      # sinh quiz, nộp bài, cập nhật mastery
      mastery.py                   # đọc dữ liệu mastery cho dashboard
    main.py
  tests/                          # unittest, xem mục Chạy test
frontend/
  src/
    api.js                        # gọi API backend
    pages/
      DashboardPage.jsx           # tổng quan mastery + tài liệu gần đây
      UploadPage.jsx               # quản lý tài liệu
      ChatPage.jsx                 # hỏi đáp + sidebar lịch sử hội thoại
      QuizPage.jsx                 # làm quiz
    components/                   # UI dùng chung (Button, Card, ...)
```

## Cài đặt

Yêu cầu: Python 3.11+, Node.js 18+.

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r ../requirements.txt

cp ../.env.example ../.env
# Mở .env ở thư mục gốc, dán GEMINI_API_KEY lấy miễn phí tại https://aistudio.google.com/apikey

uvicorn app.main:app --reload
# API chạy ở http://localhost:8000, xem docs tự động ở http://localhost:8000/docs
```

> Lưu ý: model Gemini mặc định cấu hình trong `backend/app/llm/gemini_client.py` (hiện là `gemini-3.1-flash-lite`). Google thường xuyên thay đổi chính sách/khả dụng của model theo free tier — nếu gặp lỗi `429 ResourceExhausted` với `limit: 0`, model đó có thể đã bị deprecate; kiểm tra model còn free tier tại [trang rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) và đổi lại tên model trong file trên.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# Mở http://localhost:5173
```

## Sử dụng

1. Vào trang **Tài liệu**, tải lên 1 file PDF hoặc DOCX + nhập tên môn học. Đợi trạng thái chuyển từ "đang xử lý" → "sẵn sàng" (lần đầu sẽ chậm hơn vì phải tải model embedding về máy).
2. Sang trang **Hỏi đáp**, hỏi một câu liên quan đến nội dung tài liệu vừa tải — câu trả lời sẽ kèm nguồn trích (tên tài liệu + vị trí). Bấm "Cuộc hội thoại mới" ở sidebar để bắt đầu hội thoại khác, hoặc chọn lại một hội thoại cũ trong danh sách để xem lại.
3. Thử hỏi một câu **không có trong tài liệu** — hệ thống phải trả lời "Nội dung này chưa có trong tài liệu bạn đã tải lên" thay vì bịa câu trả lời.
4. Sang trang **Quiz**, chọn tài liệu đã sẵn sàng, nhập tên chủ đề (tuỳ chọn), bấm "Tạo quiz" — hệ thống sinh 5 câu hỏi trắc nghiệm đã qua verifier. Trả lời từng câu để xem đáp án đúng/sai kèm giải thích; điểm mastery của chủ đề đó sẽ được cập nhật.
5. Vào trang **Tổng quan** để xem điểm mastery theo từng chủ đề, số tài liệu/quiz, và tỉ lệ trả lời đúng.

## API tóm tắt

| Method & Path | Mô tả |
| --- | --- |
| `POST /documents` | Tải lên tài liệu (multipart), xử lý nền |
| `GET /documents` | Liệt kê tài liệu theo `user_id` |
| `DELETE /documents/{id}` | Xoá tài liệu + dữ liệu vector liên quan |
| `POST /chat/ask` | Đặt câu hỏi RAG, tự tạo hội thoại mới nếu chưa có `conversation_id` |
| `GET /chat/conversations` | Liệt kê hội thoại theo `user_id`, kèm preview câu hỏi đầu tiên |
| `GET /chat/conversations/{id}` | Lấy toàn bộ tin nhắn của một hội thoại |
| `POST /quiz/generate` | Sinh quiz trắc nghiệm từ một tài liệu |
| `POST /quiz/submit` | Nộp đáp án 1 câu, trả kết quả + cập nhật mastery |
| `GET /mastery` | Tổng quan mastery theo chủ đề + số liệu thống kê |

Xem chi tiết request/response tại `http://localhost:8000/docs` (Swagger UI tự sinh) khi backend đang chạy.

## Chạy test

```bash
cd backend
python -m unittest discover -s tests -v
```

Các test hiện có (`test_chunker.py`, `test_parser.py`, `test_rag.py`, `test_quiz_generator.py`, `test_mastery.py`) kiểm tra phần logic thuần Python (chunking, RAG orchestration, quiz orchestration, công thức mastery, parse DOCX) bằng fake LLM client — không cần mạng hay API key thật. Phần cần thư viện ngoài/kết nối thật (embedding, FAISS, Gemini API, router FastAPI, build frontend) chưa có test tự động, cần tự chạy thử thủ công như hướng dẫn ở mục Sử dụng.

## Chưa làm / hướng phát triển tiếp

- **Flashcard** — có thể tái dùng gần như nguyên `quiz_generator.py`, chỉ đổi prompt/output shape (front/back thay vì question/options).
- **Lập kế hoạch học tập (study plan)** — phụ thuộc dữ liệu `MasteryScore` đã có sẵn.
- **Đăng nhập/đa người dùng thật** — hiện `user_id` cố định `demo-user` ở frontend (`frontend/src/api.js`), chưa có xác thực.
- **Xoá/đổi tên cuộc hội thoại** trong lịch sử hỏi đáp.
