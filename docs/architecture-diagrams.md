# Architecture Diagrams - EduTutor

**Sản phẩm:** Trợ lý học tập cá nhân hoá dùng LLM + RAG (xem [`PRD.md`](./PRD.md))

Các sơ đồ dưới đây vẽ lại kiến trúc thật đang chạy, lấy trực tiếp từ code trong `backend/app/` - không phải kiến trúc dự kiến ban đầu. Tên biến môi trường, tên bảng, tên hàm trong ghi chú đều khớp với code hiện tại.

**3 nguyên tắc chi phối mọi sơ đồ dưới đây:**

1. Generator + Verifier là một pipeline 2 bước cố định, không phải agent tự quyết định hành động tiếp theo. Verifier là một lượt gọi LLM riêng, không nhận lịch sử hội thoại, chỉ chấp nhận câu trả lời có căn cứ trực tiếp trong đoạn trích hiện tại - đây là cơ chế chặn bịa duy nhất, không có bước con người duyệt tay từng câu trả lời.
2. Quyền truy cập là ranh giới vật lý, không phải bộ lọc sau khi tìm kiếm. Mỗi `user_id` có 1 FAISS index riêng trên đĩa (`{user_id}.faiss` + `{user_id}.meta.pkl`), không có index chung để lọc lẫn nhau.
3. Guardrail rẻ chạy trước, LLM đắt chạy sau. Câu hỏi được lọc qua 3 tầng: 2 tầng đầu rule-based miễn phí (chặn ngay yêu cầu làm bài hộ và pattern injection/jailbreak rõ ràng), chỉ tầng 3 (câu hỏi mơ hồ) mới tốn 1 lượt gọi Gemini làm gatekeeper - đỡ tốn quota free tier.

---

## Công nghệ dùng cho từng phần

| Thành phần | Công nghệ | Ghi chú |
| --- | --- | --- |
| Frontend | React 18 + Vite + React Router + Tailwind CSS | chạy dev server, chưa deploy production trong scope này |
| Backend API | FastAPI (Python) + Uvicorn | đồng bộ: upload, hỏi đáp, sinh quiz/flashcard, mastery, kế hoạch học tập |
| Xử lý nền | FastAPI `BackgroundTasks`, chạy trong cùng process, không có queue/worker riêng | đủ dùng cho quy mô 1 người dùng cục bộ hiện tại |
| Database | SQLite qua SQLAlchemy | file `edututor.db`, chưa có Alembic nên đổi schema phải xoá DB cũ tạo lại |
| Vector store | FAISS `IndexFlatIP` local, 1 index riêng cho mỗi user | inner product trên vector đã L2-normalize = cosine similarity |
| Full-text/lexical search | BM25 (`rank_bm25`), build lại từ đầu mỗi lần gọi `hybrid_search()` | chấp nhận được vì mỗi user có corpus nhỏ; tokenizer chỉ tách `\w+` + lowercase, chưa word-segmentation tiếng Việt thật |
| Fusion | Reciprocal Rank Fusion (k=60) | không cần chuẩn hoá thang điểm giữa cosine và BM25 |
| Embedding | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`, chạy local | miễn phí, không giới hạn, để dành quota Gemini cho generator/verifier |
| Rerank | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, chạy local | chấm điểm liên quan trực tiếp (query, chunk); điểm chuẩn hoá qua sigmoid về (0,1) |
| LLM | Google Gemini API (`gemini-3.1-flash-lite`, free tier) | có retry backoff khi gặp lỗi 429 |
| File storage | đĩa cục bộ (`backend/data/uploads`) | không dùng object storage ngoài |

---

## Mục lục

| # | Sơ đồ | Nội dung chính | Loại |
| --- | --- | --- | --- |
| 1 | Bối cảnh hệ thống | ai dùng, tài liệu từ đâu, dịch vụ AI nào được gọi | flowchart |
| 2 | Kiến trúc thành phần | trách nhiệm và công nghệ từng phần, 2 nhánh nạp tài liệu và hỏi đáp | flowchart |
| 3 | Luồng nạp tài liệu | từ upload tới sẵn sàng truy hồi, xử lý nền không chặn request | flowchart |
| 4 | Sequence nạp tài liệu | cơ chế polling 2 giây giữa frontend và API | sequence |
| 5 | Agent/pipeline hỏi đáp | guardrail, phân loại ý định, generator + verifier | flowchart |
| 6 | Hybrid retrieval | lọc theo user trước, 2 nhánh truy hồi song song, RRF, rerank | flowchart |
| 7 | Sinh quiz/flashcard + mastery | generator sinh hàng loạt, verify từng item, cập nhật mastery | flowchart |
| 8a | Bản đồ dữ liệu | 11 bảng gom thành 3 cụm | flowchart |
| 8b | Schema chi tiết | trường, kiểu dữ liệu, khoá | ER |
| 9 | Vòng đời tài liệu | trạng thái nghiệp vụ, versioning | state |
| 10 | Triển khai | cái gì chạy ở đâu | flowchart |

---

## 1. Bối cảnh hệ thống

Người dùng tải tài liệu học tập của mình vào hệ thống. Hệ thống gọi các dịch vụ AI ngoài (Gemini để sinh nội dung, model local để embedding/rerank) nhưng không tự tìm Internet để trả lời.

```mermaid
flowchart TB
    subgraph nguoidung["Người dùng"]
        HV["Người học<br/>Tải tài liệu - hỏi đáp - làm quiz/flashcard<br/>xem mastery và kế hoạch ôn tập"]
    end

    subgraph hethong["EduTutor"]
        APP["Backend FastAPI<br/>RAG, Quiz/Flashcard generator, Mastery, Study planner"]
    end

    subgraph corpus["Tài liệu"]
        DOC["Tài liệu học tập cá nhân<br/>PDF, DOCX do người dùng tự tải lên<br/>Slide, giáo trình, ghi chú"]
    end

    subgraph ngoai["Dịch vụ AI ngoài / local"]
        LLM["Gemini API<br/>generator, verifier, guardrail gatekeeper"]
        EMB["sentence-transformers<br/>embedding, chạy local"]
        RERANK["Cross-encoder rerank<br/>chạy local"]
    end

    HV -->|"Upload PDF/DOCX"| APP
    APP -->|"Trạng thái xử lý, poll 2s"| HV

    HV -->|"Câu hỏi tự nhiên, hoặc yêu cầu sinh quiz/flashcard"| APP
    APP -->|"Câu trả lời kèm trích dẫn, hoặc quiz/flashcard đã verify"| HV

    HV -->|"Xem dashboard, gợi ý, kế hoạch ôn tập"| APP

    DOC -.->|"Tự tải lên, không có ai duyệt lại"| APP

    APP -->|"Prompt sinh câu trả lời/quiz/flashcard, prompt verify"| LLM
    LLM -->|"Nội dung sinh ra + verdict CÓ/KHÔNG"| APP

    APP -->|"Text chunk và text câu hỏi"| EMB
    EMB -->|"Vector đã L2-normalize"| APP
    APP -->|"Câu hỏi + danh sách ứng viên"| RERANK
    RERANK -->|"Điểm liên quan (0,1) sau sigmoid"| APP
