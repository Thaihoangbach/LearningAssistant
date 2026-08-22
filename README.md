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
| **Hỏi đáp RAG** | Đặt câu hỏi về nội dung tài liệu đã tải; câu trả lời đi kèm trích dẫn nguồn (tên tài liệu + vị trí), tổng hợp/nêu rõ khác biệt khi thông tin đến từ nhiều nguồn. Hiểu được câu hỏi tiếp nối dựa trên vài lượt hội thoại gần nhất (vd: "vậy tại sao *nó* không cần RNN?"), diễn đạt lại đơn giản hơn khi người dùng nói chưa hiểu, và điều chỉnh độ sâu câu trả lời theo trình độ (`level`) — khai báo tường minh hoặc lấy lại từ Learning Profile nếu không truyền. Có bước verifier để đảm bảo không "bịa" câu trả lời khi nội dung không có trong tài liệu, và bước guardrail để chặn prompt injection/jailbreak, yêu cầu làm bài hộ, cùng câu hỏi ngoài phạm vi học tập trước khi trả lời. Lưu lại lịch sử hội thoại, xem lại hoặc tạo cuộc hội thoại mới. |
| **Gợi ý học tiếp theo** | Hỏi kiểu "tôi nên học gì tiếp theo?" sẽ được nhận diện và trả lời ngay từ dữ liệu mastery đã có (chủ đề điểm thấp nhất), không cần gọi LLM. |
| **Quiz tự kiểm tra** | Sinh câu hỏi trắc nghiệm (có thể gắn theo chủ đề, chọn độ khó, gộp nhiều tài liệu thành 1 quiz tổng hợp) từ nội dung tài liệu, mỗi câu đã qua verifier để đảm bảo đáp án đúng và giải thích khớp với tài liệu nguồn. |
| **Flashcard** | Sinh flashcard (mặt trước/mặt sau) từ tài liệu, cùng kỹ thuật generator + verifier với quiz. |
| **Kế hoạch học tập** | Lập lịch ôn tập theo số ngày còn lại tới hạn, ưu tiên chủ đề điểm thấp/chưa học trước — tính lại từ dữ liệu mastery hiện có mỗi lần gọi, tự động phản ánh tiến độ mới nhất. |
| **Mastery theo chủ đề** | Chấm điểm mức độ thành thạo (0–1) theo công thức rule-based có trọng số suy giảm theo thời gian (recency-weighted, half-life 14 ngày) mỗi khi nộp bài quiz. Dashboard tổng quan hiển thị điểm mastery, số tài liệu, số quiz, tỉ lệ đúng. |
| **Hồ sơ học tập (Learning Profile)** | Lưu `preferred_level` (trình độ) dùng chung giữa hỏi đáp và sinh quiz — chỉ cần khai báo `level`/`difficulty` một lần, các lượt sau tự áp dụng lại nếu không truyền tham số mới; truyền tường minh lại thì ghi đè preference. Nếu chưa từng khai báo, hệ thống tự suy trình độ từ điểm mastery trung bình hiện có (mastery yếu → beginner, tốt → advanced). Có `learning_goal` (mục tiêu học tập, dạng text tự do) — được lọc injection ngay khi lưu (`contains_hard_block_pattern`), sau đó đưa vào prompt sinh câu trả lời như bối cảnh tham khảo (không phải chỉ dẫn). `GET /profile` trả cả `weak_topics`/`mastered_topics` suy từ mastery hiện có. |

Chưa làm: gợi ý theo prerequisite (cần đồ thị kiến thức chưa xây dựng), theo dõi thời gian học thực tế, đăng nhập/đa người dùng thật (hiện dùng `user_id` cố định `demo-user` cho walking skeleton).

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

```bash
cd backend
python -m unittest discover -s tests -v
```

