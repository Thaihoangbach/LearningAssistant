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
| **Quản lý tài liệu** | Tải lên PDF/DOCX theo môn học, xử lý nền (parse → chunk → trích outline chương/mục → embed qua Cohere → lưu vector), theo dõi trạng thái "đang xử lý" / "sẵn sàng" / "lỗi", xoá tài liệu, xem lại outline đã trích. Upload lại cùng tên file + môn học sẽ tạo phiên bản mới (versioning) — hỏi đáp chỉ dùng bản mới nhất, bản cũ vẫn giữ lại. Phát hiện trùng nội dung qua `content_hash` (SHA-256), không chỉ dựa tên file. |
| **Hỏi đáp RAG** | Đặt câu hỏi về nội dung tài liệu đã tải; câu trả lời đi kèm trích dẫn nguồn (tên tài liệu + vị trí), tổng hợp/nêu rõ khác biệt khi thông tin đến từ nhiều nguồn. Hiểu được câu hỏi tiếp nối dựa trên vài lượt hội thoại gần nhất, chủ động hỏi lại khi câu hỏi dùng đại từ không rõ đang nhắc tới gì, và điều chỉnh độ sâu câu trả lời theo trình độ hiệu lực (khai báo tường minh, hoặc lấy từ Learning Profile, hoặc suy từ mastery trung bình — xem mục Cá nhân hoá). Verifier xác minh **theo từng câu** (claim-level) thay vì cả câu trả lời một khối — nếu chỉ một phần câu trả lời có căn cứ, hệ thống trả đúng phần đó kèm cờ `partial: true` thay vì từ chối toàn bộ hoặc giữ nguyên phần chưa xác minh được. Guardrail chặn prompt injection/jailbreak, yêu cầu làm bài hộ, và câu hỏi ngoài phạm vi học tập trước khi trả lời. Lưu lại lịch sử hội thoại, xem lại hoặc tạo cuộc hội thoại mới. |
| **Tóm tắt / So sánh / Áp dụng** | Ba dạng câu hỏi được nhận diện riêng và có cách xử lý khác quy trình hỏi đáp mặc định: **Tóm tắt** một chương/chủ đề lấy TRỌN chunk thuộc chủ đề đó theo đúng thứ tự trong tài liệu (không phải top-k liên quan nhất); **So sánh** 2 khái niệm truy hồi RIÊNG từng vế rồi gộp lại, tránh lệch về phía có nhiều nội dung hơn trong corpus; **Áp dụng** yêu cầu hệ thống tự đưa ví dụ/bài tập mới minh hoạ khái niệm đã học, kèm giải thích. Cả ba đều đi qua chung một bước verifier claim-level như hỏi đáp thường. |
| **Gợi ý học tiếp theo** | Hỏi kiểu "tôi nên học gì tiếp theo?" được nhận diện bằng rule-based (không gọi LLM) và trả lời ngay từ dữ liệu đã có: chủ đề điểm mastery thấp nhất, kèm phát hiện **hiểu sai lặp lại** (misconception) — khi người học chọn sai CÙNG một đáp án ở CÙNG một chủ đề từ 2 lần trở lên, hệ thống nêu rõ cụ thể đang nhầm gì, không chỉ nói chung chung "hay sai". |
| **Quiz tự kiểm tra** | Sinh câu hỏi trắc nghiệm (có thể gắn theo chủ đề, chọn độ khó — hoặc để hệ thống tự chọn theo trình độ hiệu lực, gộp nhiều tài liệu thành 1 quiz tổng hợp) từ nội dung tài liệu, mỗi câu đã qua verifier để đảm bảo đáp án đúng và giải thích khớp với tài liệu nguồn, được gắn nhãn loại nội dung (khái niệm/định nghĩa/công thức/sự kiện/quy trình). |
| **Flashcard + ôn tập ngắt quãng (spaced repetition)** | Sinh flashcard (mặt trước/mặt sau) từ tài liệu hoặc lưu trực tiếp từ một câu trả lời hỏi đáp, cùng kỹ thuật generator + verifier với quiz. Mỗi thẻ có bảng "board" theo trạng thái đến hạn/đang học/đã thuộc; đánh giá theo 4 mức (again/hard/good/easy) sẽ tính lại ngày ôn tiếp theo bằng thuật toán SM-2 rút gọn (phỏng theo Anki), và điểm ghi nhớ (retention) được tính lại từ toàn bộ lịch sử đánh giá mỗi lần đọc. |
| **Kế hoạch học tập** | Lập lịch ôn tập theo ngày thi đã khai báo cho từng môn học (`/courses`), ưu tiên chủ đề yếu trước — mỗi chủ đề trong kế hoạch kèm hành động đề xuất cụ thể (nên làm quiz, ôn flashcard, hay học lại từ đầu) và lý do, suy ra từ việc so sánh điểm hiểu bài (mastery) với điểm ghi nhớ (retention) của đúng chủ đề đó. Có thể đánh dấu thủ công một chủ đề "đã ôn hôm nay". |
| **Mastery theo chủ đề** | Chấm điểm mức độ thành thạo (0–1) theo công thức rule-based có trọng số suy giảm theo thời gian (recency-weighted, half-life 14 ngày) và theo độ khó câu hỏi (đúng câu khó/sai câu dễ được tính là bằng chứng mạnh hơn) mỗi khi nộp bài quiz. Điểm còn tiếp tục suy giảm nhẹ theo thời gian không luyện tập mỗi khi đọc lại (half-life 30 ngày, không ghi ngược vào DB). Dashboard tổng quan hiển thị điểm mastery, số tài liệu, số quiz, tỉ lệ đúng, danh sách câu đã trả lời sai gần đây. |
| **Cá nhân hoá (3 lớp) + Hồ sơ học tập** | `app/services/learner_context.py` gộp 3 lớp cá nhân hoá thành một lời gọi duy nhất trước khi đưa vào prompt hoặc chọn độ khó: (1) **Hồ sơ tĩnh tự khai** — `preferred_level`, `learning_goal` qua `PUT /profile`, được lọc injection ngay khi lưu; (2) **Điểm tổng hợp theo thời gian** — mastery trung bình đã decay; (3) **Ký ức theo sự kiện cụ thể** (`MemoryEvent`) — log các sự kiện học tập (hỏi bị từ chối, chọn sai quiz, quên flashcard...) có embedding riêng, truy hồi theo ngữ nghĩa xuyên suốt mọi cuộc hội thoại (khác với lịch sử chat thông thường, vốn chỉ có tác dụng trong 1 cuộc hội thoại). Trình độ hiệu lực ưu tiên: khai báo tường minh > đã lưu trong hồ sơ > suy từ mastery trung bình (yếu → beginner, tốt → advanced). `GET /profile` trả cả trình độ hiệu lực và nguồn suy ra nó ("declared"/"inferred"). |
| **Môn học & ngày thi** | Gom các tên môn học đã dùng khi tải tài liệu để gợi ý lại lúc upload; đặt/xoá ngày thi cho từng môn (`/courses/{course_name}/exam-date`) làm đầu vào cho kế hoạch học tập. |