```

Không có lớp "văn bản tham chiếu bên ngoài" nào - hệ thống cố tình không tìm Internet trực tiếp, để câu trả lời luôn bám vào đúng tài liệu người học đã tải lên.

---

## 2. Kiến trúc thành phần

Không có worker process riêng - xử lý tài liệu chạy nền trong cùng process FastAPI qua `BackgroundTasks`.

```mermaid
flowchart TB
    subgraph giaodien["Giao diện - React 18 + Vite"]
        UIUP["UploadPage - quản lý tài liệu, poll trạng thái 2 giây"]
        UICHAT["ChatPage - hỏi đáp + sidebar lịch sử hội thoại"]
        UIQUIZ["QuizPage - làm quiz, xem đáp án/giải thích"]
        UIDASH["DashboardPage - mastery, tài liệu gần đây"]
    end

    subgraph api["API - FastAPI + Uvicorn"]
        DOCSVC["documents.py<br/>Nhận file, versioning, đẩy BackgroundTask, xoá tài liệu"]
        CHATSVC["chat.py<br/>Guardrail + retrieval + RAG + gợi ý học tiếp theo + lịch sử"]
        QUIZSVC["quiz.py<br/>Sinh quiz đa tài liệu, chấm bài, cập nhật mastery"]
        FCSVC["flashcard.py<br/>Sinh flashcard từ tài liệu"]
        MASTERYSVC["mastery.py (router)<br/>Đọc dashboard mastery"]
        PLANSVC["study_plan.py<br/>Tính kế hoạch ôn tập theo số ngày còn lại"]
    end

    subgraph nen["Xử lý nền - trong cùng process API"]
        BGTASK["_run_processing_job - FastAPI BackgroundTasks<br/>Parse, Chunk, Embed, Index"]
    end

    subgraph logic["Logic thuần Python - test được không cần FastAPI"]
        RAGLOGIC["app/llm/rag.py<br/>generator + verifier"]
        GUARD["app/llm/guardrail.py<br/>3 tầng chặn"]
        QUIZLOGIC["app/llm/quiz_generator.py, flashcard_generator.py"]
        MASTERYLOGIC["app/mastery.py<br/>recency-weighted formula"]
        PLANLOGIC["app/study_planner.py<br/>round-robin theo ưu tiên"]
        RETR["app/retrieval/pipeline.py<br/>hybrid search + rerank"]
    end

    subgraph luutru["Lưu trữ"]
        SQLITE[("SQLite<br/>Document, Conversation, Message<br/>Quiz, Attempt, MasteryScore, ...")]
        FAISS[("FAISS index riêng theo user<br/>.faiss + .meta.pkl trên đĩa")]
        FILES[("Đĩa cục bộ<br/>backend/data/uploads")]
    end

    subgraph ngoai["Dịch vụ AI"]
        GEMINI["Gemini API"]
        EMBLOCAL["sentence-transformers (local)"]
        RRLOCAL["cross-encoder rerank (local)"]
    end

    UIUP -->|"Nạp 1: POST file"| DOCSVC
    DOCSVC -->|"Nạp 2: Ghi Document status=đang xử lý"| SQLITE
    DOCSVC -->|"Nạp 3: Lưu file gốc"| FILES
    DOCSVC -->|"Nạp 4: add_task ngay trong response"| BGTASK
    DOCSVC -->|"Nạp 5: trả document_id ngay"| UIUP
    UIUP -->|"Nạp 6: GET /documents mỗi 2 giây"| DOCSVC
    DOCSVC -->|"status hiện tại"| UIUP

    BGTASK -->|"Đọc file gốc"| FILES
    BGTASK -->|"Ghi Section/Chunk qua vectorstore, cập nhật status"| SQLITE
    BGTASK -->|"Embedding cho chunk"| EMBLOCAL
    BGTASK -->|"Ghi vector"| FAISS

    UICHAT -->|"Hỏi 1: câu hỏi + user_id"| CHATSVC
    CHATSVC -->|"Hỏi 2"| GUARD
    GUARD -->|"Gatekeeper, chỉ khi mơ hồ"| GEMINI
    CHATSVC -->|"Hỏi 3: lọc document_ids theo quyền + trạng thái"| RETR
    RETR -->|"Hỏi 4"| FAISS
    RETR -->|"Hỏi 5: embedding câu hỏi"| EMBLOCAL
    RETR -->|"Hỏi 6: rerank top ứng viên"| RRLOCAL
    RETR -->|"Hỏi 7: top-k đã rerank"| CHATSVC
    CHATSVC -->|"Hỏi 8"| RAGLOGIC
    RAGLOGIC -->|"generator + verifier"| GEMINI
    CHATSVC -->|"Hỏi 9: lưu Message + trả lời"| SQLITE
    CHATSVC -->|"Câu trả lời + trích dẫn"| UICHAT

    UIQUIZ -->|"Sinh quiz / nộp bài"| QUIZSVC
    QUIZSVC -->|"Truy hồi theo từng tài liệu"| FAISS
    QUIZSVC -->|"generator + verify từng câu"| QUIZLOGIC
    QUIZLOGIC -->|"gọi LLM"| GEMINI
    QUIZSVC -->|"Ghi Quiz/QuizItem/Attempt, cập nhật MasteryScore"| SQLITE

    FCSVC -->|"Cùng pattern với Quiz"| QUIZLOGIC
    MASTERYSVC -->|"Đọc MasteryScore đã cache"| SQLITE
    PLANSVC -->|"Đọc Topic/MasteryScore, tính lại mỗi lần gọi"| PLANLOGIC
    PLANLOGIC --> SQLITE

    UIDASH --> MASTERYSVC
