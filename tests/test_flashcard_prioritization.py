"""BUG-007 — flashcard không được ưu tiên đoạn giống khu vực tham khảo ngang
hàng nội dung cốt lõi. Test hàm thuần `_prioritize_core_content`
(app/routers/flashcard.py) — không cần Postgres thật vì không chạm DB."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.llm.rag import RetrievedChunk
from app.routers.flashcard import _prioritize_core_content


def make_chunk(text, doc="pythagoras.pdf", pos="Trang 1"):
    return RetrievedChunk(text=text, document_name=doc, position_ref=pos, score=0.8)


BIBLIOGRAPHY_TEXT = (
    "23. Russell & Norvig (2021), tr. 272.\n"
    "24. Smith, J. (2019). A Study of X. ISBN 123-456-789.\n"
    "25. Doe, A. (2018), pp. 45-60."
)

CORE_CONTENT_TEXT = (
    "Định lý Pythagoras phát biểu rằng trong một tam giác vuông, bình phương "
    "cạnh huyền bằng tổng bình phương hai cạnh góc vuông.\n"
    "Đây là một trong những định lý cơ bản nhất của hình học Euclid."
)


class TestPrioritizeCoreContent(unittest.TestCase):
    def test_bibliography_chunk_moved_to_end(self):
        chunks = [make_chunk(BIBLIOGRAPHY_TEXT, pos="Trang 20"), make_chunk(CORE_CONTENT_TEXT, pos="Trang 1")]
        result = _prioritize_core_content(chunks)
        self.assertEqual(result[0].position_ref, "Trang 1")
        self.assertEqual(result[-1].position_ref, "Trang 20")

    def test_relative_order_within_each_group_is_stable(self):
        chunks = [
            make_chunk(BIBLIOGRAPHY_TEXT, pos="Trang 20"),
            make_chunk(CORE_CONTENT_TEXT, pos="Trang 1"),
            make_chunk(CORE_CONTENT_TEXT, pos="Trang 2"),
            make_chunk(BIBLIOGRAPHY_TEXT, pos="Trang 21"),
        ]
        result = _prioritize_core_content(chunks)
        self.assertEqual([c.position_ref for c in result], ["Trang 1", "Trang 2", "Trang 20", "Trang 21"])

    def test_no_bibliography_chunks_keeps_original_order(self):
        chunks = [make_chunk(CORE_CONTENT_TEXT, pos=f"Trang {i}") for i in range(1, 4)]
        result = _prioritize_core_content(chunks)
        self.assertEqual([c.position_ref for c in result], ["Trang 1", "Trang 2", "Trang 3"])

    def test_bibliography_chunks_are_kept_not_dropped(self):
        # Hạ ưu tiên, KHÔNG xoá — vẫn còn trong danh sách để generator dùng
        # nếu thật sự thiếu nội dung khác.
        chunks = [make_chunk(BIBLIOGRAPHY_TEXT, pos="Trang 20")]
        result = _prioritize_core_content(chunks)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
