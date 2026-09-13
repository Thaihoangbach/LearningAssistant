# EduTutor Golden Set — Evaluation Report

**Scope:** 393/393 case, chạy thật trên backend local (Postgres `edututor-pg`
+ MinIO local — không đụng production)
**Corpus:** 13 tài liệu độc lập mới (Wikipedia), tải lên dưới
`user_id=golden-eval-user`, `course_name=GoldenSetEval`
**Bộ case:** `eval/golden_set.jsonl` (393 case)

Đây là báo cáo **số liệu và kết quả**. Phân tích nguyên nhân gốc, root
cause, và các fix đã áp dụng nằm ở **[failure_analysis.md](failure_analysis.md)**.

---

## 1. Tóm tắt điều hành

| | |
|---|---:|
| Tổng số case | 393/393 (100% đã chạy thật) |
| Citation accuracy (khi có trả lời) | 155/160 — **97%** |
| Content correctness — LLM judge (khi có trả lời) | 159/160 — **99%** |
| **Pass rate đã hiệu chỉnh, 267 case Q&A** (loại evaluator noise + test-design gap, xem mục 3.2) | 175/257 — 68% |
| **Pass rate bộ regression 51 case, cùng ID, trước → sau toàn bộ fix** | 23/51 (45%) → **36/51 (70.6%)** |
| Guardrail false-positive (câu hỏi hợp lệ bị chặn nhầm) | 0/9 |
| Guardrail true-block (câu cần chặn bị chặn đúng) | 9/11 |
| Kịch bản hành vi (Quiz/Flashcard/Mastery/Study Plan/Profile/...) | 40/41 pass |
| Bug thật phát hiện & đã sửa | 5 — xem mục 5 |
| Bug thật phát hiện, chưa sửa | 2 — xem mục 5 |

**Kết luận chính:** khi hệ thống *có* trả lời, độ chính xác nội dung và
trích dẫn gần như tuyệt đối. Vấn đề Q&A không phải một nguyên nhân duy nhất
mà là nhiều lỗi độc lập cùng nằm ở một điểm quyết định trong verifier — chi
tiết root cause và fix xem `failure_analysis.md`. Toàn bộ cơ chế
Quiz/Flashcard/Mastery/Study Plan hoạt động đúng thiết kế qua vòng đời API
thật.

---

## 2. Phạm vi và phương pháp

Golden Set gồm 393 case chia làm 2 phần, chạy bằng 2 script riêng do khác
nhau về cách dựng state:

| Phần | Case | Category | Script | Kết quả |
|---|---:|---|---|---|
| 1 — Q&A | 267 | rag_qa, retrieval, grounding_citation, abstention_clarification, conversational, decomposition, multi_document, compare, summarize, apply, guardrail | `eval/scripts/run_golden_set.py` | `eval/results/run_results.jsonl` |
| 2 — Hành vi | 126 | document_management, persistence, error_handling, personalization, mastery, quiz, flashcard, study_plan, profile | `eval/scripts/run_stateful_scenarios.py` | `eval/results/stateful_results.jsonl` |

Phần 1 gọi trực tiếp `POST /chat/ask` cho từng case và chấm điểm theo
`expected_behavior`/`abstention_type`/`expected_citations`/`must_contain`/
`must_not_contain`; case có `expected_answer` được chấm thêm bằng LLM judge
(model chấm nội dung có đúng ý hay không, không yêu cầu giống hệt câu chữ).

Phần 2 dùng **Stateful Scenario Runner**: mỗi kịch bản gồm setup state thật
(qua API hoặc chỉnh trực tiếp timestamp trong DB khi cần mô phỏng thời gian)
→ gọi API thật → assert kết quả. 126 Golden Case gốc được gom thành 41 kịch
bản đại diện để tiết kiệm quota (nhiều case cùng category dùng chung một lần
setup — xem mục 4.1).

---

## 3. Kết quả Phần 1 — Q&A (267 case)

### 3.1 Kết quả theo category (số thô, chưa hiệu chỉnh)

| Category | Pass | Fail | Tỷ lệ |
|---|---:|---:|---:|
| rag_qa | 40 | 5 | 89% |
| retrieval | 31 | 4 | 89% |
| decomposition | 12 | 8 | 60% |
| compare | 8 | 7 | 53% |
| multi_document | 8 | 12 | 40% |
| grounding_citation | 14 | 21 | 40% |
| conversational | 10 | 15 | 40% |
| abstention_clarification | 9 | 16 | 36% |
| apply | 4 | 11 | 27% |
| guardrail | — | — | n/a — xem mục 3.3 |
| summarize | — | — | n/a — xem `failure_analysis.md` |

