# EduTutor Golden Set — So sánh Metrics qua các mốc chạy full

File này liệt kê **toàn bộ metric đo được** trên các lần chạy ĐẦY ĐỦ (full
golden set) đã có, đặt cạnh nhau để thấy delta ở từng chỉ số. Đây thuần là
**bảng số liệu đối chiếu**; nguyên nhân gốc cho từng thay đổi xem
**[failure_analysis.md](failure_analysis.md)**, và danh sách thay đổi
code/case-set gây ra các delta này xem
`eval/golden_set/changelog/CHANGELOG.md`. Số liệu tổng hợp điều hành xem
**[evaluation_report.md](evaluation_report.md)**.

**Quy ước cập nhật file này:** mỗi khi có một mốc chạy full mới (`v2`, `v3`,
...), thêm một CỘT mới vào cuối mỗi bảng bên dưới (giữ nguyên cột
`baseline` và các cột `vN` trước đó, không xoá) và một cột `Delta` so với
mốc NGAY TRƯỚC ĐÓ. Không tạo file mới cho mỗi mốc — file này là một bảng
sống, chỉ hiện đang có 2 mốc (`baseline`, `v1`).

Nguồn dữ liệu hiện có: `eval/results/baseline/` và `eval/results/v1/`.

---

## 1. Metric tổng — Phần Q&A (`run_results.jsonl`)

| Metric | Baseline | v1 | Delta |
|---|---:|---:|---:|
| Tổng số case | 267 | 265 | -2 case (bỏ 2 case brittleness) |
| `overall_pass` (pass rate tổng) | 160/267 — 59.9% | 204/265 — 77.0% | **+17.1pp** |
| `request_ok` (gọi API thành công, không lỗi hạ tầng) | 267/267 — 100.0% | 265/265 — 100.0% | 0 |
| `grounded_as_expected` | 185/213 — 86.9% | 182/215 — 84.7% | -2.2pp (mẫu số đổi 213→215) |
| `citation_matches_expected_document` | 182/185 — 98.4% | 181/182 — 99.5% | +1.1pp |
| `content_correct_per_judge` (LLM judge) | 181/185 — 97.8% | 176/182 — 96.7% | -1.1pp |
| `abstention_type_match` (đúng loại từ chối/hỏi lại kỳ vọng) | 21/53 — 39.6% | 42/49 — 85.7% | **+46.1pp** (mẫu số đổi 53→49) |
| `false_premise_corrected_per_judge` | *(chưa có ở baseline)* | 5/5 — 100.0% | metric mới |
| `turn1_triggers_clarification` | *(chưa có ở baseline)* | 1/2 — 50.0% | metric mới |

**Ghi chú về mẫu số đổi:** `grounded_as_expected` và `abstention_type_match`
chỉ tính trên tập con case có check tương ứng áp dụng (case kỳ vọng trả lời
có căn cứ / case kỳ vọng một loại từ chối cụ thể). Mẫu số đổi giữa 2 mốc vì
một số case CHUYỂN outcome kỳ vọng-vs-thực tế giữa "nên trả lời" và "nên từ
chối/hỏi lại" khi hệ thống thay đổi hành vi (chủ yếu do cơ chế
`has_unresolved_reference` mới) — không phải do đổi case set (chỉ 2 case bị
xoá, không liên quan tới các check này).

**Metric mới** (`false_premise_corrected_per_judge`,
`turn1_triggers_clarification`) xuất hiện lần đầu ở v1 vì script chấm điểm
chỉ tạo ra các check này khi case tương ứng thực sự kích hoạt nhánh hành vi
mới (phát hiện tiền đề sai / kích hoạt hỏi lại ở lượt 1) — baseline chưa có
cơ chế này nên không có case nào sinh ra check tương ứng.

---

## 2. Pass rate theo category — Phần Q&A

