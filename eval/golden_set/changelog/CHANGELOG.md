# Changelog — Golden Set

Ghi lại các thay đổi tới `data/golden_set.jsonl` ảnh hưởng tới kết quả
đánh giá (thêm/sửa/xoá case, đổi corpus). Không ghi sửa lỗi chính tả không
ảnh hưởng kết quả chấm điểm.

## v2 — 2026-09-16 (tổng hợp thay đổi so với baseline, mốc `eval/results/v1/`)

Mục này gộp lại nhiều lần chạy trung gian (chạy thử, chạy có hồi quy rồi
sửa, resume giữa chừng) trong cùng một đợt làm việc — chi tiết từng lần
chạy trung gian không giữ lại, chỉ so sánh kết quả CUỐI CÙNG với baseline.

**Case set — 393 → 391 case (267 → 265 case Q&A):**
- Xoá EDU-GRD-033, EDU-GRD-035 (subcategory `invalid_citation_index`). Cả
  hai chỉ kiểm chứng được bằng cách ép câu trả lời thô của LLM từ một chuỗi
  dựng sẵn, không thể tái hiện qua API thật — chuyển thành 2 unit test trực
  tiếp gọi `answer_question()` với `FakeLLMClient`, xem
  `tests/test_rag.py::TestCitationIndexValidation`. Hành vi thật của hệ
  thống (`_strip_invalid_citations` + fallback `NOT_GROUNDED_MESSAGE` khi 0
  citation hợp lệ còn lại) không đổi — đây thuần là chuyển chỗ kiểm chứng,
  không phải phát hiện bug sản phẩm.

**Hạ tầng test đã sửa (không phải bug sản phẩm):**
- Dựng scope riêng cho 8 case `out_of_scope` (EDU-ABS-016..023): corpus gốc
  gom cả 13 tài liệu vào CHUNG 1 course (`GoldenSetEval`) nên ranh giới "chỉ
  1 tài liệu trong phạm vi" mà 8 case này giả định chưa từng tồn tại khi
  chạy. Đã upload lại 5 tài liệu cần thiết vào 5 course riêng
  (`eval/scripts/upload_scoped_docs.py`, mapping tại
  `sources/scoped_course_mapping.json`) và sửa `run_golden_set.py` tự động
  định tuyến 8 case này về đúng course hẹp. Kết quả: 8/8 pass — xác nhận
  ranh giới phạm vi tài liệu vốn đã hoạt động đúng, chỉ là hạ tầng test
  thiếu.
- `run_golden_set.py` thiếu `load_dotenv()` khiến check
  `content_correct_per_judge` bị bỏ qua âm thầm khi chạy như tiến trình
  Python riêng (không thấy được API key từ `.env` gốc) — đã thêm
  `load_dotenv()` đúng vị trí.
- `run_stateful_scenarios.py` crash `UnicodeEncodeError` khi in tiếng Việt
  ra stdout bị redirect trên Windows (codepage cp1252) — đã ép
  `sys.stdout`/`sys.stderr` dùng UTF-8.

**Bug sản phẩm thật đã sửa:**
- `has_unresolved_reference()` (`backend/app/retrieval/query_context.py`)
  — cơ chế mới phát hiện câu hỏi có đại từ/tham chiếu chưa rõ ràng để hỏi
  lại làm rõ thay vì trả lời liều theo một khả năng. Đây là thay đổi lớn
  nhất so với baseline — giải quyết phần lớn Phát hiện #1 trong
  `eval/reports/failure_analysis.md` (baseline: hệ thống không có bước
  phát hiện câu hỏi mơ hồ độc lập): `abstention_clarification` tăng từ
  20.0% (baseline) lên 80.0%. Bản vá đầu của cơ chế này từng gây hồi quy
  giả-dương trên câu hỏi ghép có tiền ngữ (antecedent) ngay trong CÙNG câu
  hỏi — đã sửa bằng ngoại lệ `_has_named_antecedent_in_question()` (mệnh đề
  trước đại từ ≥7 từ thô thì coi là đã nêu tên chủ thể, ngưỡng chọn dựa
  trên đối chiếu true positive gần nhất và false positive xa nhất). Còn 1
  khoảng trống cố ý chưa sửa: EDU-RET-002 ("Why do trees **that** are grown
  very deep...?" — "that" làm đại từ quan hệ với mệnh đề trước rất ngắn,
  `ANAPHORA_RE` chưa phân biệt được với "that" hồi chỉ thật; không sửa vì
  tái cấu trúc `ANAPHORA_RE` từng gây hồi quy 1 lần, rủi ro cao hơn lợi ích
  cho đúng 1 case đã biết).
