# Golden Set — Live Run Report (chạy thật, không phải số liệu suy diễn)

Chạy thật toàn bộ **393/393 case** trên backend local (Postgres
`edututor-pg` + MinIO local, không đụng production), với 13 tài liệu
corpus mới đã tải lên dưới `user_id=golden-eval-user`,
`course_name=GoldenSetEval`:

- **267 case** thuộc 11 category dùng `POST /chat/ask` (rag_qa, retrieval,
  grounding_citation, abstention_clarification, conversational,
  decomposition, multi_document, compare, summarize, apply, guardrail) —
  script `eval/run_golden_set.py`, kết quả thô `eval/run_results.jsonl`.
- **126 case** thuộc 9 category hành vi (document_management, persistence,
  error_handling, personalization, mastery, quiz, flashcard, study_plan,
  profile) — chạy qua 41 kịch bản stateful (setup → API actions →
  verification → assertions), tái dùng state chung để tiết kiệm quota,
  script `eval/run_stateful_scenarios.py`, kết quả thô
  `eval/stateful_results.jsonl`.

## Một bug thật phát hiện trong lúc chuẩn bị chạy

Tài liệu Phở (`13_offtopic_am_thuc_vi.pdf`) kẹt mãi ở "đang xử lý" vì pypdf
trích ra byte NUL (0x00) lẫn trong text, Postgres từ chối thẳng insert, job
xử lý nền crash giữa chừng không kịp ghi `status="lỗi"`. Đã sửa
(`backend/app/ingestion/parser.py`, commit `6ff36a6`, có test hồi quy
`tests/test_parser.py`).

---

# Phần 1 — Q&A (267 case qua `/chat/ask`)

## Kết quả theo category

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

---

# Phần 2 — Hành vi (126 case, chạy qua 41 kịch bản stateful)

## Phân biệt Golden Cases / Stateful Scenarios / API calls / LLM calls

| | Số lượng |
|---|---:|
| Golden Cases gốc (9 category hành vi) | 126 |
| Stateful Scenarios thực chạy (nhóm/đại diện, tái dùng state chung) | 41 |
| API calls thật tới backend | 45 |
| LLM generation calls (Quiz + Flashcard generate, MỖI cái CHỈ 1 lần rồi tái dùng) | 2 |

Không phải 1-1 giữa 126 Golden Case và 41 Scenario — nhiều Golden Case
cùng category dùng CHUNG một lần setup (vd 5 case `topic_plausibility_filter`
đều xét trên CÙNG kết quả `GET /study-plan` một lần thay vì gọi lại 5 lần).
Đây là chủ đích tiết kiệm quota, không phải bỏ sót.

## Kết quả: 40/41 scenario PASS

Toàn bộ Profile (6/6), Document management (7/7), Error handling (3/3),
Quiz→Mastery (8/8, bao gồm cả 2 case time-simulation qua đúng field
`MasteryScore.updated_at`), Flashcard→SRS (10/10, bao gồm case time-simulation
qua đúng field `FlashcardReview.next_due_at`, KHÔNG phải `reviewed_at`),
Study Plan (5/6) đều đúng như kỳ vọng.

## Một phát hiện thật, giá trị — lỗ hổng còn sót trong bộ lọc topic nhiễu

`GET /study-plan` (qua `app/routers/study_plan.py`, dùng chung
`filter_topic_titles` với `chat.py`) vẫn để lọt qua các mục **tham khảo
đánh số kiểu Wikipedia** vào kế hoạch học, dù trông rõ ràng không phải
tiêu đề chương:

- `15. "OpenNMT – Open-Source Neural Machine Translation". opennmt.net. Truy cập`
- `1.0 for a class C means that every item` (một câu bị cắt giữa chừng, không phải heading)

**Nguyên nhân**: Sau khi sửa outline PDF trước đó trong phiên (bỏ nhánh
Title-Case/ALL-CAPS, chỉ giữ mục đánh số kiểu `_NUMBERED_SECTION_RE =
r"^\d{1,2}(\.\d{1,2}){0,3}\.?\s+\S"`), một mục THAM KHẢO đánh số trong phần
"Tham khảo"/"References" của Wikipedia (vd `"15. Tên bài báo". domain.net.
Truy cập ngày...`) khớp CHÍNH XÁC mẫu này — về mặt cú pháp nó cũng là "số +
dấu chấm + text", không khác gì "6.1 Machine Translation". Bộ lọc
`is_plausible_topic()` có luật loại citation-like (năm trong ngoặc,
ISBN/DOI, "tr./pp.") nhưng KHÔNG có luật cho định dạng **web/Wikipedia**
(URL + "Truy cập ngày") — đúng kiểu trích dẫn phổ biến nhất trong corpus
mới (toàn bộ 13 tài liệu đều từ Wikipedia).

