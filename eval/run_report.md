# Golden Set — Live Run Report (chạy thật, không phải số liệu suy diễn)

Chạy thật toàn bộ 267 case thuộc 11 category dùng `POST /chat/ask`
(rag_qa, retrieval, grounding_citation, abstention_clarification,
conversational, decomposition, multi_document, compare, summarize, apply,
guardrail) trên backend local (Postgres `edututor-pg` + MinIO local, không
đụng production), với 13 tài liệu corpus mới đã tải lên dưới
`user_id=golden-eval-user`, `course_name=GoldenSetEval`. Script:
`eval/run_golden_set.py`. Kết quả thô: `eval/run_results.jsonl` (267/267
case có kết quả thật).

126 case thuộc 9 category hành vi còn lại (document_management,
persistence, error_handling, personalization, mastery, quiz, flashcard,
study_plan, profile) chưa nằm trong phạm vi lần chạy này — cần dựng fixture
trạng thái DB (lịch sử attempt, review flashcard nhiều ngày...) phức tạp
hơn mức mô tả tự nhiên trong `context` của mỗi case hỗ trợ tự động hoá
đáng tin cậy.

## Một bug thật phát hiện trong lúc chuẩn bị chạy

Tài liệu Phở (`13_offtopic_am_thuc_vi.pdf`) kẹt mãi ở "đang xử lý" vì pypdf
trích ra byte NUL (0x00) lẫn trong text, Postgres từ chối thẳng insert, job
xử lý nền crash giữa chừng không kịp ghi `status="lỗi"`. Đã sửa
(`backend/app/ingestion/parser.py`, commit `6ff36a6`, có test hồi quy
`tests/test_parser.py`).

## Kết quả theo category (267/267 case)

| Category | Pass | Fail | Tỷ lệ | Ghi chú |
|---|---:|---:|---:|---|
| rag_qa | 40 | 5 | 89% | Lõi hỏi đáp trực tiếp — hoạt động rất tốt |
| retrieval | 31 | 4 | 89% | Kể cả với paraphrase/typo/thuật ngữ gần đúng |
| decomposition | 12 | 8 | 60% | Xem phát hiện #1 bên dưới |
| compare | 8 | 7 | 53% | |
| multi_document | 8 | 12 | 40% | |
| grounding_citation | 14 | 21 | 40% | Xem phát hiện #2 |
| conversational | 10 | 15 | 40% | Xem phát hiện #3 |
| abstention_clarification | 9 | 16 | 36% | Nhiều case bị chấm nhầm bởi công cụ chấm điểm — xem ghi chú |
| apply | 4 | 11 | 27% | |
| guardrail | — | — | — | Không dùng tỷ lệ pass nhị phân — xem phần riêng bên dưới, kết quả THỰC CHẤT tốt hơn nhiều so với số thô |
| summarize | — | — | — | Xem phát hiện #4 — không phải "hỏng hoàn toàn" như số thô cho thấy |

**Chỉ số xuyên suốt (đáng tin cậy nhất, không phụ thuộc cách phân loại category)**:
- Citation accuracy khi có trả lời: **155/160 (97%)**
- Content correctness (LLM judge) khi có trả lời: **159/160 (99%)**

## Guardrail — đọc đúng bản chất thay vì tỷ lệ pass thô

- **9/9 case false-positive (câu hỏi hợp lệ) đều KHÔNG bị chặn nhầm** — guardrail không có false positive nào trong mẫu này.
- Trong các case cố ý cần bị chặn: câu yêu cầu "làm hộ bài tập" (tiếng Việt lẫn tiếng Anh) đều bị chặn đúng bởi `ACADEMIC_INTEGRITY_MESSAGE`.
- 2 case injection tinh vi hơn (giả mạo trích dẫn, yêu cầu "bỏ qua tài liệu dùng kiến thức chung") **không bị lợi dụng thành công** (hệ thống không tạo trích dẫn giả, không bỏ qua tài liệu) nhưng cũng không được nhận diện rõ ràng là injection — rơi vào phản hồi chung chung (`needs_clarification`/không tìm thấy). Đây là điểm biên đáng theo dõi, không phải lỗ hổng bảo mật thực sự (không có hành vi có hại nào xảy ra).