- Heuristic trích xuất heading (`backend/app/ingestion/outline.py`, Phát
  hiện #2 và #4 trong `failure_analysis.md`): thêm bộ lọc URL (`_URL_RE`)
  và câu văn mở đầu bằng số thập phân viết thường
  (`_NUMBERED_LOWERCASE_BODY_RE`), mở rộng `_WEB_CITATION_RE` để bắt cả
  "Truy cập" đứng cuối dòng bị cắt ngắn. Cải thiện một phần —
  `summarize` tăng từ 33.3% lên 41.7%, vẫn là category yếu nhất, chưa giải
  quyết dứt điểm.

**Vấn đề còn lại, mới ghi nhận ở mốc này (chưa sửa):**
- EDU-GRD2-007 (câu hỏi hợp lệ có kèm lệnh chèn trong nội dung tài liệu —
  indirect injection): hệ thống từ chối oan ("không phải câu hỏi học tập
  hợp lệ") thay vì trả lời bình thường và bỏ qua lệnh chèn như thiết kế dự
  định. Case này fail giống hệt ở cả baseline lẫn mốc này (không phải hồi
  quy mới) nhưng chưa từng được ghi nhận trong `failure_analysis.md` trước
  đây.
- EDU-RET-015: fail mới so với baseline, chưa điều tra nguyên nhân.

**Kết quả cuối cùng so với baseline** (số liệu đầy đủ:
`eval/reports/evaluation_report.md`; kết quả thô: `eval/results/v1/`):

| | Baseline | v1 |
|---|---:|---:|
| Q&A pass rate | 160/267 (59.9%) | 204/265 (77.0%) |
| `grounded_as_expected` | 185/213 (86.9%) | 182/215 (84.7%) |
| Citation accuracy | 182/185 (98.4%) | 181/182 (99.5%) |
| Content correctness (judge) | 181/185 (97.8%) | 176/182 (96.7%) |
| Hành vi (kịch bản) | 40/41 | 41/41 |

Bài học quy trình (không ảnh hưởng kết quả): quy trình kiểm tra "còn quota
Cohere không" trước khi chạy full run từng kết luận SAI dựa vào field
`billed_units` trong response của 1 lệnh gọi thử nghiệm — field này xuất
hiện ở CẢ key trial, không phải dấu hiệu key trả phí/không giới hạn. Header
đúng để kiểm tra là
`x-trial-endpoint-call-limit`/`x-trial-endpoint-call-remaining` (có sẵn
trong mọi response, không cần đoán).

## v1 — 2026-09-14 (bản gốc)

- 393 case: 267 Q&A (rag_qa, retrieval, grounding_citation,
  abstention_clarification, conversational, decomposition, multi_document,
  compare, summarize, apply, guardrail) + 126 hành vi (document_management,
  persistence, error_handling, personalization, mastery, quiz, flashcard,
  study_plan, profile).
- Corpus: 13 tài liệu Wikipedia độc lập (`eval/corpus/`).
- Kết quả đo lần đầu: `eval/results/baseline/` — xem
  `eval/reports/evaluation_report.md` cho số liệu đầy đủ.
- Vấn đề đã biết trong chính bộ case (chưa sửa, ghi nhận để theo dõi):
  khoảng 10 case có tiền đề bị lỗi trong định nghĩa case (không phải lỗi hệ
  thống) — xem `annotations/annotation_guidelines.md`.
