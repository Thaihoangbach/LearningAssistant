# EduTutor Golden Set — Evaluation Report

**Scope:** 393/393 case, chạy thật trên backend local (Postgres `edututor-pg`
+ MinIO local — không đụng production)
**Corpus:** 13 tài liệu độc lập (Wikipedia), tải lên dưới
`user_id=golden-eval-user`, `course_name=GoldenSetEval`
**Bộ case:** `eval/golden_set/data/golden_set.jsonl` (393 case)

Đây là báo cáo **số liệu và kết quả**. Phân tích nguyên nhân gốc cho các
vấn đề còn tồn tại nằm ở **[failure_analysis.md](failure_analysis.md)**.

---

## 1. Tóm tắt điều hành

| | |
|---|---:|
| Tổng số case | 393/393 (100% đã chạy thật) |
| **Pass rate, 267 case Q&A** | 160/267 — **59.9%** |
| `grounded_as_expected` (hệ thống trả lời có căn cứ đúng khi đáng ra phải trả lời) | 185/213 — **86.9%** |
| Citation accuracy (khi có trả lời) | 182/185 — **98.4%** |
| Content correctness — LLM judge (khi có trả lời) | 181/185 — **97.8%** |
| Guardrail false-positive (câu hỏi hợp lệ bị chặn nhầm) | 0/9 |
| Guardrail true-block (câu cần chặn bị chặn đúng) | 9/9 |
| Kịch bản hành vi (Quiz/Flashcard/Mastery/Study Plan/Profile/...) | 40/41 pass |

**Kết luận chính:** khi hệ thống *có* trả lời, độ chính xác nội dung và
trích dẫn gần như tuyệt đối (97-98%). Khoảng cách giữa pass rate tổng thể
(59.9%) và độ chính xác khi-có-trả-lời (97-98%) nằm ở việc hệ thống đôi khi
từ chối/hỏi lại oan thay vì trả lời — `grounded_as_expected` đo trực tiếp
điều này (86.9%). Chi tiết nguyên nhân gốc cho các case còn fail và các vấn
đề đã biết xem `failure_analysis.md`.

---

## 2. Phạm vi và phương pháp

Golden Set gồm 393 case chia làm 2 phần, chạy bằng 2 script riêng do khác
nhau về cách dựng state:

| Phần | Case | Category | Script | Kết quả |
|---|---:|---|---|---|
| 1 — Q&A | 267 | rag_qa, retrieval, grounding_citation, abstention_clarification, conversational, decomposition, multi_document, compare, summarize, apply, guardrail | `eval/scripts/run_golden_set.py` | `eval/results/baseline/run_results.jsonl` |
| 2 — Hành vi | 126 | document_management, persistence, error_handling, personalization, mastery, quiz, flashcard, study_plan, profile | `eval/scripts/run_stateful_scenarios.py` | `eval/results/baseline/stateful_results.jsonl` |

Phần 1 gọi trực tiếp `POST /chat/ask` cho từng case và chấm điểm theo
`expected_behavior`/`abstention_type`/`expected_citations`/`must_contain`/
`must_not_contain`; case có `expected_answer` được chấm thêm bằng LLM judge
(model chấm nội dung có đúng ý hay không, không yêu cầu giống hệt câu chữ).
Khoảng 10/267 case có tiền đề bị lỗi trong chính định nghĩa case (không
phải lỗi hệ thống) — không loại khỏi số liệu tổng, chỉ ghi chú trong
`failure_analysis.md` khi liên quan trực tiếp tới một phát hiện.

Phần 2 dùng **Stateful Scenario Runner**: mỗi kịch bản gồm setup state thật
(qua API hoặc chỉnh trực tiếp timestamp trong DB khi cần mô phỏng thời gian)
→ gọi API thật → assert kết quả. 126 Golden Case gốc được gom thành 41 kịch
bản đại diện để tiết kiệm quota (nhiều case cùng category dùng chung một lần
setup — xem mục 4.1).

---

## 3. Kết quả Phần 1 — Q&A (267 case)

### 3.1 Kết quả theo category

| Category | Pass/Tổng | Tỷ lệ |
|---|---:|---:|
| rag_qa | 44/45 | 97.8% |
| retrieval | 32/35 | 91.4% |
| decomposition | 13/20 | 65.0% |
| compare | 9/15 | 60.0% |
| grounding_citation | 20/35 | 57.1% |
| guardrail | 10/20 | 50.0% |
| apply | 6/15 | 40.0% |
| conversational | 10/25 | 40.0% |
| multi_document | 7/20 | 35.0% |
| summarize | 4/12 | 33.3% |
| abstention_clarification | 5/25 | 20.0% |