```

---

## 3. Luồng nạp tài liệu

Không có hàng chờ duyệt của con người trước khi tài liệu vào truy hồi - tài liệu được dùng ngay khi xử lý xong, vì đây là tài liệu người dùng tự tải lên cho chính mình chứ không phải kho tri thức chung cần kiểm soát nguồn.

```mermaid
flowchart TB
    START(["Người học chọn file PDF/DOCX + tên môn học, bấm Tải lên"])

    subgraph dongbo["Giai đoạn 1 - Đồng bộ, FastAPI trả về ngay"]
        A1{"Đúng định dạng và dưới 30MB?"}
        REJECT(["Từ chối ngay, kèm lý do cụ thể"])
        A2["Lưu file gốc xuống đĩa"]
        A3{"Có bản is_latest=True cùng tên file + môn học?"}
        A4["Đánh dấu bản cũ is_latest=False, version = bản cũ + 1"]
        A5["Ghi Document mới, status = đang xử lý, version, is_latest=True"]
        A6["add_task đẩy _run_processing_job vào BackgroundTasks"]
        A7["Trả document_id + status ngay"]
    end

    subgraph nen["Giai đoạn 2 - Chạy nền, cùng process, không chặn request khác"]
        B1["Parser: PDF theo trang, DOCX theo nhóm 10 đoạn văn"]
        B2{"Trích được text?"}
        B2FAIL["Ném lỗi: không có nội dung text trích xuất được"]
        B3["Chunker cắt theo max_chars=800, overlap=100"]
        B4["Embed toàn bộ chunk, sentence-transformers local"]
        B5["Ghi IndexedChunk vào FAISS index riêng của user"]
        B6["status = sẵn sàng"]
        B7["status = lỗi, ghi error_reason = str(exception)"]
    end

    READY(["Tài liệu sẵn sàng cho hỏi đáp F2, sinh quiz F4, flashcard F5"])

    START --> A1
    A1 -->|"Không"| REJECT
    A1 -->|"Có"| A2
    A2 --> A3
    A3 -->|"Có"| A4
    A3 -->|"Không"| A5
    A4 --> A5
    A5 --> A6
    A6 --> A7
    A6 -.->|"chạy song song, không chờ"| B1
    B1 --> B2
    B2 -->|"Không"| B2FAIL
    B2FAIL --> B7
    B2 -->|"Có"| B3
    B3 --> B4
    B4 --> B5
    B5 --> B6
    B6 --> READY
