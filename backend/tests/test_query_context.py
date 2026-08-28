import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.retrieval.query_context import build_retrieval_query, needs_context


class Turn:
    """Giả lập app.llm.rag.ConversationTurn mà không import nó."""

    def __init__(self, question, answer):
        self.question = question
        self.answer = answer


HISTORY = [Turn("Mạng CNN dùng convolution để làm gì?", "CNN dùng bộ lọc trượt để trích đặc trưng.")]


class TestNeedsContext(unittest.TestCase):
    def test_question_with_pronoun_needs_context(self):
        self.assertTrue(needs_context("tại sao nó lại tốt hơn?"))

    def test_very_short_question_needs_context(self):
        self.assertTrue(needs_context("còn cái kia?"))

    def test_self_contained_question_does_not(self):
        self.assertFalse(needs_context("Gradient Descent hoạt động như thế nào trong mạng nơ-ron?"))

    def test_english_pronoun_is_detected(self):
        self.assertTrue(needs_context("why is it better than the previous approach?"))


class TestBuildRetrievalQuery(unittest.TestCase):
    def test_without_history_returns_question_unchanged(self):
        q = "tại sao nó lại tốt hơn?"
        self.assertEqual(build_retrieval_query(q, None), q)
        self.assertEqual(build_retrieval_query(q, []), q)

    def test_self_contained_question_is_left_alone(self):
        q = "Gradient Descent hoạt động như thế nào trong mạng nơ-ron?"
        self.assertEqual(build_retrieval_query(q, HISTORY), q)

    def test_follow_up_gains_terms_from_previous_turn(self):
        result = build_retrieval_query("tại sao nó lại tốt hơn?", HISTORY)
        self.assertIn("tại sao nó lại tốt hơn?", result)
        self.assertIn("CNN", result)

    def test_does_not_duplicate_terms_already_in_question(self):
        result = build_retrieval_query("CNN có nhược điểm gì?", [Turn("CNN là gì?", "CNN là mạng tích chập.")])
        # câu này tự chứa nội dung nên không được đụng vào
        self.assertEqual(result, "CNN có nhược điểm gì?")

    def test_context_terms_are_capped(self):
        long_turn = [Turn(" ".join(f"thuatngu{i}" for i in range(50)), "trả lời dài")]
        result = build_retrieval_query("nó là gì?", long_turn, max_context_terms=3)
        added = [t for t in result.split() if t.startswith("thuatngu")]
        self.assertEqual(len(added), 3)

    def test_uses_most_recent_turn_first(self):
        history = [
            Turn("Decision Tree là gì?", "Cây quyết định chia dữ liệu."),
            Turn("Còn Random Forest?", "Random Forest là tập hợp nhiều cây."),
        ]
        result = build_retrieval_query("nó khác gì?", history, max_context_terms=4)
        self.assertIn("Random", result)

    def test_empty_question_is_safe(self):
        self.assertEqual(build_retrieval_query("", HISTORY), "")


if __name__ == "__main__":
    unittest.main()