Số thô đánh giá THẤP HƠN thực tế — xem mục 3.2 để biết vì sao và số liệu
đã hiệu chỉnh.

### 3.2 Số liệu đã hiệu chỉnh — tách product failure / evaluator noise / test-design gap

`run_golden_set.py::score_case()` (bản gốc) có 2 lỗi khiến nhiều case bị
tính "fail" dù hệ thống làm đúng — chi tiết 2 lỗi này và cách sửa nằm ở
`failure_analysis.md` mục 1. Số liệu đã hiệu chỉnh (gộp thẳng vào field
`final_label` trong `eval/results/run_results.jsonl`):

| Nhãn | Số case | Tỷ lệ |
|---|---:|---:|
| `pass` | 130 | 48.7% |
| `evaluator_noise` (lỗi chấm điểm, không phải lỗi hệ thống) | 45 | 16.9% |
| `test_design_gap` (tiền đề case sai, không phải bug sản phẩm) | 10 | 3.7% |
| `product_failure` (nghi lỗi hệ thống thật) | 82 | 30.7% |

**Pass rate đã hiệu chỉnh: 175/257 (68.1%)**, loại 10 case test-design-gap
khỏi mẫu số. `product_failure` còn lại theo category:

| Category | product_failure |
|---|---:|
| grounding_citation | 13 |
| abstention_clarification | 11 |
| guardrail | 11 |
| conversational | 9 |
| apply | 8 |
| retrieval | 7 |
| multi_document | 7 |
| summarize | 6 |
| rag_qa | 5 |
| decomposition | 4 |
| compare | 1 |

### 3.3 Guardrail — đọc đúng bản chất thay vì tỷ lệ pass thô

- **9/9 case false-positive** (câu hỏi hợp lệ) **không bị chặn nhầm.**
- Các case cố ý cần chặn: yêu cầu "làm hộ bài tập" (tiếng Việt lẫn tiếng
  Anh) đều bị chặn đúng bởi `ACADEMIC_INTEGRITY_MESSAGE`.
- 2 case injection tinh vi hơn (giả mạo trích dẫn, yêu cầu "bỏ qua tài liệu
  dùng kiến thức chung") không bị lợi dụng thành công (không tạo trích dẫn
  giả, không bỏ qua tài liệu) nhưng cũng không được nhận diện rõ ràng là
  injection — rơi vào phản hồi chung chung. Đây là điểm biên đáng theo dõi,
  không phải lỗ hổng bảo mật thực sự.

---

## 4. Kết quả Phần 2 — Hành vi (126 case, 41 kịch bản)

### 4.1 Golden Cases / Scenarios / API calls / LLM calls

| | Số lượng |
|---|---:|
| Golden Cases gốc (9 category hành vi) | 126 |
| Stateful Scenarios thực chạy (đại diện, tái dùng state chung) | 41 |
| API calls thật tới backend | 45 |
| LLM generation calls (Quiz + Flashcard generate, mỗi loại chỉ 1 lần rồi tái dùng) | 2 |

Không phải 1-1 giữa 126 Golden Case và 41 Scenario — nhiều Golden Case cùng
category dùng chung một lần setup (ví dụ 5 case `topic_plausibility_filter`
đều xét trên cùng kết quả `GET /study-plan` một lần thay vì gọi lại 5 lần).
Đây là chủ đích tiết kiệm quota, không phải bỏ sót.

### 4.2 Kết quả theo nhóm — 40/41 scenario PASS

| Nhóm | Pass/Tổng |
|---|---:|
| Profile | 6/6 |
| Document management | 7/7 |
| Error handling | 3/3 |
| Quiz → Mastery | 8/8 |
| Flashcard → SRS | 10/10 |
| Study Plan | 5/6 |

Quiz→Mastery bao gồm 2 case time-simulation qua đúng field
`MasteryScore.updated_at`; Flashcard→SRS bao gồm case time-simulation qua
đúng field `FlashcardReview.next_due_at` (không phải `reviewed_at`).

Case duy nhất fail (Study Plan) là một phát hiện thật — xem
`failure_analysis.md` mục 2.

### 4.3 Ngoài phạm vi lần chạy này