```

Metadata gắn vào mỗi chunk khi index (bước B5): `document_id` và tên tài liệu, `position_ref` (Trang n hoặc Mục n), `chunk_id` riêng. Không có khái niệm "trạng thái duyệt nội dung" ở cấp chunk hay tài liệu - cơ chế đảm bảo không bịa nằm ở verifier LLM khi trả lời (sơ đồ 5), không nằm ở việc kiểm soát ai được đưa tài liệu vào.

Chunk hiện đang cắt theo kích thước cố định (800 ký tự, overlap 100), không phải semantic chunking. Đây là baseline đơn giản, `eval/report.md` mục 3 có ghi lại đây là chỗ có thể cải thiện sau này.

---

## 4. Sequence - nạp tài liệu và theo dõi trạng thái

Không có bảng job với phần trăm tiến độ - chỉ có `Document.status` (đang xử lý / sẵn sàng / lỗi), frontend tự poll lại bằng `setInterval` 2 giây (`UploadPage.jsx`).

```mermaid
sequenceDiagram
    autonumber
    actor HV as Người học
    participant FE as UploadPage (React)
    participant API as documents.py (FastAPI)
    participant DB as SQLite
    participant BG as _run_processing_job (BackgroundTasks)
    participant EMB as sentence-transformers (local)
    participant VEC as FAISS (local)

    HV->>FE: Chọn file, nhập tên môn học, bấm Tải lên
    FE->>API: POST /documents (multipart)
    API->>DB: Ghi Document status=đang xử lý, version, is_latest
    API-->>FE: Trả document_id ngay, không chờ xử lý xong
    API->>BG: add_task(...) chạy trong cùng process, sau khi response đã gửi
    FE-->>HV: Hiện tài liệu với badge "đang xử lý"

    activate BG
    BG->>BG: parse_document() - PDF theo trang / DOCX theo nhóm đoạn văn
    BG->>BG: chunk_sections() - 800 ký tự, overlap 100
    BG->>EMB: embed_texts(chunks)
    EMB-->>BG: ma trận embedding đã L2-normalize
    BG->>VEC: UserVectorStore(user_id).add(embeddings, chunks)
    alt Xử lý thành công
        BG->>DB: doc.status = "sẵn sàng"
    else Lỗi ở bất kỳ bước nào
        BG->>DB: doc.status = "lỗi", error_reason = str(exception)
    end
    deactivate BG

    loop Mỗi 2 giây (setInterval trong UploadPage)
        FE->>API: GET /documents?user_id=...
        API->>DB: Đọc danh sách Document
        DB-->>API: status hiện tại từng tài liệu
        API-->>FE: Danh sách kèm status
        FE-->>HV: Cập nhật badge trạng thái
    end

    Note over FE,DB: Chỉ có 3 trạng thái rời rạc, không có phần trăm tiến độ.
```

---

## 5. Agent/pipeline hỏi đáp

Đây là pipeline cố định, không phải agent tự chọn hành động tiếp theo (đã ghi rõ trong docstring của `app/llm/rag.py`). Hai nhánh dừng sớm: guardrail chặn và verifier từ chối.

```mermaid
flowchart TD
    IN(["Câu hỏi của người học + user_id"])

    CLASSIFY{"Khớp mẫu ý định 'nên học gì tiếp theo'?"}
    RECOBUILD["Đọc lại MasteryScore đã có, gợi ý rule-based, không gọi LLM"]

    subgraph guard["Guardrail - app/llm/guardrail.py"]
        G1{"Vừa có danh từ chỉ loại bài vừa có cụm 'làm hộ'?"}
        G1BLOCK(["Chặn - thông báo không làm bài hộ"])
        G2{"Khớp pattern injection/jailbreak rõ ràng?"}
        G2BLOCK(["Chặn - không phải câu hỏi học tập hợp lệ"])
        G3{"Khớp từ khoá mơ hồ (vai trò, prompt, system...)?"}
        G3LLM["Gọi Gemini 1 lần làm gatekeeper phân loại"]
        G3BLOCK(["Chặn theo verdict KHÔNG_AN_TOÀN"])
    end

    subgraph retrieve["Truy hồi có kiểm soát"]
        DOCFILTER["Lọc document_ids: status=sẵn sàng, is_latest=True, đúng user_id (+course_name nếu có)"]
        NODOCS{"Có tài liệu nào sẵn sàng?"}
        NODOCSERR(["Lỗi 400 - chưa có tài liệu nào sẵn sàng"])
        RETRIEVE["Hybrid retrieval + rerank (xem sơ đồ 6)"]
        THRESH{"Có chunk nào đạt min_score, mặc định 0.3?"}
        NOCTX(["'Nội dung này chưa có trong tài liệu bạn đã tải lên.'"])
    end

    subgraph genver["Generator + Verifier - app/llm/rag.py"]
        HISTBLOCK["Lấy tối đa 3 lượt hội thoại gần nhất, chỉ để giải ngữ cảnh đại từ"]
        LEVEL["Áp instruction theo level (beginner/advanced) nếu có truyền vào"]
        GEN["Generator: sinh câu trả lời nháp từ đoạn trích + lịch sử + level"]
        VERIFY["Verifier: lượt gọi LLM riêng, không nhận lịch sử hội thoại"]
        GROUNDED{"Verifier trả 'CÓ'?"}
        NOTGROUNDED(["'Chưa đủ căn cứ trong kho tài liệu để trả lời chắc chắn câu hỏi này.'"])
        DEDUPE["Loại trùng source theo (document_name, position_ref)"]
    end

    SAVE["Lưu Message (user + assistant) kèm is_grounded và cited_sources"]
    OUT(["Trả câu trả lời + is_grounded + sources"])

    IN --> CLASSIFY
    CLASSIFY -->|"Có"| RECOBUILD
    CLASSIFY -->|"Không"| G1
    RECOBUILD --> SAVE

    G1 -->|"Có"| G1BLOCK
    G1BLOCK --> SAVE
    G1 -->|"Không"| G2
    G2 -->|"Có"| G2BLOCK
    G2BLOCK --> SAVE
    G2 -->|"Không"| G3
    G3 -->|"Có"| G3LLM
    G3LLM -->|"KHÔNG_AN_TOÀN"| G3BLOCK
    G3BLOCK --> SAVE
    G3LLM -->|"AN_TOÀN"| DOCFILTER
    G3 -->|"Không"| DOCFILTER

    DOCFILTER --> NODOCS
    NODOCS -->|"Không"| NODOCSERR
    NODOCS -->|"Có"| RETRIEVE
    RETRIEVE --> THRESH
    THRESH -->|"Không"| NOCTX
    NOCTX --> SAVE
    THRESH -->|"Có"| HISTBLOCK
    HISTBLOCK --> LEVEL
    LEVEL --> GEN
    GEN --> VERIFY
    VERIFY --> GROUNDED
    GROUNDED -->|"Không"| NOTGROUNDED
    NOTGROUNDED --> SAVE
    GROUNDED -->|"Có"| DEDUPE
    DEDUPE --> SAVE
    SAVE --> OUT
