import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.misconception import WrongChoice, find_repeated_misconceptions


def _wrong(item_id, selected, correct="Đáp án đúng", topic="Chủ đề", question="Câu hỏi?"):
    return WrongChoice(
        quiz_item_id=item_id,
        question=question,
        selected_answer=selected,
        correct_answer=correct,
        topic_name=topic,
    )


class TestFindRepeatedMisconceptions(unittest.TestCase):
    def test_same_wrong_choice_twice_is_a_misconception(self):
        choices = [_wrong("q1", "Nhầm A"), _wrong("q1", "Nhầm A")]
        result = find_repeated_misconceptions(choices)
        self.assertEqual(len(result), 1)
        self.assertIn("Nhầm A", result[0])

    def test_single_wrong_choice_is_not_reported(self):
        self.assertEqual(find_repeated_misconceptions([_wrong("q1", "Nhầm A")]), [])

    def test_different_wrong_choices_are_not_grouped(self):
        choices = [_wrong("q1", "Nhầm A"), _wrong("q1", "Nhầm B")]
        self.assertEqual(find_repeated_misconceptions(choices), [])

    def test_same_wrong_choice_across_different_questions_counts(self):
        choices = [
            _wrong("q1", "Entropy luôn giảm", topic="Decision Tree"),
            _wrong("q2", "Entropy luôn giảm", topic="Decision Tree"),
        ]
        result = find_repeated_misconceptions(choices)
        self.assertEqual(len(result), 1)

    def test_mentions_topic_name(self):
        choices = [_wrong("q1", "Nhầm A", topic="Backpropagation")] * 2
        self.assertIn("Backpropagation", find_repeated_misconceptions(choices)[0])

    def test_threshold_is_configurable(self):
        choices = [_wrong("q1", "Nhầm A")] * 2
        self.assertEqual(find_repeated_misconceptions(choices, min_occurrences=3), [])

    def test_empty_input_is_safe(self):
        self.assertEqual(find_repeated_misconceptions([]), [])

    def test_blank_selected_answer_is_ignored(self):
        choices = [_wrong("q1", ""), _wrong("q1", "")]
        self.assertEqual(find_repeated_misconceptions(choices), [])

    def test_same_answer_in_different_topics_is_not_merged(self):
        choices = [
            _wrong("q1", "Luôn tăng", topic="Chủ đề A"),
            _wrong("q2", "Luôn tăng", topic="Chủ đề B"),
        ]
        self.assertEqual(find_repeated_misconceptions(choices), [])

    def test_most_repeated_is_reported_first(self):
        choices = (
            [_wrong("q1", "Sai ít", topic="T")] * 2
            + [_wrong("q2", "Sai nhiều", topic="T")] * 4
        )
        result = find_repeated_misconceptions(choices)
        self.assertIn("Sai nhiều", result[0])


if __name__ == "__main__":
    unittest.main()