Chưa làm: gợi ý theo prerequisite (cần đồ thị kiến thức chưa xây dựng), theo dõi thời gian học thực tế, đăng nhập/đa người dùng thật (hiện dùng `user_id` cố định `demo-user` cho walking skeleton), tự động thay đổi hành vi sinh quiz/flashcard theo `generation_mode` (hiện mới lưu để truy vết, chưa đổi cách sinh).

## Kiến trúc & công nghệ

**Backend:** Python, FastAPI, SQLAlchemy + Alembic, PostgreSQL + pgvector (dữ liệu quan hệ VÀ vector embedding trong cùng một DB — xem `app/vectorstore/pgvector_store.py`), Cohere API (embedding + rerank, `app/ingestion/embedder.py`/`app/retrieval/reranker.py`), Backblaze B2 (lưu file gốc đã tải lên, S3-compatible, `app/storage.py`), OpenAI API (LLM mặc định — `app/llm/client_factory.py` tự rơi về Google Gemini nếu chỉ có `GEMINI_API_KEY`). Backend hoàn toàn **stateless** — không có gì cần đĩa bền vững, deploy được lên host free tier không có volume (Render).

**Frontend:** React 18 + Vite, React Router, Tailwind CSS, lucide-react.

Pipeline RAG là generator + verifier hai bước cố định (không phải multi-agent tự quyết định hành động): generator sinh câu trả lời/câu hỏi dựa trên chunk truy hồi được, verifier kiểm tra lại tính đúng đắn/căn cứ **theo từng câu** (claim-level) trước khi trả về — nếu chỉ một phần câu trả lời có căn cứ, hệ thống trả đúng phần đó kèm cờ `partial: true`. Trước bước generator, câu hỏi hỏi đáp còn đi qua guardrail 3 tầng: 2 tầng đầu rule-based chặn ngay yêu cầu làm bài hộ và các pattern injection/jailbreak rõ ràng (không tốn quota), câu mơ hồ hơn mới gọi thêm 1 lượt LLM làm gatekeeper phân loại an toàn/không an toàn.

