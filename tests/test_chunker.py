import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

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

    def test_section_index_matches_position_in_sections_list(self):
        # section_index dùng cho structural retrieval (lấy hết chunk của một
        # DocumentTopic) — phải trỏ đúng chỉ số 0-based trong `sections` đầu
        # vào, không phải theo chunk_index (vốn tăng liên tục xuyên section).
        sections = [
            ("Trang 1", "Nội dung một."),
            ("Trang 2", "Nội dung hai, dài hơn một chút để chắc chắn."),
            ("Trang 3", "Nội dung ba."),
        ]
        chunks = chunk_sections(sections, max_chars=800, overlap_chars=100, bridge_sections=False)
        self.assertEqual([c.section_index for c in chunks], [0, 1, 2])

    def test_bridge_chunk_gets_left_section_index(self):
        long_a = " ".join(f"Câu A{i} có nội dung đủ dài để vượt ngưỡng." for i in range(12))
        long_b = " ".join(f"Câu B{i} có nội dung đủ dài để vượt ngưỡng." for i in range(12))
        sections = [("Trang 1", long_a), ("Trang 2", long_b)]
        chunks = chunk_sections(sections, max_chars=300, overlap_chars=100)
        bridge = next(c for c in chunks if "–" in c.position_ref)
        self.assertEqual(bridge.section_index, 0)

    def test_invalid_overlap_raises(self):
        with self.assertRaises(ValueError):
            chunk_sections([("Trang 1", "abc")], max_chars=50, overlap_chars=50)

    def test_returns_chunk_dataclass_instances(self):
        chunks = chunk_sections([("Trang 1", "abc")], max_chars=800, overlap_chars=100)
        self.assertIsInstance(chunks[0], Chunk)


class TestSentenceBoundaries(unittest.TestCase):
    def test_chunks_do_not_cut_mid_sentence(self):
        text = " ".join(f"Đây là câu số {i} trong đoạn văn thử nghiệm." for i in range(30))
        chunks = chunk_sections([("Trang 1", text)], max_chars=200, overlap_chars=50)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            # mỗi chunk phải kết thúc bằng dấu câu, không cụt giữa chừng
            self.assertTrue(c.text.rstrip().endswith("."), f"chunk cụt: {c.text!r}")

    def test_single_sentence_longer_than_max_is_hard_split(self):
        text = "A" * 250
        chunks = chunk_sections([("Trang 1", text)], max_chars=100, overlap_chars=20)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c.text), 100)


class TestSectionBridging(unittest.TestCase):
    def _long(self, marker):
        return " ".join(f"Câu {marker}{i} có nội dung đủ dài để vượt ngưỡng." for i in range(12))

    def test_bridge_chunk_spans_two_sections(self):
        sections = [("Trang 1", self._long("A")), ("Trang 2", self._long("B"))]
        chunks = chunk_sections(sections, max_chars=300, overlap_chars=100)
        bridges = [c for c in chunks if "–" in c.position_ref]
        self.assertEqual(len(bridges), 1)
        # chunk bắc cầu phải chứa nội dung của CẢ HAI trang
        self.assertIn("A", bridges[0].text)
        self.assertIn("B", bridges[0].text)

    def test_bridge_position_ref_names_both_sections(self):
        sections = [("Trang 1", self._long("A")), ("Trang 2", self._long("B"))]
        chunks = chunk_sections(sections, max_chars=300, overlap_chars=100)
        bridge = next(c for c in chunks if "–" in c.position_ref)
        self.assertEqual(bridge.position_ref, "Trang 1–Trang 2")

    def test_short_sections_are_not_bridged(self):
        # section ngắn hơn cửa sổ chồng lấn thì đã nằm trọn trong chunk của
        # chính nó, bắc cầu chỉ tạo nhiễu
        sections = [("Trang 1", "Ngắn."), ("Trang 2", "Cũng ngắn.")]
        chunks = chunk_sections(sections, max_chars=800, overlap_chars=100)
        self.assertEqual([c.position_ref for c in chunks], ["Trang 1", "Trang 2"])

    def test_bridging_can_be_disabled(self):
        sections = [("Trang 1", self._long("A")), ("Trang 2", self._long("B"))]
        chunks = chunk_sections(sections, max_chars=300, overlap_chars=100, bridge_sections=False)
        self.assertEqual([c for c in chunks if "–" in c.position_ref], [])


if __name__ == "__main__":
    unittest.main()
