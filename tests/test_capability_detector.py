import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.capability_detector import CAPABILITY_NAMES, detect_capability


class TestStudyPlanIntent(unittest.TestCase):
    def test_detects_deadline_question_and_extracts_days(self):
        match = detect_capability("tôi còn 5 ngày nữa thi, ôn thế nào cho kịp?")
        self.assertEqual(match.name, "study_plan")
        self.assertEqual(match.params["days"], 5)

    def test_detects_explicit_plan_request(self):
        match = detect_capability("lập kế hoạch ôn tập cho tôi trong 10 ngày")
        self.assertEqual(match.name, "study_plan")
        self.assertEqual(match.params["days"], 10)

    def test_plan_request_without_days_uses_default(self):
        match = detect_capability("lập kế hoạch ôn tập giúp tôi")
        self.assertEqual(match.name, "study_plan")
        self.assertEqual(match.params["days"], 7)

    def test_english_plan_request(self):
        match = detect_capability("make me a 3 day study plan")
        self.assertEqual(match.name, "study_plan")
        self.assertEqual(match.params["days"], 3)

    def test_absurd_day_count_is_clamped(self):
        match = detect_capability("còn 9999 ngày nữa thi, lập kế hoạch ôn tập")
        self.assertLessEqual(match.params["days"], 60)


class TestRecommendationIntent(unittest.TestCase):
    def test_detects_what_to_study_next(self):
        match = detect_capability("tôi nên học gì tiếp theo?")
        self.assertEqual(match.name, "recommendation")

    def test_deadline_wins_over_recommendation(self):
        # câu vừa hỏi "nên ôn gì" vừa nêu thời hạn -> kế hoạch cụ thể hữu ích
        # hơn một gợi ý chung chung
        match = detect_capability("còn 3 ngày nữa thi, tôi nên ôn gì?")
        self.assertEqual(match.name, "study_plan")


class TestFlashcardDueIntent(unittest.TestCase):
    def test_detects_due_cards_question(self):
        match = detect_capability("hôm nay có thẻ nào đến hạn ôn không?")
        self.assertEqual(match.name, "flashcard_due")

    def test_detects_how_many_cards(self):
        match = detect_capability("còn bao nhiêu thẻ cần ôn?")
        self.assertEqual(match.name, "flashcard_due")


class TestDefaultRouting(unittest.TestCase):
    def test_ordinary_question_has_no_capability(self):
        self.assertIsNone(detect_capability("Gradient Descent là gì?"))

    def test_empty_question_has_no_capability(self):
        self.assertIsNone(detect_capability(""))

    def test_question_mentioning_days_but_not_planning_is_not_routed(self):
        # "3 ngày" ở đây là nội dung câu hỏi, không phải yêu cầu lập lịch
        self.assertIsNone(detect_capability("mô hình huấn luyện trong 3 ngày thì có đủ không?"))


class TestRegistryShape(unittest.TestCase):
    def test_every_detected_name_is_registered(self):
        for question in [
            "tôi nên học gì tiếp theo?",
            "còn 5 ngày nữa thi, ôn thế nào?",
            "hôm nay có thẻ nào đến hạn không?",
        ]:
            match = detect_capability(question)
            self.assertIn(match.name, CAPABILITY_NAMES)


class TestMultipleDeadlinesSignal(unittest.TestCase):
    def test_single_deadline_mention_is_not_flagged(self):
        match = detect_capability("còn 5 ngày nữa thi, ôn thế nào cho kịp?")
        self.assertFalse(match.params["multiple_days_mentioned"])

    def test_two_deadline_mentions_are_flagged(self):
        # "còn" ở đầu là cần thiết để câu khớp _PLAN_INTENT_RE (xem
        # "còn\s+\d+\s*(ngày|hôm)") — nếu không thì detect_capability trả về
        # None trước khi kịp chạy tới _detect_study_plan, bất kể
        # multiple_days_mentioned được cài đúng hay không.
        match = detect_capability("còn 5 ngày nữa thi CSDL, 10 ngày nữa thi Mạng máy tính, ôn sao đây?")
        self.assertTrue(match.params["multiple_days_mentioned"])


if __name__ == "__main__":
    unittest.main()
