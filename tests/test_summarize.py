import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.summarize import TopicCandidate, is_summarize_request, resolve_topic


class TestIsSummarizeRequest(unittest.TestCase):
    def test_vietnamese_summarize_phrasing_is_detected(self):
        self.assertTrue(is_summarize_request("Tóm tắt chương 3 giúp tôi"))
        self.assertTrue(is_summarize_request("tổng hợp giúp tôi phần Gradient Descent"))

    def test_english_summarize_phrasing_is_detected(self):
        self.assertTrue(is_summarize_request("Can you summarize chapter 2?"))
        self.assertTrue(is_summarize_request("give me a summary of attention mechanisms"))

    def test_ordinary_question_is_not_detected(self):
        self.assertFalse(is_summarize_request("Gradient Descent là gì?"))
        self.assertFalse(is_summarize_request("So sánh Gradient Descent và Adam"))


class TestResolveTopic(unittest.TestCase):
    def test_no_candidates_returns_none(self):
        self.assertIsNone(resolve_topic("tóm tắt chương 3", []))

    def test_best_matching_title_by_content_word_overlap_wins(self):
        candidates = [
            TopicCandidate(topic_id="t1", document_id="d1", title="Gradient Descent"),
            TopicCandidate(topic_id="t2", document_id="d1", title="Learning Rate"),
        ]
        result = resolve_topic("tóm tắt Gradient Descent giúp tôi", candidates)
        self.assertEqual(result.topic_id, "t1")

    def test_no_word_overlap_returns_none_instead_of_guessing(self):
        candidates = [TopicCandidate(topic_id="t1", document_id="d1", title="Gradient Descent")]
        result = resolve_topic("tóm tắt chương này giúp tôi", candidates)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
