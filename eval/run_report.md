# Golden Set — Live Run Report (real execution, not projected)

Chạy thật qua `POST /chat/ask` trên backend local (Postgres `edututor-pg` +
MinIO local, không đụng production), 13 tài liệu corpus mới đã tải lên dưới
`user_id=golden-eval-user`, `course_name=GoldenSetEval`. Script:
`eval/run_golden_set.py`. Kết quả thô: `eval/run_results.jsonl`.

## Phạm vi thực chạy được trong lần này

- **174/267 case** thuộc 11 category dùng `/chat/ask` đã chạy xong và có kết
  quả thật (rag_qa, retrieval, grounding_citation, abstention_clarification,
  conversational, decomposition — 6/6 category có ít nhất 1 kết quả).
- **93 case còn lại** của 11 category trên (multi_document, compare,
  summarize, apply, guardrail, và phần đuôi decomposition) **chưa chạy được**
  — bị chặn giữa chừng bởi **hết quota Cohere Trial API key (giới hạn 1000
  lượt gọi/tháng)**. Mọi câu hỏi đều cần Cohere embed để truy hồi, nên khi
  hết quota mọi request tiếp theo đều lỗi 429/timeout. Đây là giới hạn hạ
  tầng thật, không phải lỗi code — cần key Cohere trả phí hoặc đợi quota
  reset để chạy tiếp phần còn lại.
- **126 case thuộc 9 category hành vi** (document_management, persistence,
  error_handling, personalization, mastery, quiz, flashcard, study_plan,
  profile) **không nằm trong phạm vi lần chạy này** — các case đó cần dựng
  fixture trạng thái DB (lịch sử attempt, review flashcard nhiều ngày...)
  phức tạp hơn những gì mô tả tự nhiên trong `context` của mỗi case hỗ trợ
  tự động hoá đáng tin cậy ngay bây giờ.

## Một bug thật phát hiện TRƯỚC KHI chạy được: NUL byte trong PDF

Tài liệu Phở (`13_offtopic_am_thuc_vi.pdf`) kẹt mãi ở "đang xử lý" vì pypdf
trích ra byte NUL (0x00), Postgres từ chối thẳng, job xử lý nền crash giữa
chừng không kịp ghi `status="lỗi"` — đúng kịch bản đã lường trước khi audit
code (`feature_inventory.md`). Đã sửa (`backend/app/ingestion/parser.py`,
commit `6ff36a6`, có test hồi quy `tests/test_parser.py`) và tải lại thành
công. Xem đây là một bằng chứng cụ thể rằng lần chạy thật này tìm ra thứ mà
việc "xây" Golden Set trên giấy không tìm ra được.

## Kết quả tổng hợp (174 case đã chạy)

| Category | Pass | Fail | Tỷ lệ |
|---|---:|---:|---:|
| rag_qa | 40 | 5 | 89% |
| retrieval | 32 | 3 | 91% (đã hiệu chỉnh, xem ghi chú bên dưới) |
| decomposition | 6 | 3 | 67% (mẫu nhỏ, mới chạy 9/20) |
| conversational | 11 | 14 | 44% |
| grounding_citation | 14 | 21 | 40% |
| abstention_clarification | 9 | 16 | 36% |
| **TỔNG (đã hiệu chỉnh)** | **112** | **62** | **64.4%** |

**Ghi chú hiệu chỉnh quan trọng**: script chấm điểm (`run_golden_set.py`)
ban đầu nhận diện sai 8 câu trả lời đúng thành "fail" — hệ thống thật trả
lời đúng ("Không tìm thấy nội dung này trong tài liệu của bạn. Hệ thống đã
tìm 2 lượt...") cho các câu hỏi ngoài phạm vi ("giá xăng dầu hôm nay",
"capital of France"...), nhưng regex nhận diện trong script chỉ khớp đúng
message cố định `NO_CONTEXT_MESSAGE` của `rag.py`, không khớp câu trả lời
đầy đủ hơn từ `answer_with_fallback` (`qa_pipeline.py`). Đây là **giới hạn
của công cụ chấm điểm, không phải lỗi hệ thống** — số liệu trong bảng trên
đã trừ đi 8 trường hợp này. Tỷ lệ thô (chưa hiệu chỉnh) là 59.8%.