```

Không có nhánh riêng "phát hiện mâu thuẫn giữa nguồn rồi hỏi lại người dùng" - generator được chỉ dẫn tự nêu rõ khác biệt khi các đoạn trích đến từ nhiều nguồn mâu thuẫn nhau, nhưng đây là hành vi mong đợi ở output văn bản, không phải một nhánh graph riêng có kiểm tra sau đó.

---

## 6. Hybrid retrieval

Lọc theo quyền và trạng thái tài liệu xảy ra trước khi truy hồi (qua tham số `document_ids` truyền vào tận `UserVectorStore`), không phải lọc kết quả sau khi đã tìm kiếm trên toàn bộ corpus.

```mermaid
flowchart TB
    Q(["Câu hỏi + user_id + document_ids đã lọc quyền/trạng thái"])

    ISOLATE["UserVectorStore(user_id): mở đúng file .faiss/.meta.pkl của user này, không có index nào khác truy cập được"]

    MODE{"Biến môi trường EDUTUTOR_RETRIEVAL_MODE=dense_only? (chỉ dùng khi benchmark, không set khi chạy thật)"}

    subgraph denseonly["Nhánh benchmark - so sánh cấu hình"]
        DENSESEARCH["store.search(): cosine similarity thuần, bỏ qua BM25 và rerank"]
    end

    subgraph hybrid["Nhánh production - mặc định"]
        subgraph songsong["Hai nhánh song song trong hybrid_search()"]
            DENSE["Nhánh ngữ nghĩa<br/>FAISS IndexFlatIP top candidate_pool"]
            BM25B["Nhánh từ khoá<br/>BM25Okapi build lại từ metadata hiện có, loại chunk điểm = 0.0 tuyệt đối"]
        end
        RRF["Reciprocal Rank Fusion (k=60), gộp 2 danh sách id thành 1 điểm duy nhất"]
        FILTERDOC["Lọc theo document_ids (quyền + sẵn sàng + is_latest + course_name)"]
        CANDIDATES["Tối đa candidate_pool = max(20, top_k x 3) ứng viên"]
        RERANK["Cross-encoder rerank, chấm điểm trực tiếp (câu hỏi, chunk)"]
        SIGMOID["Chuẩn hoá điểm qua sigmoid về (0,1)"]
        TOPK["Cắt về top_k cuối cùng, mặc định 5"]
    end

    THRESH{"Điểm cao nhất >= min_score, mặc định 0.3?"}
    CTX(["Context gửi cho generator (sơ đồ 5)"])
    NONE(["Không đủ căn cứ, agent trả NO_CONTEXT_MESSAGE"])

    Q --> ISOLATE
    ISOLATE --> MODE
    MODE -->|"Có, chỉ benchmark"| DENSESEARCH
    MODE -->|"Không, mặc định"| DENSE
    MODE -->|"Không, mặc định"| BM25B
    DENSE --> RRF
    BM25B --> RRF
    RRF --> FILTERDOC
    FILTERDOC --> CANDIDATES
    CANDIDATES --> RERANK
    RERANK --> SIGMOID
    SIGMOID --> TOPK
    TOPK --> THRESH
    DENSESEARCH --> THRESH
    THRESH -->|"Có"| CTX
    THRESH -->|"Không"| NONE