Các test hiện có (`test_chunker.py`, `test_parser.py`, `test_rag.py`, `test_quiz_generator.py`, `test_flashcard_generator.py`, `test_mastery.py`, `test_guardrail.py`, `test_recommendation.py`, `test_study_planner.py`, `test_learning_profile.py`) kiểm tra phần logic thuần Python (chunking, RAG orchestration, quiz/flashcard orchestration, công thức mastery, parse DOCX, guardrail, gợi ý học tiếp theo, lập kế hoạch học tập, Learning Profile) bằng fake LLM client — không cần mạng hay API key thật. Phần cần thư viện ngoài/kết nối thật (embedding, FAISS, Gemini API, build frontend) chưa có test tự động, cần tự chạy thử thủ công như hướng dẫn ở mục Sử dụng.

> **Lưu ý khi cập nhật lên phiên bản này:** `models.py` vừa thêm cột mới (`Document.version`, `Document.is_latest`) và bảng mới (`flashcard_sets`, `flashcard_items`). Dự án chưa có công cụ migration (Alembic) — nếu đã có sẵn `backend/data/edututor.db` từ trước, cần xoá file này (hoặc tự thêm cột) để `init_db()` tạo lại schema đúng, nếu không `/documents` và `/chat/ask` sẽ lỗi "no such column". Riêng bảng `learning_profiles` (Learning Profile) là bảng **hoàn toàn mới**, không cần xoá DB cũ — `init_db()` tự thêm bảng còn thiếu vào DB hiện có mà không đụng tới các bảng khác.

## Đánh giá chất lượng (Golden Set)

[`eval/golden_set.jsonl`](eval/golden_set.jsonl) là bộ 54 case đánh giá trải trên 8 nhóm (RAG QA, Personalization, Safety, Assessment, Recommendation, Study Planner, Flashcard, Analytics), mỗi case gắn `assertion` và `watched_failure_mode` để chấm tự động. Xem [`eval/report.md`](eval/report.md) để biết kết quả đầy đủ trên cấu hình đang chạy thật (Hybrid + Reranker): điểm mạnh nhất là các nhóm rule-based (Safety, Recommendation, Planner — đều 100%), điểm yếu rõ nhất là Personalization (đo được ~13% ở thời điểm chạy báo cáo này — xem `app/learning_profile.py` và `_LEVEL_INSTRUCTIONS` trong `app/llm/rag.py` cho các cải tiến đã thêm sau đó, chưa có lượt đánh giá lại để xác nhận tác động), cùng phân tích lỗi chi tiết và so sánh với cấu hình dense-only.

## Chưa làm / hướng phát triển tiếp

- **Cá nhân hoá theo mục tiêu học tập dài hạn** (vd: "ôn thi trong 2 tuần" tự sinh kế hoạch theo goal) — `GET /study-plan` mới hỗ trợ theo số ngày, chưa gắn với goal/deadline lưu trữ lâu dài.
- **Gợi ý theo prerequisite** (vd: học Transformer thì gợi ý học Attention trước) — cần một đồ thị/quan hệ phụ thuộc giữa các chủ đề, hiện chưa có nguồn dữ liệu này.
- **Theo dõi thời gian học thực tế** cho Learning Analytics — cần instrument sự kiện ở frontend, chưa thu thập.
- **Xử lý "một phần căn cứ"** — verifier hiện chỉ CÓ/KHÔNG nhị phân; câu trả lời có bằng chứng một phần bị từ chối toàn bộ thay vì nêu rõ phần nào đã xác minh được.
- **Đăng nhập/đa người dùng thật** — hiện `user_id` cố định `demo-user` ở frontend (`frontend/src/api.js`), chưa có xác thực.
- **Xoá/đổi tên cuộc hội thoại** trong lịch sử hỏi đáp.
- **Việc suy trình độ từ mastery trung bình còn thô** — chỉ một ngưỡng cố định (yếu → beginner, tốt → advanced, còn lại không đoán), chưa tính đến xu hướng tiến bộ theo thời gian hay khác biệt giữa các môn học.
- **Chưa re-run Golden Set để đo tác động thật của các cải tiến cá nhân hóa** (siết prompt, tăng `top_k`, Learning Profile) — điểm Personalization ~13% ở `eval/report.md` là số đo TRƯỚC các thay đổi này, chưa có số liệu thật sau khi cải tiến.
