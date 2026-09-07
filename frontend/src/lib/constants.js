// Chuỗi tiếng Việt do BACKEND định nghĩa (Document.status ở models.py,
// 3 mức "tốt"/"trung bình"/"yếu" ở mastery.py) — trước đây StatusBadge.jsx,
// ProgressBar.jsx và DashboardPage.jsx mỗi nơi tự chép lại đúng 3 chuỗi này
// thành object riêng, còn QuizPage.jsx/FlashcardsPage.jsx so sánh thẳng bằng
// literal ("sẵn sàng"). Một lần đổi chính tả/khoảng trắng ở backend sẽ âm
// thầm làm rơi TẤT CẢ các chỗ đó về giá trị mặc định (badge không màu, bộ lọc
// tài liệu "sẵn sàng" thành rỗng) mà không có lỗi/cảnh báo nào nổi lên — gom
// về một chỗ duy nhất để chỉ cần sửa một dòng.

export const DOCUMENT_STATUS = Object.freeze({
  READY: "sẵn sàng",
  ERROR: "lỗi",
  PROCESSING: "đang xử lý",
});

export const MASTERY_LEVEL = Object.freeze({
  GOOD: "tốt",
  MEDIUM: "trung bình",
  WEAK: "yếu",
});
