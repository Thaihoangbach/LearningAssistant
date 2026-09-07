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
- [Deploy](#deploy)
- [Đánh giá chất lượng (Golden Set)](#đánh-giá-chất-lượng-golden-set)
- [Chưa làm / hướng phát triển tiếp](#chưa-làm--hướng-phát-triển-tiếp)

## Tổng quan

Tính năng đã triển khai:

| Tính năng | Mô tả |
| --- | --- |
| **Quản lý tài liệu** | Tải lên PDF/DOCX theo môn học, xử lý nền (parse → chunk → embed → lưu vector), theo dõi trạng thái "đang xử lý" / "sẵn sàng" / "lỗi", xoá tài liệu. Upload lại cùng tên file + môn học sẽ tạo phiên bản mới (versioning) — hỏi đáp chỉ dùng bản mới nhất, bản cũ vẫn giữ lại. |
| **Hỏi đáp RAG** | Đặt câu hỏi về nội dung tài liệu đã tải; câu trả lời đi kèm trích dẫn nguồn (tên tài liệu + vị trí), tổng hợp/nêu rõ khác biệt khi thông tin đến từ nhiều nguồn. Hiểu được câu hỏi tiếp nối dựa trên vài lượt hội thoại gần nhất (vd: "vậy tại sao *nó* không cần RNN?"), diễn đạt lại đơn giản hơn khi người dùng nói chưa hiểu, và điều chỉnh độ sâu câu trả lời theo trình độ (`level`) — khai báo tường minh hoặc lấy lại từ Learning Profile nếu không truyền. Có bước verifier để đảm bảo không "bịa" câu trả lời khi nội dung không có trong tài liệu, và bước guardrail để chặn prompt injection/jailbreak, yêu cầu làm bài hộ, cùng câu hỏi ngoài phạm vi học tập trước khi trả lời. Lưu lại lịch sử hội thoại, xem lại hoặc tạo cuộc hội thoại mới. |
| **Gợi ý học tiếp theo** | Hỏi kiểu "tôi nên học gì tiếp theo?" sẽ được nhận diện và trả lời ngay từ dữ liệu mastery đã có (chủ đề điểm thấp nhất), không cần gọi LLM. |
| **Quiz tự kiểm tra** | Sinh câu hỏi trắc nghiệm (có thể gắn theo chủ đề, chọn độ khó, gộp nhiều tài liệu thành 1 quiz tổng hợp) từ nội dung tài liệu, mỗi câu đã qua verifier để đảm bảo đáp án đúng và giải thích khớp với tài liệu nguồn. |
| **Flashcard** | Sinh flashcard (mặt trước/mặt sau) từ tài liệu, cùng kỹ thuật generator + verifier với quiz. |
| **Kế hoạch học tập** | Lập lịch ôn tập theo số ngày còn lại tới hạn, ưu tiên chủ đề điểm thấp/chưa học trước — tính lại từ dữ liệu mastery hiện có mỗi lần gọi, tự động phản ánh tiến độ mới nhất. |
| **Mastery theo chủ đề** | Chấm điểm mức độ thành thạo (0–1) theo công thức rule-based có trọng số suy giảm theo thời gian (recency-weighted, half-life 14 ngày) mỗi khi nộp bài quiz. Dashboard tổng quan hiển thị điểm mastery, số tài liệu, số quiz, tỉ lệ đúng. |
| **Hồ sơ học tập (Learning Profile)** | Lưu `preferred_level` (trình độ) dùng chung giữa hỏi đáp và sinh quiz — chỉ cần khai báo `level`/`difficulty` một lần, các lượt sau tự áp dụng lại nếu không truyền tham số mới; truyền tường minh lại thì ghi đè preference. Nếu chưa từng khai báo, hệ thống tự suy trình độ từ điểm mastery trung bình hiện có (mastery yếu → beginner, tốt → advanced). Có `learning_goal` (mục tiêu học tập, dạng text tự do) — được lọc injection ngay khi lưu (`contains_hard_block_pattern`), sau đó đưa vào prompt sinh câu trả lời như bối cảnh tham khảo (không phải chỉ dẫn). `GET /profile` trả cả `weak_topics`/`mastered_topics` suy từ mastery hiện có. |

Chưa làm: gợi ý theo prerequisite (cần đồ thị kiến thức chưa xây dựng), theo dõi thời gian học thực tế, đăng nhập/đa người dùng thật (hiện dùng `user_id` cố định `demo-user` cho walking skeleton).

## Kiến trúc & công nghệ

**Backend:** Python, FastAPI, SQLAlchemy + Alembic, PostgreSQL + pgvector (dữ liệu quan hệ VÀ vector embedding trong cùng một DB — xem `app/vectorstore/pgvector_store.py`), Cohere API (embedding + rerank, `app/ingestion/embedder.py`/`app/retrieval/reranker.py`), Backblaze B2 (lưu file gốc đã tải lên, S3-compatible, `app/storage.py`), OpenAI API (LLM mặc định — `app/llm/client_factory.py` tự rơi về Google Gemini nếu chỉ có `GEMINI_API_KEY`). Backend hoàn toàn **stateless** — không có gì cần đĩa bền vững, deploy được lên host free tier không có volume (Render).

**Frontend:** React 18 + Vite, React Router, Tailwind CSS, lucide-react.

Pipeline RAG là generator + verifier hai bước cố định (không phải multi-agent tự quyết định hành động): generator sinh câu trả lời/câu hỏi dựa trên chunk truy hồi được, verifier kiểm tra lại tính đúng đắn/căn cứ trước khi trả về. Trước bước generator, câu hỏi hỏi đáp còn đi qua guardrail 2 tầng: rule-based chặn ngay các pattern injection/jailbreak rõ ràng (không tốn quota), câu mơ hồ hơn mới gọi thêm 1 lượt Gemini làm gatekeeper phân loại an toàn/không an toàn.

## Cấu trúc dự án

```
backend/
  alembic/                       # Migration schema (Postgres)
  app/
    models.py, database.py        # Postgres + pgvector qua SQLAlchemy
    storage.py                     # File gốc trên Backblaze B2 (S3-compatible)
    ingestion/
      parser.py                   # PDF/DOCX -> sections
      chunker.py                  # sections -> chunks
      embedder.py                 # chunks -> vector (Cohere Embed API)
      pipeline.py                 # nối parser -> chunker -> embedder -> vector store
    vectorstore/
      pgvector_store.py           # Hybrid search (pgvector + Postgres full-text) theo user
    retrieval/
      reranker.py                 # Rerank kết quả hybrid (Cohere Rerank API)
    llm/
      guardrail.py                # chặn prompt injection/jailbreak + câu hỏi ngoài phạm vi (trước generator)
      rag.py                      # hỏi đáp — generator + verifier
      quiz_generator.py           # sinh quiz — generator + verifier từng câu
      flashcard_generator.py      # sinh flashcard — generator + verifier từng thẻ (tái dùng pattern quiz)
      recommendation.py           # gợi ý học tiếp theo — rule-based, đọc lại MasteryScore
      client_factory.py           # chọn LLM client thật — OpenAI (mặc định) hoặc Gemini theo key/LLM_PROVIDER
      openai_client.py            # client gọi OpenAI API thật
      gemini_client.py            # client gọi Gemini API thật (fallback)
    mastery.py                    # công thức tính mastery rule-based
    study_planner.py              # lập kế hoạch học tập — rule-based, tính lại mỗi lần gọi
    learning_profile.py           # logic thuần: level nào áp dụng, có nên ghi đè preference không
    routers/
      documents.py                 # upload (có versioning), list, xoá tài liệu
      chat.py                      # hỏi đáp RAG + gợi ý học tiếp theo + lịch sử hội thoại
      quiz.py                      # sinh quiz (đa tài liệu, theo độ khó), nộp bài, cập nhật mastery
      flashcard.py                 # sinh flashcard từ tài liệu
      mastery.py                   # đọc dữ liệu mastery cho dashboard
      study_plan.py                 # trả kế hoạch học tập theo số ngày còn lại
      profile.py                   # xem/cập nhật Learning Profile (preferred_level, learning_goal)
    main.py
tests/                            # unittest, TÁCH KHỎI backend/ — xem mục Chạy test
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

Yêu cầu: Python 3.11+, Node.js 18+, Docker (cho Postgres+pgvector cục bộ).

### 0. Hạ tầng (Postgres, và tài khoản Cohere/R2)

```bash
# Postgres + pgvector cục bộ — dữ liệu mất khi xoá container, đủ cho phát triển.
docker run -d --name edututor-pg -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=edututor \
  pgvector/pgvector:pg16
```

Cần thêm 2 key/bộ credential miễn phí (xem chi tiết cách lấy ở mục [Deploy](#deploy)):
- **Cohere API key** (embedding + rerank) — https://dashboard.cohere.com/api-keys
- **Backblaze B2** (lưu file gốc) — endpoint + access key + secret key, tạo tại Backblaze dashboard (Bucket + Application Key là hai bước riêng)

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r ../requirements.txt

cp ../.env.example ../.env
# Điền DATABASE_URL (trỏ vào Postgres vừa dựng ở bước 0), OPENAI_API_KEY hoặc
# GEMINI_API_KEY, COHERE_API_KEY, và 4 biến STORAGE_* trong .env ở thư mục gốc.

alembic upgrade head
# Tạo schema — BẮT BUỘC chạy lần đầu và sau mỗi lần models.py có cột/bảng mới.

uvicorn app.main:app --reload --port 8001
# API chạy ở http://localhost:8001, xem docs tự động ở http://localhost:8001/docs
```

**Hoặc bằng Docker** (image build sẵn migration + server, xem `docker-entrypoint.sh`):

```bash
cp .env.example .env   # điền như trên
docker compose up --build
# (đổi cổng host qua biến BACKEND_PORT nếu 8001 cũng bận, vd: BACKEND_PORT=8002 docker compose up -d
#  — nhớ sửa API_BASE tương ứng trong frontend/src/api.js)
```

Container hoàn toàn stateless — không có volume nào để mất dữ liệu; DB/vector nằm ở Postgres, file gốc nằm ở Backblaze B2, cả hai đều NGOÀI container.

> Lưu ý: model LLM mặc định là OpenAI `gpt-4o-mini` (`backend/app/llm/openai_client.py`) — cần `OPENAI_API_KEY` trong `.env` (không có free tier, tính phí theo token). Muốn dùng Gemini thay vào đó: để trống `OPENAI_API_KEY`, điền `GEMINI_API_KEY`, `app/llm/client_factory.py` tự chuyển provider mà không cần sửa code (hoặc ép bằng `LLM_PROVIDER=gemini`/`openai`). Model Gemini cấu hình ở `backend/app/llm/gemini_client.py` (hiện là `gemini-3.1-flash-lite`) — Google thường xuyên đổi chính sách free tier, nếu gặp lỗi `429 ResourceExhausted` với `limit: 0` thì model đó có thể đã bị deprecate, kiểm tra tại [trang rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# Mở http://localhost:5173
```

## Sử dụng

1. Vào trang **Tài liệu**, tải lên 1 file PDF hoặc DOCX + nhập tên môn học. Đợi trạng thái chuyển từ "đang xử lý" → "sẵn sàng".
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
| `POST /chat/ask` | Đặt câu hỏi RAG (tuỳ chọn `level`: beginner/advanced — không truyền thì lấy lại `preferred_level` đã lưu trong Learning Profile), tự tạo hội thoại mới nếu chưa có `conversation_id`. Câu hỏi kiểu "nên học gì tiếp theo?" được trả lời trực tiếp từ dữ liệu mastery, không qua RAG. |
| `GET /chat/conversations` | Liệt kê hội thoại theo `user_id`, kèm preview câu hỏi đầu tiên |
| `GET /chat/conversations/{id}` | Lấy toàn bộ tin nhắn của một hội thoại |
| `POST /quiz/generate` | Sinh quiz trắc nghiệm từ 1 tài liệu (`document_id`) hoặc nhiều tài liệu (`document_ids`), tuỳ chọn `difficulty` (cùng cơ chế fallback về Learning Profile như `/chat/ask`) |
| `POST /quiz/submit` | Nộp đáp án 1 câu, trả kết quả + cập nhật mastery |
| `POST /flashcard/generate` | Sinh flashcard (front/back) từ một tài liệu |
| `GET /mastery` | Tổng quan mastery theo chủ đề + số liệu thống kê |
| `GET /study-plan` | Kế hoạch ôn tập theo `days` còn lại, ưu tiên chủ đề yếu/chưa học |
| `GET /profile` | Xem Learning Profile: `preferred_level`, `learning_goal`, và `weak_topics` suy ra từ mastery hiện có |
| `PUT /profile` | Cập nhật thủ công `preferred_level` và/hoặc `learning_goal` |

Xem chi tiết request/response tại `http://localhost:8001/docs` (Swagger UI tự sinh) khi backend đang chạy.

## Chạy test

Phần lớn test là logic thuần (fake LLM/embedder — không cần mạng hay API key thật). Riêng test cho `pgvector_store.py`/`memory_service.py` (cosine similarity, full-text search) và `storage.py` (object storage) cần hạ tầng THẬT — không mock được vì đó là hành vi của chính hạ tầng, không phải code của app:

```bash
# Postgres + pgvector (nếu chưa có từ bước Cài đặt)
docker run -d -p 5433:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=edututor_test pgvector/pgvector:pg16

# MinIO — S3-compatible, thay Backblaze B2 khi chạy test cục bộ (không cần tài khoản B2 thật)
docker run -d -p 9010:9000 -e MINIO_ROOT_USER=testkey -e MINIO_ROOT_PASSWORD=testsecret minio/minio server /data
# Tạo bucket (một lần):
python -c "import boto3; boto3.client('s3', endpoint_url='http://localhost:9010', aws_access_key_id='testkey', aws_secret_access_key='testsecret', region_name='auto').create_bucket(Bucket='edututor-uploads')"

DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/edututor_test \
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/edututor_test \
STORAGE_ENDPOINT_URL=http://localhost:9010 STORAGE_ACCESS_KEY_ID=testkey STORAGE_SECRET_ACCESS_KEY=testsecret STORAGE_BUCKET_NAME=edututor-uploads \
python -m unittest discover -s tests -v
```

CI (`.github/workflows/ci.yml`) dựng đúng hai dịch vụ này tự động trên mọi push/PR — xem file đó để đối chiếu nếu chạy cục bộ không khớp.

## Deploy

Kiến trúc stateless (không SQLite/FAISS/file local nào) cho phép deploy backend lên host **free tier không có đĩa bền vững**. Toàn bộ dịch vụ dưới đây đều có gói miễn phí.

### 1. Neon — Postgres + pgvector

1. Tạo tài khoản tại https://neon.tech, tạo một project mới.
2. Vào **SQL Editor**, chạy `CREATE EXTENSION IF NOT EXISTS vector;`.
3. Copy connection string ở **Connection Details** — dạng `postgresql://user:pass@host/dbname`. Đổi `postgresql://` thành `postgresql+psycopg://` (driver app dùng, xem `app/database.py`) → đây là `DATABASE_URL`.

### 2. Backblaze B2 — lưu file gốc

> Đã cân nhắc Cloudflare R2 nhưng R2 bắt nhập thẻ tín dụng để bật dù chỉ dùng trong hạn mức free — B2 thì không, và vẫn free 10GB.

1. Tạo tài khoản tại https://www.backblaze.com/, vào **Buckets** → **Create a Bucket** (tên tuỳ ý, không nhất thiết là `edututor-uploads`).
2. Vào **App Keys** → **Add a New Application Key** (đây là bước RIÊNG với tạo bucket, không tự có) → giới hạn quyền vào đúng bucket vừa tạo.
3. Ghi lại: **keyID** (= `STORAGE_ACCESS_KEY_ID`), **applicationKey** (= `STORAGE_SECRET_ACCESS_KEY`, chỉ hiện một lần lúc tạo), và endpoint hiện trên trang bucket (dạng `https://s3.<region>.backblazeb2.com`, = `STORAGE_ENDPOINT_URL`).

### 3. Cohere — embedding + rerank

Tạo tài khoản tại https://dashboard.cohere.com, lấy API key ở **API Keys** (trial key dùng được ngay, đủ cho quy mô cá nhân).

### 4. Render — backend

1. Push code lên GitHub (repo này đã có `render.yaml` + `Dockerfile`).
2. Trên Render: **New +** → **Blueprint**, chọn repo → Render đọc `render.yaml` và tạo sẵn service `edututor-backend`.
3. Điền các biến môi trường được đánh dấu secret khi được hỏi (`DATABASE_URL`, `OPENAI_API_KEY` hoặc `GEMINI_API_KEY`, `COHERE_API_KEY`, `STORAGE_ENDPOINT_URL`, `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY`, `STORAGE_BUCKET_NAME`; `FRONTEND_URL` điền sau khi có domain Vercel ở bước 5).
4. Deploy — `docker-entrypoint.sh` tự chạy `alembic upgrade head` rồi mới khởi động server; theo dõi ở tab **Logs** để xác nhận migration chạy thành công. Không có **Blueprint**? Tạo thủ công: **New +** → **Web Service** → **Docker** → trỏ vào repo, `Dockerfile Path` = `./Dockerfile`, rồi tự thêm các biến môi trường ở trên.
5. Ghi lại URL Render cấp (dạng `https://edututor-backend-xxxx.onrender.com`) — dùng ở bước 5 (frontend) và điền ngược lại `FRONTEND_URL` sau khi có domain Vercel.

> Free tier Render "ngủ" sau ~15 phút không có request, request đầu tiên sau đó sẽ chậm (cold start) — chấp nhận được cho một dự án cá nhân.

### 5. Vercel — frontend

```bash
cd frontend
npx vercel --prod
```

Hoặc qua dashboard: **New Project** → import repo → **Root Directory** = `frontend` → thêm biến môi trường `VITE_API_BASE_URL` = URL backend Render (bước 4) + `/api`... thực ra API không có prefix `/api`, dùng đúng gốc URL Render, vd `https://edututor-backend-xxxx.onrender.com`. `vercel.json` đã có sẵn SPA rewrites, không cần cấu hình thêm.

Sau khi có domain Vercel, quay lại Render, cập nhật `FRONTEND_URL` = domain đó rồi **Manual Deploy** lại để CORS nhận đúng origin (xem `app/main.py::compute_allowed_origins`).

### CI/CD

`.github/workflows/ci.yml` chạy test (Postgres+pgvector, MinIO thay Backblaze B2) trên mọi push/PR tới `main`/`master`. Render/Vercel tự deploy khi có push mới lên nhánh đã kết nối — không cần bước CD riêng trong GitHub Actions; muốn CI chặn deploy khi test đỏ, tắt auto-deploy trên Render và thay bằng gọi **Deploy Hook** (Render → service → Settings → Deploy Hook) ở cuối job `backend` trong `ci.yml`.

## Đánh giá chất lượng (Golden Set)

[`eval/golden_set.jsonl`](eval/golden_set.jsonl) là bộ 54 case đánh giá trải trên 8 nhóm (RAG QA, Personalization, Safety, Assessment, Recommendation, Study Planner, Flashcard, Analytics), mỗi case gắn `assertion` và `watched_failure_mode` để chấm tự động. Xem [`eval/report.md`](eval/report.md) để biết kết quả đầy đủ trên cấu hình đang chạy thật (Hybrid + Reranker): điểm mạnh nhất là các nhóm rule-based (Safety, Recommendation, Planner — đều 100%), điểm yếu rõ nhất là Personalization (đo được ~13% ở thời điểm chạy báo cáo này — xem `app/services/learning_profile.py` và `_LEVEL_INSTRUCTIONS` trong `app/llm/rag.py` cho các cải tiến đã thêm sau đó, chưa có lượt đánh giá lại để xác nhận tác động), cùng phân tích lỗi chi tiết và so sánh với cấu hình dense-only.

## Chưa làm / hướng phát triển tiếp

- **Cá nhân hoá theo mục tiêu học tập dài hạn** (vd: "ôn thi trong 2 tuần" tự sinh kế hoạch theo goal) — `GET /study-plan` mới hỗ trợ theo số ngày, chưa gắn với goal/deadline lưu trữ lâu dài.
- **Gợi ý theo prerequisite** (vd: học Transformer thì gợi ý học Attention trước) — cần một đồ thị/quan hệ phụ thuộc giữa các chủ đề, hiện chưa có nguồn dữ liệu này.
- **Theo dõi thời gian học thực tế** cho Learning Analytics — cần instrument sự kiện ở frontend, chưa thu thập.
- **Đăng nhập/đa người dùng thật** — hiện `user_id` cố định `demo-user` ở frontend (`frontend/src/api.js`), và backend tin thẳng `user_id` do client gửi lên mà không xác minh session/token nào (rủi ro bảo mật thật nếu deploy công khai, không chỉ giới hạn kỹ thuật của walking skeleton).
- **Xoá/đổi tên cuộc hội thoại** trong lịch sử hỏi đáp.
- **Việc suy trình độ từ mastery trung bình còn thô** — chỉ một ngưỡng cố định (yếu → beginner, tốt → advanced, còn lại không đoán), chưa tính đến xu hướng tiến bộ theo thời gian hay khác biệt giữa các môn học.
- **Chưa re-run Golden Set để đo tác động thật của các cải tiến cá nhân hóa** (siết prompt, tăng `top_k`, Learning Profile) — điểm Personalization ~13% ở `eval/report.md` là số đo TRƯỚC các thay đổi này, chưa có số liệu thật sau khi cải tiến.