Lớp `app/services/` tập trung logic nghiệp vụ thuần Python (không phụ thuộc FastAPI, dùng lại được giữa nhiều router): phân loại ý định câu hỏi (rule-based `capability_detector.py` cho các yêu cầu không cần sinh nội dung; nhận diện Tóm tắt/So sánh/Áp dụng trong `chat.py`), gộp cá nhân hoá (`learner_context.py`), và các module điểm số/lịch ôn (`mastery.py`, `retention.py`, `spaced_repetition.py`, `misconception.py`, `learning_policy.py`). Xem sơ đồ 2 và 7 ở [`docs/architecture-diagrams.md`](docs/architecture-diagrams.md) để biết chi tiết luồng dữ liệu giữa các module này.

## Cấu trúc dự án

```
backend/
  alembic/                       # Migration schema (Postgres) — 7 revision, chạy qua alembic upgrade head
  app/
    models.py, database.py        # Postgres + pgvector qua SQLAlchemy — 17 bảng, xem docs/architecture-diagrams.md 9a/9b
    storage.py                     # File gốc trên Backblaze B2 (S3-compatible)
    ingestion/
      parser.py                   # PDF/DOCX -> sections
      chunker.py                  # sections -> chunks (theo câu, có bridge chunk nối 2 mục liền kề)
      embedder.py                 # chunks -> vector (Cohere Embed API, embed-multilingual-v3.0)
      outline.py                  # trích outline chương/mục lúc nạp tài liệu (heading style DOCX, heuristic số mục cho PDF)
      pipeline.py                 # nối parser -> chunker -> embedder -> vector store
    vectorstore/
      pgvector_store.py           # Hybrid search (pgvector cosine + Postgres full-text) theo user
      hybrid.py                   # Reciprocal Rank Fusion gộp 2 nhánh dense/keyword
    retrieval/
      pipeline.py                 # retrieve_chunks — 2 pha strict/wide, gọi reranker
      reranker.py                 # Rerank kết quả hybrid (Cohere Rerank API)
      query_context.py            # bổ sung từ khoá ngữ cảnh hội thoại + phát hiện đại từ không rõ tiền ngữ
      keywords.py                 # trích từ khoá nội dung, cắt phần "đóng vai .../act as..." khỏi query truy hồi
    llm/
      guardrail.py                # chặn prompt injection/jailbreak + yêu cầu làm bài hộ + câu hỏi ngoài phạm vi
      rag.py                      # hỏi đáp — generator + verifier theo claim, output_style, cờ partial
      quiz_generator.py           # sinh quiz — generator + verifier từng câu
      flashcard_generator.py      # sinh flashcard — generator + verifier từng thẻ (tái dùng pattern quiz)
      recommendation.py           # gợi ý học tiếp theo — rule-based, đọc lại MasteryScore + misconception
      client_factory.py           # chọn LLM client thật — OpenAI (mặc định) hoặc Gemini theo key/LLM_PROVIDER
      openai_client.py            # client gọi OpenAI API thật
      gemini_client.py            # client gọi Gemini API thật (fallback)
    services/                     # logic nghiệp vụ thuần Python, dùng lại giữa nhiều router
      qa_pipeline.py               # 2 pha strict/wide + near-miss + gợi ý chủ đề khi từ chối
      capability_detector.py       # rule-based: study_plan / recommendation / flashcard_due (không cần sinh nội dung)
      summarize.py, compare.py, apply.py   # 3 dạng câu hỏi có contract output riêng
      structural_retrieval.py      # lấy trọn 1 chủ đề theo section_index (dùng cho Tóm tắt)
      context_assembly.py          # lọc document_ids theo quyền + trạng thái + course_name
      citation.py                  # câu hỗ trợ trích dẫn, resolve_topic theo overlap từ khoá
      learner_context.py           # gộp 3 lớp cá nhân hoá (hồ sơ tĩnh, mastery, ký ức sự kiện) thành 1 lời gọi
      learning_profile.py          # logic thuần: level nào áp dụng, có nên ghi đè preference không
      learning_state.py, learning_policy.py   # gộp comprehension+retention theo topic → đề xuất quiz/flashcard/learn
      mastery.py                   # công thức tính mastery rule-based (recency + difficulty weighted)
      retention.py                 # điểm ghi nhớ từ lịch sử flashcard, recency-weighted
      spaced_repetition.py         # lịch ôn tiếp theo — SM-2 rút gọn (4 mức, giống Anki)
      misconception.py             # phát hiện đáp án sai lặp lại theo (topic, đáp án đã chọn)
      study_planner.py             # lập kế hoạch học tập theo ngày thi từng môn + learning_policy
      flashcard.py                 # board due/learning/mastered
      document_cleanup.py          # dọn dữ liệu liên quan khi xoá tài liệu
      generation_mode.py           # nhãn lineage learn/review/exam/weak_topics cho Quiz/FlashcardSet
    memory/                        # ký ức dài hạn theo sự kiện (Lớp 3 cá nhân hoá, KHÁC lịch sử hội thoại)
      service.py                   # record_event / recall_events (pgvector cosine trên MemoryEvent)
      scoring.py                   # điểm chọn sự kiện = 0.35 recency + 0.45 relevance + 0.20 importance
    routers/
      documents.py                 # upload (có versioning + dedup content_hash), list, xoá tài liệu
      chat.py                      # hỏi đáp RAG + Tóm tắt/So sánh/Áp dụng + gợi ý học tiếp theo + lịch sử hội thoại
      courses.py                   # liệt kê tên môn học đã dùng, đặt/xoá ngày thi theo môn
      quiz.py                      # sinh quiz (đa tài liệu, theo độ khó), nộp bài, cập nhật mastery
      flashcard.py                 # sinh flashcard, lưu từ câu trả lời, board, lịch sử, review SM-2 rút gọn
      mastery.py                   # đọc dữ liệu mastery + danh sách câu sai cho dashboard
      study_plan.py                 # trả kế hoạch học tập theo ngày thi từng môn, đánh dấu đã ôn
      profile.py                   # xem/cập nhật/xoá Learning Profile (preferred_level, learning_goal)
    main.py
tests/                            # unittest, TÁCH KHỎI backend/ — xem mục Chạy test
frontend/
  src/
    api.js                        # gọi API backend
    App.jsx                       # định tuyến React Router — 7 trang dưới đây
    pages/
      DashboardPage.jsx           # tổng quan mastery + tài liệu gần đây
      UploadPage.jsx               # quản lý tài liệu + xem outline đã trích
      ChatPage.jsx                 # hỏi đáp + sidebar lịch sử hội thoại + lưu câu trả lời thành flashcard
      QuizPage.jsx                 # sinh quiz, làm bài, xem đáp án/giải thích
      FlashcardsPage.jsx           # board due/learning/mastered, đánh giá SM-2 rút gọn
      StudyPlanPage.jsx            # lịch ôn tập theo lưới ngày, quản lý ngày thi theo môn
      ProfilePage.jsx              # trình độ khai báo vs suy ra, mục tiêu học tập
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
| `POST /documents` | Tải lên tài liệu (multipart), xử lý nền. Upload lại cùng tên file + môn học sẽ tạo phiên bản mới; trùng nội dung được phát hiện qua `content_hash`. |
| `GET /documents` | Liệt kê tài liệu theo `user_id` (kèm `version`, `is_latest`) |
| `DELETE /documents/{id}` | Xoá tài liệu + toàn bộ chunk/outline liên quan, cùng 1 transaction |
| `GET /documents/{id}/outline` | Xem outline chương/mục đã trích ở lúc nạp tài liệu |
| `POST /chat/ask` | Đặt câu hỏi RAG, hoặc câu hỏi Tóm tắt/So sánh/Áp dụng (tự nhận diện theo nội dung câu hỏi), hoặc câu hỏi kiểu "nên học gì tiếp theo?"/kế hoạch ôn tập/thẻ nào đến hạn (trả lời trực tiếp từ dữ liệu đã có, không qua RAG). Tuỳ chọn `level` (beginner/advanced — không truyền thì lấy trình độ hiệu lực từ Learning Profile/mastery), tự tạo hội thoại mới nếu chưa có `conversation_id`. Response gồm `is_grounded`, `partial` (chỉ đúng một phần câu trả lời có căn cứ), `sources`, `search_report` khi từ chối. |
| `GET /chat/conversations` | Liệt kê hội thoại theo `user_id`, kèm preview câu hỏi đầu tiên |
| `GET /chat/conversations/{id}` | Lấy toàn bộ tin nhắn của một hội thoại |
| `GET /courses` | Liệt kê tên môn học đã dùng khi tải tài liệu, kèm ngày thi nếu đã đặt |
| `PUT /courses/{course_name}/exam-date` | Đặt/cập nhật ngày thi cho một môn học |
| `DELETE /courses/{course_name}/exam-date` | Xoá ngày thi đã đặt cho một môn học |
| `POST /quiz/generate` | Sinh quiz trắc nghiệm từ 1 tài liệu (`document_id`) hoặc nhiều tài liệu (`document_ids`), tuỳ chọn `difficulty`/`generation_mode` (cùng cơ chế fallback trình độ hiệu lực như `/chat/ask`) |
| `POST /quiz/submit` | Nộp đáp án 1 câu (`selected_answer`), trả kết quả + cập nhật mastery |
| `POST /flashcard/generate` | Sinh flashcard (front/back) từ một tài liệu, tuỳ chọn `topic_name`/`generation_mode` |
| `POST /flashcard/save` | Lưu trực tiếp một câu trả lời hỏi đáp thành flashcard (không cần tài liệu) |
| `GET /flashcard/due` | Danh sách thẻ đến hạn ôn |
| `GET /flashcard/board` | Bảng thẻ theo trạng thái đến hạn/đang học/đã thuộc |
| `GET /flashcard/mistakes` | Danh sách thẻ lần đánh giá gần nhất là "again" |
| `GET /flashcard/{id}/history` | Lịch sử đánh giá của một thẻ |
| `POST /flashcard/review` | Đánh giá một thẻ (again/hard/good/easy), tính lại lịch ôn tiếp theo (SM-2 rút gọn) |
| `GET /mastery` | Tổng quan mastery theo chủ đề + số liệu thống kê |
| `GET /mastery/mistakes` | Danh sách câu quiz đã trả lời sai gần đây |
| `GET /study-plan` | Kế hoạch ôn tập theo ngày thi đã đặt cho các môn (`course_names`), mỗi chủ đề kèm hành động đề xuất (quiz/flashcard/learn) và lý do |
| `POST /study-plan/review` | Đánh dấu thủ công một chủ đề "đã ôn hôm nay" |
| `GET /profile` | Xem Learning Profile: `preferred_level`, `learning_goal`, `effective_level` và nguồn suy ra nó |
| `PUT /profile` | Cập nhật thủ công `preferred_level` và/hoặc `learning_goal` |
| `DELETE /profile` | Xoá Learning Profile (không ảnh hưởng mastery/lịch sử) |

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

[`eval/golden_set/data/golden_set.jsonl`](eval/golden_set/data/golden_set.jsonl) là bộ case Q&A + hành vi, chạy thật trên backend local để đánh giá EduTutor — xem [`eval/README.md`](eval/README.md) cho cấu trúc đầy đủ và cách chạy lại. Kết quả, số liệu, và phân tích nguyên nhân gốc luôn thay đổi theo lần chạy gần nhất — xem trực tiếp [`eval/reports/`](eval/reports/) và [`eval/golden_set/changelog/CHANGELOG.md`](eval/golden_set/changelog/CHANGELOG.md) thay vì con số trong tài liệu này.

## Chưa làm / hướng phát triển tiếp

- **`generation_mode` (learn/review/exam/weak_topics) hiện chỉ để truy vết** — lưu trên `Quiz`/`FlashcardSet` nhưng chưa thực sự đổi cách sinh câu hỏi/thẻ theo từng mode.
- **`MemoryEvent.last_accessed_at`/`access_count` hiện chỉ quan sát** — được cập nhật mỗi lần một sự kiện được truy hồi, nhưng chưa đưa vào công thức chọn sự kiện (`memory/scoring.py`).
- **Cá nhân hoá theo mục tiêu học tập dài hạn kết hợp deadline** — `learning_goal` (Learning Profile) và ngày thi theo môn (`/courses`) hiện là 2 nguồn tách biệt, chưa gộp thành một kế hoạch tự sinh theo goal cụ thể kiểu "ôn thi trong 2 tuần, ưu tiên phần X".
- **Gợi ý theo prerequisite** (vd: học Transformer thì gợi ý học Attention trước) — cần một đồ thị/quan hệ phụ thuộc giữa các chủ đề, hiện chưa có nguồn dữ liệu này.
- **Theo dõi thời gian học thực tế** cho Learning Analytics — cần instrument sự kiện ở frontend, chưa thu thập.
- **Đăng nhập/đa người dùng thật** — hiện `user_id` cố định `demo-user` ở frontend (`frontend/src/api.js`), và backend tin thẳng `user_id` do client gửi lên mà không xác minh session/token nào (rủi ro bảo mật thật nếu deploy công khai, không chỉ giới hạn kỹ thuật của walking skeleton).
- **Xoá/đổi tên cuộc hội thoại** trong lịch sử hỏi đáp.
- **Việc suy trình độ từ mastery trung bình còn thô** — chỉ một ngưỡng cố định (yếu → beginner, tốt → advanced, còn lại không đoán), chưa tính đến xu hướng tiến bộ theo thời gian hay khác biệt giữa các môn học.

Số liệu đánh giá chất lượng (pass rate, độ chính xác trích dẫn, các nhóm case còn fail...) đổi theo từng lần chạy Golden Set — xem [`eval/reports/`](eval/reports/) và [`eval/golden_set/changelog/CHANGELOG.md`](eval/golden_set/changelog/CHANGELOG.md) để có số liệu mới nhất, không lấy số liệu từ tài liệu này.
