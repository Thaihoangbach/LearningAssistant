import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.llm.recommendation import (
    NO_MASTERY_DATA_MESSAGE,
    TopicMastery,
    build_recommendation,
    is_recommendation_request,
)


class TestIsRecommendationRequest(unittest.TestCase):
    def test_vietnamese_phrasing_detected(self):
        self.assertTrue(is_recommendation_request("Tôi nên học gì tiếp theo?"))
        self.assertTrue(is_recommendation_request("Tôi nên tập trung vào chủ đề nào?"))

    def test_english_phrasing_detected(self):
        self.assertTrue(is_recommendation_request("What should I study next?"))

    def test_normal_factual_question_not_detected(self):
        self.assertFalse(is_recommendation_request("Gradient Descent là gì?"))


class TestBuildRecommendation(unittest.TestCase):
    def test_no_topics_returns_no_data_message(self):
        self.assertEqual(build_recommendation([]), NO_MASTERY_DATA_MESSAGE)

    def test_weak_topics_are_prioritized(self):
        topics = [
            TopicMastery(topic_name="Decision Tree", score=0.2),
            TopicMastery(topic_name="Linear Regression", score=0.9),
        ]
        message = build_recommendation(topics)
        self.assertIn("Decision Tree", message)
        self.assertNotIn("Linear Regression", message)

    def test_no_weak_topics_suggests_lowest_scoring_one(self):
        topics = [
            TopicMastery(topic_name="Decision Tree", score=0.8),
            TopicMastery(topic_name="Linear Regression", score=0.9),
        ]
        message = build_recommendation(topics)
        self.assertIn("Decision Tree", message)


class TestStructuredRecommendation(unittest.TestCase):
    def test_includes_reason_from_episodic_evidence(self):
        topics = [TopicMastery(topic_name="Backpropagation", score=0.2)]
        evidence = {"Backpropagation": ["Trả lời sai câu quiz về đạo hàm chuỗi"]}
        result = build_recommendation(topics, evidence_by_topic=evidence)
        self.assertIn("đạo hàm chuỗi", result)

    def test_suggests_reviewing_due_flashcards_when_any(self):
        topics = [TopicMastery(topic_name="CNN", score=0.3)]
        result = build_recommendation(topics, due_flashcards=7)
        self.assertIn("7", result)
        self.assertIn("flashcard", result.lower())

    def test_no_flashcard_line_when_none_due(self):
        topics = [TopicMastery(topic_name="CNN", score=0.3)]
        result = build_recommendation(topics, due_flashcards=0)
        self.assertNotIn("flashcard", result.lower())

    def test_suggests_a_concrete_quiz_action(self):
        topics = [TopicMastery(topic_name="CNN", score=0.3)]
        result = build_recommendation(topics)
        self.assertIn("quiz", result.lower())
        self.assertIn("CNN", result)

    def test_evidence_for_unrelated_topic_is_not_shown(self):
        topics = [TopicMastery(topic_name="CNN", score=0.3)]
        evidence = {"Decision Tree": ["Sai câu về entropy"]}
        result = build_recommendation(topics, evidence_by_topic=evidence)
        self.assertNotIn("entropy", result)

    def test_evidence_is_capped(self):
        topics = [TopicMastery(topic_name="CNN", score=0.3)]
        evidence = {"CNN": [f"Sự kiện số {i}" for i in range(10)]}
        result = build_recommendation(topics, evidence_by_topic=evidence)
        self.assertNotIn("Sự kiện số 3", result)

    def test_still_works_with_no_extra_arguments(self):
        topics = [TopicMastery(topic_name="CNN", score=0.9)]
        result = build_recommendation(topics)
        self.assertIn("CNN", result)


if __name__ == "__main__":
    unittest.main()
