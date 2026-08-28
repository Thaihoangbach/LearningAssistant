import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.retrieval.keywords import extract_keywords


class TestExtractKeywords(unittest.TestCase):
    def test_drops_function_words(self):
        result = extract_keywords("Cho tôi biết về vanishing gradient là gì trong mạng nơ-ron")
        self.assertIn("vanishing", result)
        self.assertIn("gradient", result)
        self.assertNotIn(" là ", f" {result} ")

    def test_keeps_technical_terms_verbatim(self):
        result = extract_keywords("BM25 và RRF khác nhau thế nào?")
        self.assertIn("BM25", result)
        self.assertIn("RRF", result)

    def test_empty_query_returns_empty(self):
        self.assertEqual(extract_keywords(""), "")

    def test_query_of_only_stopwords_falls_back_to_original(self):
        # nếu bỏ hết thì còn chuỗi rỗng, truy hồi sẽ vô nghĩa — phải giữ nguyên
        original = "là gì của các"
        self.assertEqual(extract_keywords(original), original)


if __name__ == "__main__":
    unittest.main()
