import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion.chunker import Chunk, chunk_sections


class TestChunkSections(unittest.TestCase):
    def test_short_section_becomes_one_chunk(self):
        sections = [("Trang 1", "Đây là một đoạn văn ngắn.")]
        chunks = chunk_sections(sections, max_chars=800, overlap_chars=100)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, "Đây là một đoạn văn ngắn.")
        self.assertEqual(chunks[0].position_ref, "Trang 1")
        self.assertEqual(chunks[0].chunk_index, 0)

    def test_long_section_splits_into_multiple_chunks_with_overlap(self):
        # 250 ký tự, max_chars=100, overlap=20 -> nhiều chunk, có phần chồng lấn
        text = "A" * 100 + "B" * 100 + "C" * 50
        sections = [("Trang 1", text)]
        chunks = chunk_sections(sections, max_chars=100, overlap_chars=20)

        self.assertGreater(len(chunks), 1)
        # mọi chunk đều không vượt quá max_chars
        for c in chunks:
            self.assertLessEqual(len(c.text), 100)
        # có overlap: ký tự cuối của chunk trước xuất hiện ở đầu chunk sau
        self.assertEqual(chunks[0].text[-20:], chunks[1].text[:20])
        # ghép lại (bỏ phần overlap) phải khôi phục đúng nội dung gốc
        rebuilt = chunks[0].text
        for c in chunks[1:]:
            rebuilt += c.text[20:]
        self.assertEqual(rebuilt, text)

    def test_empty_section_is_skipped(self):
        sections = [("Trang 1", "   "), ("Trang 2", "Nội dung thật.")]
        chunks = chunk_sections(sections, max_chars=800, overlap_chars=100)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].position_ref, "Trang 2")

    def test_chunk_index_increments_across_sections(self):
        sections = [("Trang 1", "Nội dung 1."), ("Trang 2", "Nội dung 2.")]
        chunks = chunk_sections(sections, max_chars=800, overlap_chars=100)
        self.assertEqual([c.chunk_index for c in chunks], [0, 1])
        self.assertEqual(chunks[0].position_ref, "Trang 1")
        self.assertEqual(chunks[1].position_ref, "Trang 2")

    def test_invalid_overlap_raises(self):
        with self.assertRaises(ValueError):
            chunk_sections([("Trang 1", "abc")], max_chars=50, overlap_chars=50)

    def test_returns_chunk_dataclass_instances(self):
        chunks = chunk_sections([("Trang 1", "abc")], max_chars=800, overlap_chars=100)
        self.assertIsInstance(chunks[0], Chunk)


if __name__ == "__main__":
    unittest.main()