```

Vì sao cần cả 2 nhánh, đã đo bằng eval thật chứ không chỉ đoán theo lý thuyết:

| So sánh | Dense-only (Config A) | Hybrid + Rerank (Config B, đang chạy thật) |
| --- | --- | --- |
| Context Precision | 0.41 (N=22) | **0.77** (N=22), +0.36 |
| Citation Accuracy | 0.30 (N=20) | **0.75** (N=20), +0.45 |
| Faithfulness | 0.80 (N=40) | **0.90** (N=40), +0.10 |
| Ổn định qua 2 lần chạy độc lập | - | cả 3 chỉ số trên không đổi (0pp), nên chênh lệch trên là tín hiệu thật |

Nguồn: `eval/report.md` mục 14-15. Đánh đổi duy nhất thấy được: Hybrid+Rerank lọc gắt hơn nên đôi khi từ chối trả lời thay vì trả lời không hoàn chỉnh, ở câu hỏi so sánh 2 chủ đề tách biệt (xem mục 13 của `eval/report.md`).

---

## 7. Sinh Quiz/Flashcard và cập nhật mastery

Cùng một pattern generator sinh hàng loạt rồi verify từng item được dùng lại cho cả Quiz và Flashcard; nộp bài quiz là điểm duy nhất kích hoạt tính lại mastery.

```mermaid
flowchart TB
    REQ(["Yêu cầu sinh quiz/flashcard: 1 hoặc nhiều document_id"])
    DOCCHECK{"Tài liệu tồn tại, đúng user_id, status=sẵn sàng?"}
    ERR1(["Lỗi 400 - tài liệu không tồn tại hoặc chưa sẵn sàng"])

    RETRPERDOC["Truy hồi riêng theo từng tài liệu (query = tên file), tránh dồn hết câu hỏi vào 1 tài liệu khi sinh đa tài liệu"]
    NOCHUNK{"Có chunk nào truy hồi được?"}
    ERR2(["Lỗi 400 - không tìm thấy nội dung để sinh"])

    GEN["Generator: 1 lượt gọi LLM sinh JSON N câu hỏi/thẻ + chunk_index tham chiếu"]
    PARSE{"JSON hợp lệ và là mảng?"}
    EMPTY1(["Trả rỗng, không cố sửa JSON hỏng"])

    LOOP["Với từng item trong mảng"]
    FIELDCHECK{"Đủ field bắt buộc và chunk_index hợp lệ?"}
    SKIP1["Bỏ qua item, không gọi verifier để đỡ tốn quota"]
    ITEMVERIFY["Verify riêng: LLM đọc chunk gốc + nội dung item, trả CÓ/KHÔNG"]
    ACCEPT{"Verifier trả CÓ?"}
    SKIP2["Loại item"]
    KEEP["Giữ item, gắn source_document/source_position từ chunk"]

    ALLEMPTY{"Còn item nào sau khi lọc?"}
    ERR3(["Lỗi 500 - không sinh được câu hỏi nào xác minh được"])
    TOPICASSIGN["Gán Topic: ưu tiên tên người dùng nhập, sau đó tên file (1 tài liệu) hoặc course_name (đa tài liệu)"]
    SAVEQUIZ["Lưu Quiz/QuizItem hoặc FlashcardSet/FlashcardItem, không trả correct_answer khi sinh quiz"]

    SUBMIT(["Người học nộp đáp án 1 câu"])
    RECORDATTEMPT["Ghi Attempt(is_correct, attempted_at)"]
    HASTOPIC{"QuizItem có gắn topic_id?"}
    RECOMPUTE["Lấy toàn bộ lịch sử Attempt của topic đó, tính lại compute_mastery(), recency-weighted"]
    UPSERT["Ghi đè MasteryScore (cache)"]
    RETURNRESULT(["Trả is_correct + correct_answer + explanation + updated_mastery_score"])

    REQ --> DOCCHECK
    DOCCHECK -->|"Không"| ERR1
    DOCCHECK -->|"Có"| RETRPERDOC
    RETRPERDOC --> NOCHUNK
    NOCHUNK -->|"Không"| ERR2
    NOCHUNK -->|"Có"| GEN
    GEN --> PARSE
    PARSE -->|"Không"| EMPTY1
    PARSE -->|"Có"| LOOP
    LOOP --> FIELDCHECK
    FIELDCHECK -->|"Không"| SKIP1
    FIELDCHECK -->|"Có"| ITEMVERIFY
    ITEMVERIFY --> ACCEPT
    ACCEPT -->|"Không"| SKIP2
    ACCEPT -->|"Có"| KEEP
    SKIP1 --> ALLEMPTY
    SKIP2 --> ALLEMPTY
    KEEP --> ALLEMPTY
    ALLEMPTY -->|"Không"| ERR3
    ALLEMPTY -->|"Có"| TOPICASSIGN
    TOPICASSIGN --> SAVEQUIZ

    SAVEQUIZ -.->|"Người học làm bài sau đó"| SUBMIT
    SUBMIT --> RECORDATTEMPT
    RECORDATTEMPT --> HASTOPIC
    HASTOPIC -->|"Có"| RECOMPUTE
    RECOMPUTE --> UPSERT
    UPSERT --> RETURNRESULT
    HASTOPIC -->|"Không"| RETURNRESULT
