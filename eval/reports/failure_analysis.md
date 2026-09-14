# EduTutor Golden Set — Failure Analysis

Phân tích nguyên nhân gốc (root cause) cho các case fail trong
**[evaluation_report.md](evaluation_report.md)**. Đọc file đó trước để có
số liệu tổng quan.

---

## 1. Tổng quan

Khi hệ thống *có* trả lời, độ chính xác nội dung và trích dẫn gần như
tuyệt đối (97-98%). Toàn bộ vấn đề còn lại nằm ở việc hệ thống **có chịu
trả lời hay không** — `grounded_as_expected` (185/213, 86.9%) đo trực tiếp
điều này. Bốn phát hiện dưới đây giải thích phần lớn khoảng cách còn lại.

---

## 2. Phát hiện #1 — Không có bước phát hiện độc lập cho câu hỏi mơ hồ

**Category ảnh hưởng:** `abstention_clarification` (5/25 pass, 20%).

Hệ thống hiện đánh giá độ liên quan của câu hỏi qua verifier's
`addresses_question` — một phán quyết dựa trên ĐOẠN TRÍCH đã truy hồi được,
không có bước riêng kiểm tra "câu hỏi này có tự nó đủ rõ nghĩa không" TRƯỚC
khi truy hồi. Hệ quả: với câu hỏi dùng đại từ không có gì để bám ("Nó hoạt
động thế nào?", "Cái đó dùng để làm gì?", "Ai đã phát minh ra nó?") hoặc
thuật ngữ có nhiều nghĩa hợp lệ trong kho tài liệu (vd "Kernel là gì?" — có
thể là bộ lọc CNN hoặc kernel method trong Random Forest), hệ thống truy
hồi theo đúng TỪ trong câu hỏi, tìm được MỘT đoạn trích có vẻ liên quan, và
trả lời tự tin theo đúng đoạn đó — mà không nhận ra còn ít nhất một khả
năng khác hợp lệ không kém.

Case cụ thể: `EDU-ABS-008/009/010/012/013/014` — tất cả thuộc subcategory
`ambiguous_question`/`missing_context_pronoun`/`multiple_possible_referents`.
Hành vi hiện tại AN TOÀN (không bịa, luôn có căn cứ cho những gì nó nói)
nhưng không lý tưởng — đúng ra nên hỏi lại nêu rõ các khả năng thay vì chọn
một cách ngầm định.

**Hướng xử lý khả dĩ:** thêm một bước so sánh cluster chunk theo tài liệu
TRƯỚC khi generation — nếu top-k chunk trải đều trên ≥2 tài liệu/chủ đề
không liên quan nhau, hỏi lại nêu tên các khả năng thay vì chọn một. Đánh
đổi thật: thêm độ trễ/1 lượt gọi LLM cho MỌI câu hỏi (không chỉ câu mơ hồ),
và rủi ro false-positive hỏi lại khi câu hỏi thực ra không mơ hồ. Cần quyết
định trước khi xây.

---

## 3. Phát hiện #2 — Bước trích xuất dàn ý chưa đủ tốt cho văn bản có nhiều trích dẫn/số liệu

**Category ảnh hưởng:** `summarize` (4/12 pass, 33%), rò rỉ sang
`study_plan` (1 kịch bản hành vi fail).

Tính năng Tóm tắt dựa vào `DocumentTopic` — heading được trích xuất lúc
tải tài liệu lên (`app/ingestion/outline.py`, heuristic
`_NUMBERED_SECTION_RE`: coi dòng dạng "số + dấu chấm + text" là heading).
Với văn bản Wikipedia tiếng Anh có nhiều trích dẫn/chú thích số, heuristic
này thường xuyên nhặt NHẦM dòng KHÔNG PHẢI heading thật:

- Doc `random_forest`: `DocumentTopic` DUY NHẤT trích ra được có title
  `"31. Aug. 2023"` — một ngày trích dẫn trong danh mục tham khảo.
- Doc `precision_and_recall`: `DocumentTopic` DUY NHẤT có title `"1.0 for
  a class C means that every item"` — một câu văn bị hiểu nhầm số thập
  phân "1.0" thành mục lục đánh số.
- Doc `reinforcement_learning`: `DocumentTopic` DUY NHẤT là một dòng trích
  dẫn học thuật đầy đủ tên tác giả/năm.
- Doc `dich_may_bang_no_ron`: CẢ 2 `DocumentTopic` đều là trích dẫn web
  (tiếng Nga và tiếng Việt, kiểu `"...". domain.net. Truy cập...`).

Bộ lọc chất lượng ở điểm tiêu thụ (`is_plausible_topic()`) loại được phần
lớn nhưng không phải tất cả — một số dòng trích dẫn/câu văn có số thập phân
vẫn đủ "sạch" về mặt cú pháp (không dấu phẩy, không ISBN/DOI, tỉ lệ chữ cái
đủ cao) để qua được bộ lọc dù không phải heading thật. Kết quả: nhiều tài
liệu KHÔNG có một chủ đề hợp lệ nào để tóm tắt, dù bản thân tài liệu có nội
dung — Summarize trả `NEEDS_TOPIC_MESSAGE` dù đáng ra phải tóm tắt được.
Vấn đề nằm ở TRÍCH XUẤT, không phải ở bước khớp chủ đề (`resolve_topic()`
hoạt động đúng — trả None khi không có candidate hợp lệ).

Tác động rò rỉ sang Study Plan: các dòng trích dẫn/câu văn lọt qua bộ lọc
này cũng xuất hiện như "chủ đề cần học" trong kế hoạch ôn tập.

**Hướng xử lý khả dĩ:** siết lại `_NUMBERED_SECTION_RE`/`is_plausible_topic()`
cho trường hợp cụ thể này — vd loại số thập phân dạng "N.N" theo sau bởi
chữ thường (dấu hiệu câu văn, không phải mục lục), và mở rộng nhận diện
trích dẫn web sang các biến thể ngôn ngữ khác ngoài tiếng Việt/Anh đã có.
Phạm vi rộng hơn một fix hẹp — cần khảo sát thêm trên corpus đa dạng hơn
trước khi sửa để tránh siết nhầm heading thật.

---

## 4. Phát hiện #3 — Theo dõi ngữ cảnh hội thoại qua nhiều lượt chưa ổn định

**Category ảnh hưởng:** `conversational` (10/25 pass, 40%).

Phần lớn case fail (6/15 case fail) nhận `NO_CONTEXT`/`NOT_GROUNDED` dù
lượt hỏi trước đó đã xác định đúng chủ đề — câu hỏi tiếp nối dùng đại từ
("Nó có mấy loại phổ biến?", "Cái đó hoạt động theo cơ chế nào?") không
luôn được `build_retrieval_query()` nối đủ ngữ cảnh từ lượt trước để truy
hồi ra đúng đoạn trích. Đây là biến thể "trong hội thoại" của Phát hiện #1
— khác ở chỗ ngữ cảnh CÓ SẴN (trong `conversation_history`) nhưng không
được tận dụng nhất quán để dựng truy vấn truy hồi. Số case còn lại fail vì
lý do khác (judge/citation không khớp một phần câu trả lời hợp lệ) — không
cùng một nguyên nhân, cần xem từng case cụ thể nếu muốn sửa tiếp.

---

## 5. Phát hiện #4 — Các kẽ hở nhỏ, ảnh hưởng thấp

- **Trích dẫn web bị cắt ngắn:** `is_plausible_topic()`'s
  `_WEB_CITATION_RE` yêu cầu cụm "Truy cập ngày" liền nhau; khi dòng
  heading bị cắt ngắn bởi giới hạn độ dài đúng trước từ "ngày" (còn lại
  "...Truy cập"), regex không khớp được và dòng đó lọt qua bộ lọc. Fix
  nhỏ: chấp nhận riêng "Truy cập" đứng cuối dòng không cần "ngày" theo sau.
- **So khớp chủ đề Summarize theo âm tiết đơn lẻ (tiếng Việt):** ngưỡng
  hiện tại (≥2 từ nội dung trùng giữa câu hỏi và preview một chủ đề) vẫn có
  thể trùng ngẫu nhiên vì tiếng Việt viết rời từng âm tiết (vd "liệu" trong
  "dữ liệu" trùng với "liệu" tách từ "tài liệu"; "quy" trong "chính quy"
  trùng với "quy" trong "Hồi quy"). Hiếm gặp nhưng có thể khớp nhầm sang
  chủ đề không liên quan khi câu hỏi hoàn toàn không có chủ đề hợp lệ nào.

---

## 6. Việc còn lại, theo mức ưu tiên đề xuất

1. Quyết định hướng cho Phát hiện #1 (phát hiện câu hỏi mơ hồ độc lập) —
   cần chốt trước vì ảnh hưởng độ trễ/chi phí của MỌI câu hỏi, không chỉ
   câu mơ hồ.
2. Cải thiện heuristic trích xuất heading cho Phát hiện #2 — tác động lớn
   nhất tới Summarize, cần khảo sát thêm trên corpus đa dạng trước khi sửa.
3. Xem lại cách `build_retrieval_query()` dùng `conversation_history` cho
   Phát hiện #3.
4. Hai kẽ hở nhỏ ở Phát hiện #4 — sửa nhanh, rủi ro thấp.
5. Mở rộng độ phủ `personalization`/`persistence`/`multi_course_merge` còn
   thiếu (`evaluation_report.md` mục 4.3).