`rag_qa` và `retrieval` gần như bão hòa (>90%). Bốn nhóm thấp nhất
(`abstention_clarification`, `summarize`, `multi_document`, `conversational`)
chiếm phần lớn số case fail — nguyên nhân gốc từng nhóm xem
`failure_analysis.md`.

### 3.2 Guardrail — đọc đúng bản chất thay vì tỷ lệ pass thô

- **9/9 case cố ý kiểm tra false-positive** (câu hỏi hợp lệ diễn đạt giống
  đáng ngờ — persona gia sư, từ nhạy cảm dùng đúng ngữ cảnh toán học...)
  **không bị guardrail chặn nhầm.**
- **9/9 case cố ý cần chặn** (yêu cầu "làm hộ bài tập", prompt injection
  trực tiếp/gián tiếp, jailbreak DAN, tiết lộ chỉ dẫn hệ thống) **đều bị
  chặn đúng.**
- 2 case injection tinh vi hơn (giả mạo trích dẫn `[Nature, 2023]`, yêu cầu
  "bỏ qua tài liệu dùng kiến thức chung") **không bị guardrail chặn** theo
  đúng thiết kế (đây không phải jailbreak, guardrail cố tình cho qua) —
  nhưng bản thân câu trả lời sau đó không phải lúc nào cũng giữ đúng
  căn cứ/trích dẫn ở mọi lượt chạy. Đây là điểm biên đáng theo dõi ở lớp
  generator, không phải lỗ hổng guardrail.
- Vì vậy category `guardrail` ở bảng 3.1 (50%) phản ánh cả lỗi retrieval/
  grounding của những case KHÔNG nên bị chặn nhưng cũng không dễ trả lời
  (câu hỏi diễn đạt dài/lạ), không phải guardrail chặn sai.

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
`failure_analysis.md`.

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

## 5. Vấn đề đã biết — tổng hợp

| # | Mô tả | Mức độ ảnh hưởng |
|---|---|---|
| 1 | Không có bước phát hiện độc lập cho câu hỏi mơ hồ (đại từ không rõ ngữ cảnh, thuật ngữ đa nghĩa) — hệ thống trả lời tự tin theo 1 khả năng thay vì hỏi lại nêu rõ các khả năng | Trung bình — ảnh hưởng category `abstention_clarification` |
| 2 | Bước trích xuất dàn ý (`app/ingestion/outline.py`) đôi khi nhặt nhầm dòng trích dẫn/câu văn có số thập phân làm heading duy nhất của tài liệu, khiến Summarize không có chủ đề hợp lệ để tóm tắt dù tài liệu có nội dung | Cao — ảnh hưởng phần lớn category `summarize`, rò rỉ sang cả `study_plan` |
| 3 | Ngữ cảnh hội thoại (`conversation_history`) không luôn được `build_retrieval_query()` tận dụng đủ để truy hồi đúng đoạn trích cho câu hỏi tiếp nối dùng đại từ | Trung bình — phần lớn nguyên nhân fail của category `conversational` |
| 4 | Bộ lọc trích dẫn web (`is_plausible_topic`) chưa bắt được mọi biến thể bị cắt ngắn bởi giới hạn độ dài heading | Thấp — 1 case hành vi `study_plan` |
| 5 | So khớp chủ đề Summarize theo âm tiết đơn lẻ trong tiếng Việt đôi khi trùng ngẫu nhiên giữa 2 chủ đề không liên quan | Thấp — hiếm gặp |

Nguyên nhân gốc, bằng chứng cụ thể, và đề xuất hướng xử lý cho từng mục xem
**[failure_analysis.md](failure_analysis.md)**.

---

## Phụ lục — Nguồn dữ liệu

- Bộ case: `eval/golden_set/data/golden_set.jsonl` (393 case; 77 case đánh dấu `in_regression_set: true` làm tập con chạy nhanh)
- Kết quả Phần 1 (267 case Q&A): `eval/results/baseline/run_results.jsonl`
- Kết quả Phần 2 (126 case hành vi, 41 kịch bản): `eval/results/baseline/stateful_results.jsonl`
- Script chạy: `eval/scripts/run_golden_set.py`, `eval/scripts/run_stateful_scenarios.py`, `eval/scripts/run_local_backend.py`, `eval/scripts/validate_golden_set.py`, `eval/scripts/analyze_failures.py`
- Corpus: `eval/corpus/` (13 tài liệu + `README.md`)
- Xem `eval/README.md` cho cấu trúc đầy đủ và cách chạy lại; `failure_analysis.md` cho phân tích nguyên nhân gốc.