## Hai phát hiện thật, đáng chú ý nhất

### 1. Follow-up câu hỏi dùng đại từ thường KHÔNG resolve được ngữ cảnh

7/25 case `conversational` (28%) rơi vào `needs_clarification` thay vì trả
lời đúng, và cụ thể là những câu hỏi dùng đại từ chỉ định ("nó", "cái đó")
tiếp nối lượt trước:

- "Vậy làm sao để biết một mô hình đang bị **vậy**?" (tiếp nối "overfitting")
- "**Nó** có mấy loại phổ biến?"
- "**Cái đó** hoạt động theo cơ chế nào?"

Cả ba đều nhận `NEEDS_CLARIFICATION_MESSAGE` thay vì dùng
`build_retrieval_query()` (đã có cơ chế nối từ khoá lượt trước vào truy vấn)
để resolve đúng chủ đề. Đây là bằng chứng thật xác nhận đúng lo ngại đã nêu
trong phần thảo luận thiết kế trước đó của phiên này ("Q&A chưa thực sự
resolve pronoun tốt") — giờ có số liệu cụ thể thay vì suy đoán.

### 2. Câu hỏi có tiền đề SAI bị gộp chung vào "needs_clarification" thay vì "unsupported_claim"

5 case (`EDU-GRD-013` đến `017`) hỏi những câu có tiền đề SAI rõ ràng (vd
"AlexNet đã dùng cơ chế attention...", "LeNet-5 được LeCun phát triển tại
**Google** năm 1998", "Random forest giảm overfitting bằng cách **tăng**
độ tương quan giữa các cây...") — tất cả đều nhận `NEEDS_CLARIFICATION_MESSAGE`
thay vì một câu trả lời khẳng định-và-sửa-lại hoặc từ chối rõ ràng vì
"không có căn cứ". Verifier's "addresses_question" gate có vẻ chặn những
câu hỏi dạng này TRƯỚC KHI cơ chế per-claim grounding có cơ hội đánh giá
tính đúng/sai của tiền đề — hệ quả là hệ thống AN TOÀN (không bịa, không
khẳng định sai) nhưng phản hồi mơ hồ hơn mức cần thiết, không rõ ràng nói
"tiền đề câu hỏi không đúng" cho người dùng.

## Điểm mạnh được xác nhận thật (không phải suy đoán)

- **Citation accuracy khi có trả lời**: 111/115 (97%) — trích dẫn đúng
  tài liệu nguồn.
- **Content correctness (LLM judge)**: 114/115 (99%) — khi hệ thống trả lời
  có căn cứ, nội dung gần như luôn đúng ý so với đáp án tham chiếu.
- **rag_qa**: 89% — lõi hỏi đáp trực tiếp hoạt động rất tốt.
- **retrieval**: 91% (đã hiệu chỉnh) — kể cả với paraphrase/typo/thuật ngữ
  gần đúng.

## Việc còn lại để có bức tranh đầy đủ

1. Chạy nốt 93 case `/chat/ask` còn lại — cần quota Cohere mới.
2. Xây fixture cho 126 case hành vi (Quiz/Flashcard/Mastery/Study
   Plan/Profile/Document management/Persistence/Error handling) — chưa làm
   trong lần này.
3. Sửa lại regex nhận diện outcome trong `run_golden_set.py` để khớp đúng
   message đầy đủ của `answer_with_fallback`, tránh hiệu chỉnh thủ công lần
   sau.
4. Điều tra kỹ hơn 2 phát hiện thật ở trên (pronoun resolution, false-premise
   handling) — đây là việc CẢI THIỆN SẢN PHẨM, ngoài phạm vi bản thân Golden
   Set.
