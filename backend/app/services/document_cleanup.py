"""Dọn dữ liệu dàn ý khi một tài liệu bị xoá hoặc bị thay bằng bản mới.

Vì sao cần: `DocumentTopic` và các `Topic` sinh ra từ dàn ý
(app/routers/documents.py::_save_outline) không có vòng đời gắn với
`Document`. Hậu quả đo được khi kiểm thử:

- Xoá hết tài liệu rồi mà kế hoạch ôn tập VẪN xếp lịch cho chủ đề của tài liệu
  đã xoá — người dùng có 0 tài liệu nhưng vẫn nhận lịch ôn.
- Upload lại cùng một file sinh ra dàn ý trùng lặp, làm lệch bản đồ thứ tự chủ
  đề dùng khi lập kế hoạch.

Nguyên tắc quan trọng khi dọn: XOÁ TÀI LIỆU KHÔNG ĐƯỢC XOÁ LỊCH SỬ HỌC TẬP.
`DocumentTopic` là cấu trúc của tài liệu nên xoá cùng tài liệu. Còn `Topic` là
đơn vị theo dõi tiến độ — chỉ xoá khi người học CHƯA từng dùng tới nó (không có
điểm mastery, không có lượt làm bài, không có câu quiz hay thẻ nào gắn vào) và
không còn tài liệu nào khác nhắc tới. Người đã bỏ công làm bài về một chủ đề
thì không nên mất tiến độ chỉ vì gỡ tài liệu nguồn.
"""

from typing import List

from app.models import (
    Attempt,
    DocumentTopic,
    FlashcardItem,
    MasteryScore,
    QuizItem,
    Topic,
)


def _topic_is_used(db, topic_id: str) -> bool:
    """Người học đã từng tương tác với chủ đề này chưa."""
    checks = (
        db.query(MasteryScore).filter(MasteryScore.topic_id == topic_id).first(),
        db.query(Attempt).filter(Attempt.topic_id == topic_id).first(),
        db.query(QuizItem).filter(QuizItem.topic_id == topic_id).first(),
        db.query(FlashcardItem).filter(FlashcardItem.topic_id == topic_id).first(),
    )
    return any(c is not None for c in checks)


def cleanup_document_topics(db, document_id: str, user_id: str) -> List[str]:
    """Xoá dàn ý của một tài liệu, và những Topic nó tạo ra mà chưa ai dùng tới.

    Trả về tên các Topic đã xoá (chủ yếu để ghi log/kiểm thử)."""
    outline_rows = (
        db.query(DocumentTopic)
        .filter(DocumentTopic.document_id == document_id, DocumentTopic.user_id == user_id)
        .all()
    )
    if not outline_rows:
        return []

    titles = [row.title for row in outline_rows]
    for row in outline_rows:
        db.delete(row)
    db.commit()

    removed: List[str] = []
    for title in set(titles):
        # Tài liệu KHÁC còn nhắc tới chủ đề này thì giữ lại.
        still_referenced = (
            db.query(DocumentTopic)
            .filter(DocumentTopic.user_id == user_id, DocumentTopic.title == title)
            .first()
        )
        if still_referenced is not None:
            continue

        topic = db.query(Topic).filter(Topic.user_id == user_id, Topic.name == title).first()
        if topic is None or _topic_is_used(db, topic.id):
            continue

        db.delete(topic)
        removed.append(title)

    if removed:
        db.commit()
    return removed
