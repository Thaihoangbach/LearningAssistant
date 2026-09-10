"""Chế độ sinh Quiz/Flashcard (Learning Loop Phase 3) — ghi vào
Quiz.generation_mode / FlashcardSet.generation_mode (cột đã thêm ở Phase 0,
xem alembic f3b8a1d4e6c2) để sau này phân tích lineage theo mục tiêu học.

CHỈ lưu vết, CHƯA làm thay đổi nội dung sinh ra theo từng mode — đúng như
Phase 0 đã chuẩn bị ("chuẩn bị chỗ lưu ... để không phải migrate schema lần
hai", xem docstring migration). Thay đổi hành vi sinh theo mode là quyết
định lớn hơn (chọn tài liệu/chủ đề nào, độ khó ra sao cho từng mode) nên cố
tình để ngoài phạm vi bước này.
"""

VALID_GENERATION_MODES = ("learn", "review", "exam", "weak_topics")
