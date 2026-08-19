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


if __name__ == "__main__":
    unittest.main()
