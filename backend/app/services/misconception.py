"""Phát hiện quan niệm sai LẶP LẠI từ đáp án người học đã chọn.

Quiz generator cố tình thiết kế đáp án nhiễu là "nhầm lẫn hợp lý giữa hai khái
niệm gần nhau" (app/llm/quiz_generator.py), nên việc người học CHỌN NHẦM CÁI
NÀO mang thông tin chẩn đoán thật: chọn A thay vì B phản ánh một kiểu hiểu sai
khác hẳn chọn C thay vì B. Chọn sai một lần có thể do bất cẩn; chọn ĐÚNG MỘT
đáp án sai NHIỀU LẦN mới là quan niệm sai thực sự.

Nhờ module này, cá nhân hoá đi từ mức "chủ đề này yếu" xuống mức "bạn đang
hiểu sai điểm cụ thể nào" — thô hơn hẳn nếu chỉ có đúng/sai.

Module thuần, không chạm DB, không gọi LLM.
"""

from collections import Counter
from dataclasses import dataclass
from typing import List

MIN_OCCURRENCES = 2
MAX_REPORTED = 3


@dataclass
class WrongChoice:
    quiz_item_id: str
    question: str
    selected_answer: str
    correct_answer: str
    topic_name: str


def find_repeated_misconceptions(
    choices: List[WrongChoice], min_occurrences: int = MIN_OCCURRENCES
) -> List[str]:
    """Trả về mô tả những quan niệm sai xuất hiện lặp lại, dễ đọc cho người dùng.

    Gom theo (chủ đề, đáp án đã chọn) chứ không theo câu hỏi: cùng một hiểu sai
    thường lộ ra ở nhiều câu hỏi khác nhau trong cùng chủ đề. Ngược lại, cùng
    một chuỗi đáp án ở HAI chủ đề khác nhau là hai chuyện khác nhau nên không
    được gộp."""
    counter = Counter(
        (c.topic_name, c.selected_answer.strip())
        for c in choices
        if c.selected_answer and c.selected_answer.strip()
    )

    repeated = [
        (topic, answer, count)
        for (topic, answer), count in counter.items()
        if count >= min_occurrences
    ]
    repeated.sort(key=lambda item: item[2], reverse=True)

    return [
        f'Ở chủ đề "{topic}" bạn đã {count} lần chọn nhầm đáp án "{answer}"'
        for topic, answer, count in repeated[:MAX_REPORTED]
    ]
