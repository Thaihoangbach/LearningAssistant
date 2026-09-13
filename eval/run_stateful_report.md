# Golden Set — Stateful Scenario Report (126 case hành vi, chạy thật)

Bổ sung cho `eval/run_report.md` (267 case `/chat/ask`). Chạy 41 kịch bản
stateful qua `eval/run_stateful_scenarios.py`, mỗi kịch bản đi qua đúng
vòng đời API thật (setup → API actions → verification → assertions), map
tới 1 hoặc nhiều trong số 126 Golden Case gốc theo category/subcategory
tương ứng. Không insert business value thẳng vào DB ở bất kỳ bước nào.

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