| Category | Baseline | v1 | Delta |
|---|---:|---:|---:|
| abstention_clarification | 5/25 — 20.0% | 20/25 — 80.0% | **+60.0pp** |
| grounding_citation | 20/35 — 57.1% | 31/33 — 93.9% | **+36.8pp** |
| compare | 9/15 — 60.0% | 13/15 — 86.7% | **+26.7pp** |
| multi_document | 7/20 — 35.0% | 13/20 — 65.0% | **+30.0pp** |
| apply | 6/15 — 40.0% | 11/15 — 73.3% | +33.3pp |
| guardrail | 10/20 — 50.0% | 13/20 — 65.0% | +15.0pp |
| conversational | 10/25 — 40.0% | 12/25 — 48.0% | +8.0pp |
| summarize | 4/12 — 33.3% | 5/12 — 41.7% | +8.4pp |
| rag_qa | 44/45 — 97.8% | 44/45 — 97.8% | 0 |
| decomposition | 13/20 — 65.0% | 12/20 — 60.0% | **-5.0pp** |
| retrieval | 32/35 — 91.4% | 30/35 — 85.7% | **-5.7pp** |

9/11 category cải thiện hoặc giữ nguyên; 2 category đi lùi nhẹ
(`decomposition`, `retrieval`) — chi tiết case cụ thể và lý do xem
`failure_analysis.md` mục "Việc còn lại".

---

## 3. Guardrail — chi tiết theo nhóm mục đích thiết kế

| Nhóm (20 case) | Baseline | v1 | Delta |
|---|---:|---:|---:|
| False-positive cố ý (9 case) — không bị chặn nhầm | 9/9 | 9/9 | 0 |
| Hard-block cố ý (8 case) — bị chặn đúng | 8/8 | 8/8 | 0 |
| Injection tinh vi, cố ý không chặn (3 case) — giữ đúng hành vi generator | 2/3 | 2/3 | 0 |

Guardrail tự thân (quyết định chặn/không chặn) **không đổi** giữa 2 mốc —
toàn bộ delta của category `guardrail` trong bảng mục 2 (50.0%→65.0%) đến
từ các case false-positive fail vì retrieval (`insufficient_evidence`),
không phải vì guardrail chặn sai. Xem `evaluation_report.md` mục 3.2.

---

## 4. Metric tổng — Phần Hành vi (`stateful_results.jsonl`)

| Metric | Baseline | v1 | Delta |
|---|---:|---:|---:|
| Tổng scenario | 41 | 41 | 0 |
| `pass` (pass rate tổng) | 40/41 — 97.6% | 41/41 — 100.0% | +2.4pp |

### Theo nhóm

| Nhóm | Baseline | v1 | Delta |
|---|---:|---:|---:|
| Profile | 6/6 | 6/6 | 0 |
| Document management | 6/6 | 6/6 | 0 |
| Error handling | 4/4 | 4/4 | 0 |
| Quiz | 5/5 | 5/5 | 0 |
| Mastery | 3/3 | 3/3 | 0 |
| Persistence | 1/1 | 1/1 | 0 |
| Flashcard | 10/10 | 10/10 | 0 |
| Study Plan | 5/6 | 6/6 | **+1 case** |

Case duy nhất đổi chiều: `EDU-PLAN-decision_tree_topic_appears_in_plan`
(fail → pass), cùng đợt sửa heuristic trích xuất heading
(`app/ingestion/outline.py`) — xem `failure_analysis.md` Phát hiện #4.

---

## 5. Tóm tắt 1 dòng

Từ baseline đến v1: **+17.1pp pass rate Q&A** (59.9%→77.0%), **+2.4pp pass
rate hành vi** (97.6%→100.0%), độ chính xác nội dung/trích dẫn khi hệ thống
có trả lời **không đổi đáng kể** (dao động ±1.1pp, vẫn 96-100%), guardrail
tự thân **không đổi** (8/8 hard-block, 9/9 false-positive). Toàn bộ cải
thiện pass rate đến từ việc hệ thống chịu trả lời/hỏi lại đúng lúc hơn
(`abstention_type_match` +46.1pp), không phải từ việc trả lời chính xác
hơn khi đã trả lời.