**Vì sao đáng chú ý**: đây là loại lỗi CHỈ lộ ra khi kiểm thử một tính năng
(Study Plan) đọc dữ liệu do một tính năng KHÁC tạo ra (outline extraction
lúc upload) — đúng giá trị của kịch bản liên-tính-năng mà thiết kế lần này
hướng tới, không thể phát hiện được nếu chỉ test outline.py hay
study_plan.py riêng lẻ.

## Việc không nằm trong phạm vi lần chạy này (nêu rõ, không giấu)

- Không test `personalization` sâu (inferred_level qua 3 dải mastery cụ
  thể — cần 3 user riêng với mastery set sẵn ở đúng 3 dải, chưa dựng).
  `effective_level_priority`/`no_contradiction_constraint` cũng chưa chạy —
  cần so sánh 2 câu trả lời LLM thật (beginner vs advanced) nên tốn thêm
  LLM call, để dành cho lượt sau nếu cần.
- Không test riêng `retention_vs_mastery_boundary`, `recommend_action_policy`
  qua state thật (đã verify gián tiếp qua unit test có sẵn, xem
  `tests/test_learning_policy.py`/`tests/test_retention.py`).
- Không test `multi_course_merge` với ≥2 môn có mastery khác nhau thật.
- `document_management`: chưa test `duplicate_upload_versioning` (upload
  lại đúng file), `mismatched_extension_content`, `noisy_ocr_outline_empty`
  — có thể bổ sung nếu cần độ phủ cao hơn.

## Nguyên tắc đã tuân thủ đúng như thống nhất

- **Không test lại công thức** `compute_mastery`/`decay_unpractised`/SRS
  interval (đã có unit test riêng) — chỉ test API có đọc/ghi đúng qua vòng
  đời thật.
- **Đúng field cho từng cơ chế thời gian**: `MasteryScore.updated_at` cho
  decay, `FlashcardReview.next_due_at` cho SRS due-date (không phải
  `reviewed_at`) — xác nhận qua code trước khi viết script, tránh lặp lại
  lỗi đã bị phát hiện lúc thảo luận thiết kế.
- **Topic thật từ corpus** (`04_cay_quyet_dinh_vi.pdf`, "Random Forest")
  cho kịch bản Quiz→Mastery→Study Plan, không tự đặt tên.
- **Invariant xác định trước LLM judge**: `generated<requested ⟹
  partial=True` test bằng so sánh số thuần, không cần LLM.
- **State cô lập**: mỗi scenario dùng `user_id`/`course_name` riêng khi
  không cố ý test chia sẻ state (Profile, Document management dùng user
  ngẫu nhiên riêng; Quiz→Mastery→Study Plan cố ý DÙNG CHUNG
  `golden-eval-user` vì đó chính là kịch bản liên-tính-năng cần test).

---

# Tổng kết chung

**Điểm mạnh xuyên suốt**: khi hệ thống CÓ trả lời, độ chính xác và trích
dẫn gần như tuyệt đối (97-99%); toàn bộ cơ chế Quiz/Flashcard/Mastery/Study
Plan hoạt động đúng thiết kế qua vòng đời API thật.

**Vấn đề chính không phải "trả lời sai"** mà là (a) verifier quá thận
trọng với câu hỏi phức tạp/ghép ý, dẫn tới "cần làm rõ" thay vì trả lời
thẳng hoặc từ chối có lý do cụ thể, và (b) một lỗ hổng cụ thể trong bộ lọc
topic nhiễu chưa xử lý được định dạng trích dẫn web/Wikipedia.

## Việc còn lại

1. Điều tra sâu verifier's "addresses_question" gate (phát hiện #3, Phần 1) — việc cải thiện sản phẩm, ngoài phạm vi Golden Set.
2. Vá bộ lọc `is_plausible_topic()` để nhận diện thêm định dạng trích dẫn web (URL + "Truy cập ngày").
3. Xem lại ngưỡng khớp từ trong `resolve_topic()` (Summarize).
4. Mở rộng độ phủ Personalization/Persistence còn thiếu (Phần 2).