```

Điểm đáng chú ý đã đo được: Flashcard groundedness đạt 1.00 (N=6) trong khi Quiz groundedness chỉ đo 0.67 (N=9) dù dùng chung một pattern generator+verifier. `eval/report.md` mục 13 chỉ ra phần lớn "fail" của Quiz là do giám khảo chấm sai (hiểu nhầm việc hệ thống cố tình giấu đáp án ở bước sinh là thiếu sót), không phải lỗi groundedness thật. Cần sửa tiêu chí chấm trước khi kết luận Quiz kém hơn Flashcard.

---

## 8a. Bản đồ dữ liệu

11 bảng gom thành 3 cụm.

```mermaid
flowchart TB
    subgraph cum1["Cụm 1 - Người dùng và tài liệu"]
        USER["USER<br/>Hiện chỉ 1 user cố định (demo-user)"]
        DOCUMENT["DOCUMENT<br/>Versioning qua version + is_latest"]
    end

    subgraph cum2["Cụm 2 - Hội thoại và tri thức đã sinh"]
        CONV["CONVERSATION"]
        MSG["MESSAGE<br/>is_grounded + cited_sources (JSON)"]
        TOPIC["TOPIC<br/>Nhóm quiz/flashcard để tính mastery"]
        QUIZ["QUIZ"]
        QUIZITEM["QUIZ_ITEM"]
        FCSET["FLASHCARD_SET"]
        FCITEM["FLASHCARD_ITEM"]
    end

    subgraph cum3["Cụm 3 - Tiến độ học tập"]
        ATTEMPT["ATTEMPT<br/>Input duy nhất cho công thức mastery"]
        MASTERY["MASTERY_SCORE<br/>Cache, ghi đè mỗi khi có Attempt mới"]
    end

    USER -->|"tải lên nhiều"| DOCUMENT
    USER -->|"có nhiều"| CONV
    CONV -->|"chứa nhiều"| MSG
    USER -->|"làm nhiều"| QUIZ
    DOCUMENT -->|"sinh ra"| QUIZ
    QUIZ -->|"gồm nhiều"| QUIZITEM
    TOPIC -->|"gắn với"| QUIZITEM
    DOCUMENT -->|"sinh ra"| FCSET
    FCSET -->|"gồm nhiều"| FCITEM
    TOPIC -->|"gắn với"| FCITEM
    QUIZITEM -->|"sinh ra khi nộp bài"| ATTEMPT
    TOPIC -->|"gắn với"| ATTEMPT
    ATTEMPT -->|"tính lại"| MASTERY
    TOPIC -->|"có điểm"| MASTERY
