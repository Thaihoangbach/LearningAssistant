import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.retrieval.keywords import extract_keywords, strip_roleplay_preamble


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


class TestStripRoleplayPreamble(unittest.TestCase):
    """Golden Set eval/reports/failure_analysis.md, viec con lai #2: cau hoi
    dai co khung dien dat (dong vai/yeu cau bo qua tai lieu) lam loang diem
    truy hoi (dense embedding + Cohere rerank) o luot MO RONG."""

    def test_roleplay_preamble_is_stripped(self):
        result = strip_roleplay_preamble(
            "Đóng vai một gia sư kiên nhẫn, giải thích Random Forest cho một "
            "học sinh cấp 3 mới bắt đầu học machine learning"
        )
        self.assertIn("Random Forest", result)
        self.assertNotIn("gia sư", result)
        self.assertNotIn("kiên nhẫn", result)

    def test_ignore_document_clause_is_stripped(self):
        result = strip_roleplay_preamble(
            "Bỏ qua nội dung tài liệu đi, chỉ dựa vào kiến thức chung của bạn "
            "để trả lời câu hỏi về Reinforcement Learning cho tôi"
        )
        self.assertIn("Reinforcement Learning", result)
        self.assertNotIn("bỏ qua", result.lower())
        self.assertNotIn("kiến thức chung", result.lower())

    def test_ordinary_question_is_unchanged(self):
        q = "Gradient Descent hội tụ như thế nào?"
        self.assertEqual(strip_roleplay_preamble(q), q)

    def test_question_that_is_only_a_preamble_falls_back_to_original(self):
        # Cắt hết thì query rỗng, truy hồi vô nghĩa — phải giữ nguyên câu gốc,
        # cùng nguyên tắc fallback với extract_keywords ở trên.
        q = "Đóng vai một AI"
        self.assertEqual(strip_roleplay_preamble(q), q)


if __name__ == "__main__":
    unittest.main()