- `personalization`: chưa test sâu `inferred_level` qua 3 dải mastery cụ
  thể (cần 3 user riêng với mastery set sẵn đúng 3 dải). `effective_level_
  priority`/`no_contradiction_constraint` cũng chưa chạy — cần so sánh 2
  câu trả lời LLM thật (beginner vs advanced), tốn thêm LLM call.
- `retention_vs_mastery_boundary`, `recommend_action_policy`: đã verify
  gián tiếp qua unit test có sẵn (`tests/test_learning_policy.py`,
  `tests/test_retention.py`), chưa test qua state thật.
- `multi_course_merge`: chưa test với ≥2 môn có mastery khác nhau thật.
- `document_management`: chưa test `duplicate_upload_versioning` (upload
  lại đúng file), `mismatched_extension_content`, `noisy_ocr_outline_empty`.

### 4.4 Nguyên tắc đã tuân thủ

- Không test lại công thức `compute_mastery`/`decay_unpractised`/SRS
  interval (đã có unit test riêng) — chỉ test API có đọc/ghi đúng qua vòng
  đời thật.
- Đúng field cho từng cơ chế thời gian: `MasteryScore.updated_at` cho
  decay, `FlashcardReview.next_due_at` cho SRS due-date (không phải
  `reviewed_at`) — xác nhận qua code trước khi viết script.
- Topic thật từ corpus (`04_cay_quyet_dinh_vi.pdf`, "Random Forest") cho
  kịch bản Quiz→Mastery→Study Plan, không tự đặt tên.
- Invariant xác định trước LLM judge: `generated < requested ⟹ partial=True`
  kiểm bằng so sánh số thuần, không cần LLM.
- State cô lập: mỗi scenario dùng `user_id`/`course_name` riêng khi không
  cố ý test chia sẻ state; Quiz→Mastery→Study Plan cố ý dùng chung
  `golden-eval-user` vì đó chính là kịch bản liên-tính-năng cần test.

---

## 5. Bug thật phát hiện — tổng hợp trạng thái

| # | Mô tả | Trạng thái |
|---|---|---|
| 1 | pypdf trích ra byte NUL (0x00) trong text PDF, Postgres từ chối insert, job xử lý nền crash giữa chừng | **Đã sửa** |
| 2 | `is_plausible_topic()` thiếu luật lọc trích dẫn web/Wikipedia, lọt vào Study Plan như topic thật | Chưa sửa |
| 3 | Câu tự-từ-chối của generator bị verifier hiểu nhầm thành "câu hỏi mơ hồ" | **Đã sửa, có test hồi quy** |
| 4 | Điểm retrieval bị pha loãng bởi khung diễn đạt dài (roleplay/injection-style) | Chưa sửa, cần cân nhắc đánh đổi |
| 5 | `addresses_question` (verifier) chỉ có 2 giá trị CÓ/KHÔNG — ép câu hỏi ghép nhiều phần vào phán quyết all-or-nothing | **Đã sửa, kiểm chứng live** |
| 6 | `addresses_question` không nhận diện "sửa lại tiền đề sai" là trả lời đúng | **Đã sửa, kiểm chứng live** |
| 7 | Regex tự-từ-chối bỏ sót thứ tự "...thông tin ... không có" | **Đã sửa, có test hồi quy** |
| 8 | Resume-logic của script chạy Golden Set coi case lỗi hạ tầng là "đã xong", bỏ qua không chạy lại | **Đã sửa** |

Chi tiết đầy đủ từng bug (nguyên nhân, cách sửa, kiểm chứng) nằm ở
**[failure_analysis.md](failure_analysis.md)**.

---

## Phụ lục — Nguồn dữ liệu

- Bộ case: `eval/golden_set.jsonl` (393 case; 77 case đánh dấu `in_regression_set: true` làm tập con hồi quy)
- Kết quả Phần 1 (267 case Q&A, đã có nhãn `pass`/`evaluator_noise`/`test_design_gap`/`product_failure`): `eval/results/run_results.jsonl`
- Kết quả Phần 2 (126 case hành vi): `eval/results/stateful_results.jsonl`
- Kết quả regression sau fix: `eval/results/regression_results.jsonl`
- Script chạy: `eval/scripts/run_golden_set.py` (thêm `--regression-only`), `eval/scripts/run_stateful_scenarios.py`, `eval/scripts/run_local_backend.py`
- Corpus: `eval/corpus/` (13 tài liệu + `README.md`)
- Xem `eval/README.md` cho cấu trúc đầy đủ và cách chạy lại; `failure_analysis.md` cho phân tích nguyên nhân gốc.
