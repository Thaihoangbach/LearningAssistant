"""Logic thuần Python cho Learning Profile (cá nhân hóa dài hạn) — Giai đoạn 1
trong hướng phát triển đã nêu ở docs/thesis, Chương 8.

Tách riêng khỏi router để test được không cần FastAPI/DB, giống pattern đã
dùng ở app/mastery.py và app/study_planner.py. Router (app/routers/chat.py,
app/routers/quiz.py, app/routers/profile.py) chịu trách nhiệm đọc/ghi
LearningProfile trong DB; module này chỉ quyết định LOGIC — level nào được
dùng cho request hiện tại, và có nên ghi đè preference đã lưu hay không.
"""

from typing import Optional

from app.mastery import classify_mastery


def resolve_effective_level(
    requested_level: Optional[str],
    stored_preferred_level: Optional[str],
    inferred_level: Optional[str] = None,
) -> Optional[str]:
    """Level dùng cho request hiện tại, theo thứ tự ưu tiên:
    1. Level truyền tường minh trong request (người dùng tự chọn ngay lúc này).
    2. preferred_level đã lưu trong Learning Profile (từng khai báo trước đó).
    3. Level suy ra từ điểm mastery trung bình (xem infer_level_from_mastery) —
       "trình độ xác nhận qua tương tác thực tế" khi người dùng chưa từng tự
       khai báo lần nào.
    Không có gì ở cả 3 bước thì trả None — hành vi giống hệt trước khi có
    Learning Profile (không cá nhân hóa)."""
    return requested_level or stored_preferred_level or inferred_level


def should_update_preference(requested_level: Optional[str]) -> bool:
    """Chỉ ghi đè preferred_level trong Learning Profile khi request này
    TỰ truyền level tường minh — coi đó là một lần khai báo/cập nhật
    preference mới. Request không truyền level (dùng preference cũ hoặc suy
    ra) thì không được phép âm thầm ghi đè bằng giá trị suy ra được."""
    return bool(requested_level)


def infer_level_from_mastery(avg_mastery: Optional[float]) -> Optional[str]:
    """Suy trình độ từ điểm mastery trung bình hiện có, dùng khi người dùng
    CHƯA từng tự khai báo preferred_level — đúng tinh thần "trình độ đã xác
    nhận qua tương tác thực tế, không chỉ tự khai báo" (docs/thesis, Chương 8,
    Giai đoạn 1). Dùng lại đúng ngưỡng phân loại của app/mastery.py để không
    có hai bộ ngưỡng "yếu/trung bình/tốt" lệch nhau trong cùng hệ thống.

    Mastery "yếu" -> beginner, "tốt" -> advanced. Mastery "trung bình" hoặc
    chưa có dữ liệu (avg_mastery=None, chưa làm quiz nào) -> None, vì tín
    hiệu chưa đủ rõ để tự chọn thay người dùng — trả lời mặc định (không
    nghiêng beginner/advanced) vẫn an toàn hơn đoán sai.
    """
    if avg_mastery is None:
        return None
    label = classify_mastery(avg_mastery)
    if label == "yếu":
        return "beginner"
    if label == "tốt":
        return "advanced"
    return None
