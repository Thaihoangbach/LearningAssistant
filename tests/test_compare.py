import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.llm.rag import RetrievedChunk
from app.services.compare import (
    _merge_chunks,
    extract_comparison_entities,
    is_compare_request,
)


class TestIsCompareRequest(unittest.TestCase):
    def test_vietnamese_compare_phrasing_is_detected(self):
        self.assertTrue(is_compare_request("So sánh Attention và RNN giúp tôi"))
        self.assertTrue(is_compare_request("Khác nhau giữa Gradient Descent và Adam là gì?"))

    def test_english_compare_phrasing_is_detected(self):
        self.assertTrue(is_compare_request("Compare Attention and RNN"))
        self.assertTrue(is_compare_request("What's the difference between TCP and UDP?"))

    def test_ordinary_question_is_not_detected(self):
        self.assertFalse(is_compare_request("Attention là gì?"))
        self.assertFalse(is_compare_request("Tóm tắt chương 3 giúp tôi"))
        # "khác nhau" không đi kèm "giữa" không tính là yêu cầu so sánh hai vế.
        self.assertFalse(is_compare_request("Có những cách khác nhau nào để tối ưu mô hình?"))


class TestExtractComparisonEntities(unittest.TestCase):
    def test_vietnamese_so_sanh_pattern(self):
        result = extract_comparison_entities("So sánh Attention và RNN")
        self.assertEqual(result, ("Attention", "RNN"))

    def test_vietnamese_khac_nhau_giua_pattern(self):
        result = extract_comparison_entities("Khác nhau giữa Gradient Descent và Adam là gì?")
        self.assertEqual(result, ("Gradient Descent", "Adam"))

    def test_english_compare_pattern(self):
        result = extract_comparison_entities("Compare Attention and RNN")
        self.assertEqual(result, ("Attention", "RNN"))

    def test_english_difference_between_pattern(self):
        result = extract_comparison_entities("difference between TCP and UDP")
        self.assertEqual(result, ("TCP", "UDP"))

    def test_trailing_filler_is_stripped_from_second_entity(self):
        result = extract_comparison_entities("so sánh Attention và RNN giúp tôi")
        self.assertEqual(result, ("Attention", "RNN"))

    def test_no_clear_pair_returns_none_instead_of_guessing(self):
        self.assertIsNone(extract_comparison_entities("So sánh giúp tôi với"))
        self.assertIsNone(extract_comparison_entities("Attention là gì?"))


class TestMergeChunks(unittest.TestCase):
    def make_chunk(self, chunk_id, text="nội dung", doc="a.pdf", pos="Trang 1", score=0.8):
        return RetrievedChunk(text=text, document_name=doc, position_ref=pos, score=score, chunk_id=chunk_id)

    def test_chunks_from_both_sides_are_kept(self):
        a = [self.make_chunk("c1"), self.make_chunk("c2")]
        b = [self.make_chunk("c3")]
        merged = _merge_chunks(a, b)
        self.assertEqual([c.chunk_id for c in merged], ["c1", "c2", "c3"])

    def test_duplicate_chunk_id_across_sides_is_deduped(self):
        a = [self.make_chunk("c1")]
        b = [self.make_chunk("c1"), self.make_chunk("c2")]
        merged = _merge_chunks(a, b)
        self.assertEqual([c.chunk_id for c in merged], ["c1", "c2"])


if __name__ == "__main__":
    unittest.main()