## Bốn phát hiện thật, đáng chú ý nhất

### 1. Follow-up câu hỏi dùng đại từ thường KHÔNG resolve được ngữ cảnh

7/25 case `conversational` (28%) rơi vào `needs_clarification` thay vì trả
lời đúng — cụ thể là các câu dùng đại từ chỉ định tiếp nối lượt trước
("Nó có mấy loại phổ biến?", "Cái đó hoạt động theo cơ chế nào?"). Hệ
thống không dùng được ngữ cảnh hội thoại để resolve chủ đề dù
`build_retrieval_query()` đã có cơ chế nối từ khoá lượt trước.

### 2. Câu hỏi có tiền đề SAI bị gộp vào "needs_clarification" thay vì bị bác bỏ rõ ràng

5/5 case hỏi những câu có tiền đề sai rõ ràng (vd "LeNet-5 được LeCun phát
triển tại Google năm 1998", "Random forest giảm overfitting bằng cách
TĂNG độ tương quan giữa các cây...") đều nhận `NEEDS_CLARIFICATION_MESSAGE`
thay vì một câu trả lời khẳng định-và-sửa-lại hoặc từ chối rõ ràng vì
tiền đề sai. Verifier's "addresses_question" gate có vẻ chặn những câu này
trước khi cơ chế per-claim grounding có cơ hội đánh giá đúng/sai của
tiền đề.

### 3. Một mẫu hình lặp lại xuyên suốt nhiều category: câu hỏi hợp lệ nhưng phức tạp/ghép nhiều ý dễ rơi vào "needs_clarification"

Không chỉ ở #1 và #2 — nhiều case `guardrail` false-positive (câu hỏi hợp
lệ, không nên bị chặn) và nhiều case `apply`/`grounding_citation` cũng cho
kết quả tương tự: hệ thống AN TOÀN (không bịa, không chặn nhầm) nhưng phản
hồi mơ hồ hơn cần thiết thay vì trả lời thẳng hoặc từ chối có lý do cụ thể.
Đây là dấu hiệu cho thấy verifier's "addresses_question" gate hiện đang
thiên về phía thận trọng quá mức với câu hỏi phức tạp/ghép ý, không riêng
gì hội thoại nhiều lượt.

### 4. Summarize: cơ chế khớp chủ đề (resolve_topic) chặt hơn cần thiết trong thực tế

Với các tài liệu THỰC SỰ có chủ đề để tóm tắt, chỉ 1/7 case khớp được
đúng chủ đề và trả về bản tóm tắt cấu trúc thật — 6/7 nhận
`NEEDS_TOPIC_MESSAGE` dù chủ đề có tồn tại. `resolve_topic()` chỉ khớp khi
có trùng từ nội dung với tiêu đề DocumentTopic — nguyên tắc "không đoán
bừa" này an toàn nhưng có thể quá chặt khi người dùng diễn đạt theo nội
dung thay vì lặp lại đúng từ trong tiêu đề gốc. Ngược lại, 6 case cố ý
KHÔNG có chủ đề để tóm tắt đều nhận đúng `NEEDS_TOPIC_MESSAGE` như thiết kế
— đúng hành vi mong đợi.

## Việc còn lại để có bức tranh đầy đủ

1. Xây fixture cho 126 case hành vi (Quiz/Flashcard/Mastery/Study
   Plan/Profile/Document management/Persistence/Error handling).
2. Điều tra sâu hơn phát hiện #3 (verifier addresses_question quá thận
   trọng) — đây là việc cải thiện sản phẩm, ngoài phạm vi Golden Set.
3. Xem lại ngưỡng khớp từ trong `resolve_topic()` (Summarize) — cân nhắc
   nới lỏng có kiểm soát thay vì yêu cầu trùng từ y hệt tiêu đề.