```

Không có bảng "chunk có trạng thái duyệt" - chunk (vector + text) sống trong FAISS/pickle, không phải bảng SQL riêng, không mang cờ duyệt nào. Việc không bịa được đảm bảo ở bước verifier khi trả lời (sơ đồ 5), không phải ở việc kiểm soát dữ liệu đầu vào.

---

## 8b. Schema chi tiết

Trường, kiểu dữ liệu và khoá của từng bảng SQL, lấy trực tiếp từ `app/models.py`. Chunk/vector không nằm trong SQLite mà nằm trong FAISS + file pickle metadata riêng (`app/vectorstore/faiss_store.py`), nên không xuất hiện trong ER này.

```mermaid
erDiagram
    USER ||--o{ DOCUMENT : "tải lên"
    USER ||--o{ CONVERSATION : "có"
    CONVERSATION ||--o{ MESSAGE : "chứa"
    USER ||--o{ QUIZ : "làm"
    DOCUMENT ||--o{ QUIZ : "sinh ra"
    QUIZ ||--o{ QUIZ_ITEM : "gồm"
    TOPIC ||--o{ QUIZ_ITEM : "gắn"
    DOCUMENT ||--o{ FLASHCARD_SET : "sinh ra"
    FLASHCARD_SET ||--o{ FLASHCARD_ITEM : "gồm"
    TOPIC ||--o{ FLASHCARD_ITEM : "gắn"
    QUIZ_ITEM ||--o{ ATTEMPT : "sinh ra"
    TOPIC ||--o{ ATTEMPT : "gắn"
    TOPIC ||--o{ MASTERY_SCORE : "có điểm"

    USER {
        string id PK
        string email UK
        string display_name
        datetime created_at
    }

    DOCUMENT {
        string id PK
        string user_id FK
        string file_name
        string doc_type "slide, giáo trình, ghi chú - tuỳ chọn"
        string course_name "tuỳ chọn"
        string status "đang xử lý, sẵn sàng, lỗi"
        text error_reason
        datetime uploaded_at
        int version "tăng khi upload lại cùng file_name+course_name"
        boolean is_latest
    }

    CONVERSATION {
        string id PK
        string user_id FK
        string course_name "tuỳ chọn"
        datetime created_at
    }

    MESSAGE {
        string id PK
        string conversation_id FK
        string role "user, assistant"
        text content
        text cited_sources "JSON: [{document_name, position_ref}]"
        boolean is_grounded "null nếu role=user"
        datetime created_at
    }

    TOPIC {
        string id PK
        string user_id FK
        string course_name "tuỳ chọn"
        string name
    }

    QUIZ {
        string id PK
        string user_id FK
        string document_id FK "tài liệu đầu tiên nếu đa tài liệu"
        datetime created_at
    }

    QUIZ_ITEM {
        string id PK
        string quiz_id FK
        string topic_id FK "tuỳ chọn"
        text question
        text options "JSON mảng 4 chuỗi"
        string correct_answer
        text explanation
        string source_document
        string source_position
    }

    FLASHCARD_SET {
        string id PK
        string user_id FK
        string document_id FK
        datetime created_at
    }

    FLASHCARD_ITEM {
        string id PK
        string flashcard_set_id FK
        string topic_id FK "tuỳ chọn"
        text front
        text back
        string source_document
        string source_position
    }

    ATTEMPT {
        string id PK
        string user_id FK
        string quiz_item_id FK
        string topic_id FK "tuỳ chọn"
        boolean is_correct
        datetime attempted_at
    }

    MASTERY_SCORE {
        string id PK
        string user_id FK
        string topic_id FK
        float score "0 đến 1, cache, ghi đè mỗi khi có Attempt mới"
        datetime updated_at
    }
```

---

## 9. Vòng đời tài liệu

Ba trạng thái rời rạc, không có trạng thái trung gian theo phần trăm. Versioning là một trục riêng, không phải một trạng thái trong vòng đời xử lý.

```mermaid
stateDiagram-v2
    [*] --> DangXuLy: Upload, status = "đang xử lý"

    DangXuLy --> SanSang: Parse + chunk + embed + index thành công
    DangXuLy --> Loi: Bất kỳ bước nào lỗi, ghi error_reason

    Loi --> [*]: Người dùng xoá tài liệu lỗi và tải lại từ đầu (chưa có nút thử lại tự động)

    SanSang --> DangXuLy: Upload lại cùng file_name + course_name, bản này version+1, is_latest=True; bản cũ is_latest=False, vẫn giữ trạng thái sẵn sàng

    SanSang --> [*]: Xoá tài liệu, xoá file gốc, bản ghi DB, và toàn bộ vector liên quan trong FAISS

    note right of SanSang
        Chỉ tài liệu status=sẵn sàng và is_latest=True
        được dùng cho hỏi đáp (F2) và sinh quiz/flashcard (F4, F5).
        Bản cũ (is_latest=False) vẫn hiện trong danh sách tài liệu
        nhưng không được dùng làm căn cứ truy hồi mới.
    end note

    note right of DangXuLy
        Không có phần trăm tiến độ.
        Frontend chỉ biết 3 trạng thái qua poll GET /documents mỗi 2 giây.
        Không có hàng đợi Redis/RQ, xử lý chạy trong
        cùng process API qua FastAPI BackgroundTasks.
    end note
```

---

## 10. Triển khai

Một container duy nhất cho backend (API + xử lý nền trong cùng process); frontend chưa containerize trong `docker-compose.yml` hiện tại, chạy qua `npm run dev` khi phát triển.

```mermaid
flowchart TB
    subgraph client["Máy người dùng"]
        BROWSER["Trình duyệt"]
    end

    subgraph devfe["Máy phát triển"]
        VITE["Vite dev server<br/>frontend/, npm run dev, cổng 5173"]
    end

    subgraph docker["Docker Compose - service duy nhất: backend"]
        API["FastAPI + Uvicorn<br/>+ xử lý nền qua BackgroundTasks<br/>(không phải container worker riêng)"]
        LOCALMODEL["sentence-transformers + cross-encoder<br/>load một lần (lru_cache), chạy trong cùng container"]
    end

    subgraph volume["Named volume - edututor_data"]
        DATA[("backend/data/<br/>edututor.db (SQLite), uploads/, vectorstore/ (FAISS)<br/>Sống sót qua docker compose down / rebuild image,<br/>chỉ mất khi down -v")]
    end

    subgraph ngoai["Dịch vụ ngoài"]
        GEMINI["Gemini API, free tier<br/>đọc GEMINI_API_KEY từ .env"]
    end

    BROWSER -->|"http://localhost:5173"| VITE
    VITE -->|"fetch REST, API_BASE cố định trong api.js"| API
    API -->|"JSON"| VITE

    API -->|"Đọc/ghi"| DATA
    LOCALMODEL -.->|"cùng process, không qua network"| API

    API -->|"Prompt generator/verifier/gatekeeper"| GEMINI
    GEMINI -->|"Text response"| API
```

Vì sao một container là đủ: xử lý một tài liệu (parse + embed) mất vài giây tới vài chục giây với model local, không phải vài phút gọi LLM API cho nội dung dài, nên chấp nhận được khi chạy trong `BackgroundTasks` cùng process thay vì tách sang worker riêng như Celery/RQ. Đánh đổi: nếu nhiều người dùng cùng lúc tải tài liệu lớn, xử lý nền có thể cạnh tranh CPU với các request đồng bộ khác trong cùng process - chưa phải vấn đề ở quy mô 1 người dùng cục bộ hiện tại, nhưng là chỗ cần xem lại đầu tiên nếu sau này mở rộng sang nhiều người dùng thật.

Phương án thay thế nếu cần: tách `_run_processing_job` sang worker riêng (Redis + RQ) chỉ cần thiết khi có nhiều người dùng cùng lúc tải tài liệu lớn, chưa cần ở quy mô hiện tại.
