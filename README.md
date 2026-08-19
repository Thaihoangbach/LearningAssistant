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
- [Đánh giá chất lượng (Golden Set)](#đánh-giá-chất-lượng-golden-set)
- [Chưa làm / hướng phát triển tiếp](#chưa-làm--hướng-phát-triển-tiếp)

## Tổng quan

Tính năng đã triển khai:

| Tính năng | Mô tả |
| --- | --- |
| **Quản lý tài liệu** | Tải lên PDF/DOCX theo môn học, xử lý nền (parse → chunk → embed → lưu vector), theo dõi trạng thái "đang xử lý" / "sẵn sàng" / "lỗi", xoá tài liệu. Upload lại cùng tên file + môn học sẽ tạo phiên bản mới (versioning) — hỏi đáp chỉ dùng bản mới nhất, bản cũ vẫn giữ lại. |
| **Hỏi đáp RAG** | Đặt câu hỏi về nội dung tài liệu đã tải; câu trả lời đi kèm trích dẫn nguồn (tên tài liệu + vị trí), tổng hợp/nêu rõ khác biệt khi thông tin đến từ nhiều nguồn. Hiểu được câu hỏi tiếp nối dựa trên vài lượt hội thoại gần nhất (vd: "vậy tại sao *nó* không cần RNN?"), diễn đạt lại đơn giản hơn khi người dùng nói chưa hiểu, và có thể điều chỉnh độ sâu câu trả lời theo trình độ khai báo (`level`). Có bước verifier để đảm bảo không "bịa" câu trả lời khi nội dung không có trong tài liệu, và bước guardrail để chặn prompt injection/jailbreak, yêu cầu làm bài hộ, cùng câu hỏi ngoài phạm vi học tập trước khi trả lời. Lưu lại lịch sử hội thoại, xem lại hoặc tạo cuộc hội thoại mới. |
| **Gợi ý học tiếp theo** | Hỏi kiểu "tôi nên học gì tiếp theo?" sẽ được nhận diện và trả lời ngay từ dữ liệu mastery đã có (chủ đề điểm thấp nhất), không cần gọi LLM. |
| **Quiz tự kiểm tra** | Sinh câu hỏi trắc nghiệm (có thể gắn theo chủ đề, chọn độ khó, gộp nhiều tài liệu thành 1 quiz tổng hợp) từ nội dung tài liệu, mỗi câu đã qua verifier để đảm bảo đáp án đúng và giải thích khớp với tài liệu nguồn. |
| **Flashcard** | Sinh flashcard (mặt trước/mặt sau) từ tài liệu, cùng kỹ thuật generator + verifier với quiz. |
| **Kế hoạch học tập** | Lập lịch ôn tập theo số ngày còn lại tới hạn, ưu tiên chủ đề điểm thấp/chưa học trước — tính lại từ dữ liệu mastery hiện có mỗi lần gọi, tự động phản ánh tiến độ mới nhất. |
| **Mastery theo chủ đề** | Chấm điểm mức độ thành thạo (0–1) theo công thức rule-based có trọng số suy giảm theo thời gian (recency-weighted, half-life 14 ngày) mỗi khi nộp bài quiz. Dashboard tổng quan hiển thị điểm mastery, số tài liệu, số quiz, tỉ lệ đúng. |

Chưa làm: cá nhân hoá theo mục tiêu học tập dài hạn (deadline/kế hoạch tự sinh theo goal), gợi ý theo prerequisite (cần đồ thị kiến thức chưa xây dựng), theo dõi thời gian học thực tế, đăng nhập/đa người dùng thật (hiện dùng `user_id` cố định `demo-user` cho walking skeleton).

## Kiến trúc & công nghệ

**Backend:** Python, FastAPI, SQLAlchemy (SQLite), sentence-transformers (embedding local), FAISS (vector store theo từng user), Google Gemini API (LLM, free tier).

**Frontend:** React 18 + Vite, React Router, Tailwind CSS, lucide-react.

Pipeline RAG là generator + verifier hai bước cố định (không phải multi-agent tự quyết định hành động): generator sinh câu trả lời/câu hỏi dựa trên chunk truy hồi được, verifier kiểm tra lại tính đúng đắn/căn cứ trước khi trả về. Trước bước generator, câu hỏi hỏi đáp còn đi qua guardrail 2 tầng: rule-based chặn ngay các pattern injection/jailbreak rõ ràng (không tốn quota), câu mơ hồ hơn mới gọi thêm 1 lượt Gemini làm gatekeeper phân loại an toàn/không an toàn.

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
      guardrail.py                # chặn prompt injection/jailbreak + câu hỏi ngoài phạm vi (trước generator)
      rag.py                      # hỏi đáp — generator + verifier
      quiz_generator.py           # sinh quiz — generator + verifier từng câu
      flashcard_generator.py      # sinh flashcard — generator + verifier từng thẻ (tái dùng pattern quiz)
      recommendation.py           # gợi ý học tiếp theo — rule-based, đọc lại MasteryScore
      gemini_client.py            # client gọi Gemini API thật
    mastery.py                    # công thức tính mastery rule-based
    study_planner.py              # lập kế hoạch học tập — rule-based, tính lại mỗi lần gọi
    routers/
      documents.py                 # upload (có versioning), list, xoá tài liệu
      chat.py                      # hỏi đáp RAG + gợi ý học tiếp theo + lịch sử hội thoại
      quiz.py                      # sinh quiz (đa tài liệu, theo độ khó), nộp bài, cập nhật mastery
      flashcard.py                 # sinh flashcard từ tài liệu
      mastery.py                   # đọc dữ liệu mastery cho dashboard
      study_plan.py                 # trả kế hoạch học tập theo số ngày còn lại
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

**Cách 1 — Docker (khuyến nghị, dữ liệu upload không mất khi restart/rebuild container):**

```bash
cp .env.example .env
# Mở .env ở thư mục gốc, dán GEMINI_API_KEY lấy miễn phí tại https://aistudio.google.com/apikey

docker compose up --build
# API chạy ở http://localhost:8001, xem docs tự động ở http://localhost:8001/docs
# (đổi cổng host qua biến BACKEND_PORT nếu 8001 cũng bận, vd: BACKEND_PORT=8002 docker compose up -d
#  — nhớ sửa API_BASE tương ứng trong frontend/src/api.js)
```

File upload, SQLite DB (`edututor.db`) và FAISS index đều nằm trong `backend/data/`, được mount qua Docker named volume `edututor_data` (khai báo ở `docker-compose.yml`) — `docker compose down` rồi `up` lại, hay build lại image sau khi sửa code, dữ liệu đã upload vẫn còn nguyên. Chỉ mất khi chủ động chạy `docker compose down -v` (xoá cả volume).

**Cách 2 — venv thủ công:**

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Mở .env ở thư mục gốc, dán GEMINI_API_KEY lấy miễn phí tại https://aistudio.google.com/apikey

uvicorn app.main:app --reload --port 8001
# API chạy ở http://localhost:8001, xem docs tự động ở http://localhost:8001/docs
```

Ở cách này dữ liệu upload vẫn được lưu lại bình thường trong `backend/data/` trên máy (không mất) — Docker chỉ cần thiết khi chạy trong môi trường container mà filesystem của container bị xoá giữa các lần restart/deploy.

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
| `POST /documents` | Tải lên tài liệu (multipart), xử lý nền. Upload lại cùng tên file + môn học sẽ tạo phiên bản mới. |
| `GET /documents` | Liệt kê tài liệu theo `user_id` (kèm `version`, `is_latest`) |
| `DELETE /documents/{id}` | Xoá tài liệu + dữ liệu vector liên quan |
| `POST /chat/ask` | Đặt câu hỏi RAG (tuỳ chọn `level`: beginner/advanced), tự tạo hội thoại mới nếu chưa có `conversation_id`. Câu hỏi kiểu "nên học gì tiếp theo?" được trả lời trực tiếp từ dữ liệu mastery, không qua RAG. |
| `GET /chat/conversations` | Liệt kê hội thoại theo `user_id`, kèm preview câu hỏi đầu tiên |
| `GET /chat/conversations/{id}` | Lấy toàn bộ tin nhắn của một hội thoại |
| `POST /quiz/generate` | Sinh quiz trắc nghiệm từ 1 tài liệu (`document_id`) hoặc nhiều tài liệu (`document_ids`), tuỳ chọn `difficulty` |
| `POST /quiz/submit` | Nộp đáp án 1 câu, trả kết quả + cập nhật mastery |
| `POST /flashcard/generate` | Sinh flashcard (front/back) từ một tài liệu |
| `GET /mastery` | Tổng quan mastery theo chủ đề + số liệu thống kê |
| `GET /study-plan` | Kế hoạch ôn tập theo `days` còn lại, ưu tiên chủ đề yếu/chưa học |

Xem chi tiết request/response tại `http://localhost:8001/docs` (Swagger UI tự sinh) khi backend đang chạy.

## Chạy test

```bash
cd backend
python -m unittest discover -s tests -v
```

Các test hiện có (`test_chunker.py`, `test_parser.py`, `test_rag.py`, `test_quiz_generator.py`, `test_flashcard_generator.py`, `test_mastery.py`, `test_guardrail.py`, `test_recommendation.py`, `test_study_planner.py`) kiểm tra phần logic thuần Python (chunking, RAG orchestration, quiz/flashcard orchestration, công thức mastery, parse DOCX, guardrail, gợi ý học tiếp theo, lập kế hoạch học tập) bằng fake LLM client — không cần mạng hay API key thật. Phần cần thư viện ngoài/kết nối thật (embedding, FAISS, Gemini API, build frontend) chưa có test tự động, cần tự chạy thử thủ công như hướng dẫn ở mục Sử dụng.

> **Lưu ý khi cập nhật lên phiên bản này:** `models.py` vừa thêm cột mới (`Document.version`, `Document.is_latest`) và bảng mới (`flashcard_sets`, `flashcard_items`). Dự án chưa có công cụ migration (Alembic) — nếu đã có sẵn `backend/data/edututor.db` từ trước, cần xoá file này (hoặc tự thêm cột) để `init_db()` tạo lại schema đúng, nếu không `/documents` và `/chat/ask` sẽ lỗi "no such column".

## Đánh giá chất lượng (Golden Set)

[`docs/eval/golden_set.yaml`](docs/eval/golden_set.yaml) là bộ 60 case đánh giá toàn vòng đời hệ thống (Document → Retrieval → Generation → Personalization → Assessment → Recommendation → Planning → Analytics → Safety), mỗi case gắn `implementation_status` đối chiếu với code thật (đã làm được / làm một phần / chưa làm). Xem [`docs/eval/README.md`](docs/eval/README.md) để biết cách dùng, phát hiện quan trọng nhất (indirect prompt injection qua nội dung tài liệu chưa được chặn), và khi nào nên dùng RAGAS so với LLM-as-judge tự viết cho từng nhóm case.

## Chưa làm / hướng phát triển tiếp

- **Cá nhân hoá theo mục tiêu học tập dài hạn** (vd: "ôn thi trong 2 tuần" tự sinh kế hoạch theo goal) — `GET /study-plan` mới hỗ trợ theo số ngày, chưa gắn với goal/deadline lưu trữ lâu dài.
- **Gợi ý theo prerequisite** (vd: học Transformer thì gợi ý học Attention trước) — cần một đồ thị/quan hệ phụ thuộc giữa các chủ đề, hiện chưa có nguồn dữ liệu này.
- **Theo dõi thời gian học thực tế** cho Learning Analytics — cần instrument sự kiện ở frontend, chưa thu thập.
- **Xử lý "một phần căn cứ"** — verifier hiện chỉ CÓ/KHÔNG nhị phân; câu trả lời có bằng chứng một phần bị từ chối toàn bộ thay vì nêu rõ phần nào đã xác minh được.
- **Đăng nhập/đa người dùng thật** — hiện `user_id` cố định `demo-user` ở frontend (`frontend/src/api.js`), chưa có xác thực.
- **Xoá/đổi tên cuộc hội thoại** trong lịch sử hỏi đáp.
- **Trình độ/độ khó (`level`, `difficulty`) hiện truyền tường minh mỗi request**, chưa lưu thành hồ sơ người học (Learning Profile) để tự động áp dụng.
