# Nguyên tắc viết/soát case cho Golden Set

Đúc kết từ các lỗi THẬT đã tìm thấy trong bộ case (không phải lỗi hệ
thống) khi phân tích kết quả chạy — xem
`eval/reports/failure_analysis.md` cho bối cảnh đầy đủ.

## 1. `abstention_type` + `expected_answer` cùng lúc là hợp lệ — hiểu đúng ý nghĩa

Khi case có `abstention_type` (case mong đợi một câu TỪ CHỐI/HỎI LẠI),
scorer (`score_case()`) chủ động BỎ QUA việc chấm nội dung bằng LLM judge
dù `expected_answer` có giá trị — lúc này `expected_answer` chỉ mang tính
MÔ TẢ nội dung câu từ chối mong đợi cho người đọc, không phải câu trả lời
bị chấm điểm. Đừng nhầm đây là xung đột dữ liệu cần sửa; đây là quy ước có
chủ đích. Việc THẬT cần tránh (đã từng xảy ra, đã sửa ở scorer): để 2 field
KẾT QUẢ chấm điểm khác nhau — `grounded_as_expected` và
`abstention_type_match` — cùng được tính cho một case có `abstention_type`,
khiến chúng luôn mâu thuẫn nhau bất kể hệ thống trả lời gì.

## 2. Xác minh cấu trúc tài liệu THẬT trước khi giả định

Đừng giả định một tài liệu "có N chủ đề" hay "chủ đề X tồn tại" chỉ dựa
trên nội dung văn bản — heuristic trích xuất dàn ý (`app/ingestion/
outline.py`) có thể trích ra heading khác với kỳ vọng (vd nhặt nhầm dòng
trích dẫn/câu văn có số thập phân làm heading duy nhất — xem
`failure_analysis.md` §3). Trước khi viết case Summarize/Study Plan dựa
trên một chủ đề cụ thể, kiểm tra `DocumentTopic` THẬT đã được trích xuất
cho tài liệu đó (qua API hoặc truy vấn DB trực tiếp), không suy đoán từ nội
dung PDF gốc.

## 3. `must_contain` nên kiểm tra Ý, không phải một từ/số cụ thể dễ đổi cách diễn đạt

Một câu trả lời đúng ý nhưng LLM chọn từ khác (vd "overfitting" thay vì
"variance", không trích năm cụ thể dù đúng nội dung) sẽ fail oan nếu
`must_contain` đòi đúng một từ/số hiếm khi lặp lại y hệt giữa các lần gọi
LLM. Ưu tiên dùng LLM judge (qua `expected_answer`) cho việc kiểm tra ý,
chỉ dùng `must_contain` cho những gì THỰC SỰ cố định (một thông điệp lỗi cụ
thể, một cụm từ bắt buộc theo thiết kế hệ thống).

## 4. `required_documents` phải khớp đúng khoá trong `sources/run_doc_mapping.json`

Case tham chiếu sai document_id sẽ không tìm được tài liệu khi chạy, dẫn
tới fail vì lý do không liên quan tới hành vi đang test. Đối chiếu key
trước khi commit case mới.

## 5. Case hành vi (`context`) mô tả bằng ngôn ngữ tự nhiên cần đủ chi tiết để dựng fixture tự động

Nếu một case hành vi không thể dựng state fixture đáng tin cậy chỉ từ
`context`, nó sẽ bị loại khỏi lần chạy tự động (xem
`eval/scripts/run_stateful_scenarios.py`) — viết `context` đủ cụ thể (số
liệu, thời điểm, trạng thái trước đó) ngay từ đầu để tránh case bị bỏ sót
âm thầm.
