import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.study_planner import DayPlan, TopicPriority, generate_plan


class TestGeneratePlan(unittest.TestCase):
    def test_no_topics_returns_empty_plan(self):
        self.assertEqual(generate_plan([], days=7), [])

    def test_zero_or_negative_days_returns_empty_plan(self):
        topics = [TopicPriority(topic_name="A", score=0.5)]
        self.assertEqual(generate_plan(topics, days=0), [])
        self.assertEqual(generate_plan(topics, days=-1), [])

    def test_weak_topics_scheduled_before_strong_ones(self):
        topics = [
            TopicPriority(topic_name="Mạnh", score=0.9),
            TopicPriority(topic_name="Yếu", score=0.1),
        ]
        plan = generate_plan(topics, days=2)
        self.assertEqual(plan[0].topics, ["Yếu"])
        self.assertEqual(plan[1].topics, ["Mạnh"])

    def test_topics_without_mastery_data_are_scheduled_first(self):
        topics = [
            TopicPriority(topic_name="Đã học tốt", score=0.9),
            TopicPriority(topic_name="Chưa học", score=None),
        ]
        plan = generate_plan(topics, days=2)
        self.assertEqual(plan[0].topics, ["Chưa học"])

    def test_more_days_than_topics_only_returns_days_with_content(self):
        topics = [TopicPriority(topic_name="A", score=0.5)]
        plan = generate_plan(topics, days=5)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0], DayPlan(day=1, topics=["A"]))

    def test_more_topics_than_days_distributes_round_robin(self):
        topics = [TopicPriority(topic_name=str(i), score=float(i)) for i in range(5)]
        plan = generate_plan(topics, days=2)
        self.assertEqual(len(plan), 2)
        all_topics = [t for day in plan for t in day.topics]
        self.assertEqual(sorted(all_topics), sorted(str(i) for i in range(5)))


class TestOutlineOrdering(unittest.TestCase):
    """DocumentTopic.order_index là thứ tự tác giả trình bày tài liệu — một dạng
    phụ thuộc trước-sau CHO KHÔNG. Không dùng thì kế hoạch có thể xếp
    "Backpropagation" trước "Neural Network cơ bản" chỉ vì điểm tình cờ thấp
    hơn, dù không ai học ngược thứ tự đó."""

    def test_document_order_breaks_ties_within_same_priority_band(self):
        from app.study_planner import TopicPriority, generate_plan

        topics = [
            TopicPriority(topic_name="Chương 3", score=None, order_index=2),
            TopicPriority(topic_name="Chương 1", score=None, order_index=0),
            TopicPriority(topic_name="Chương 2", score=None, order_index=1),
        ]
        plan = generate_plan(topics, days=3)
        self.assertEqual([d.topics[0] for d in plan], ["Chương 1", "Chương 2", "Chương 3"])

    def test_weak_topic_still_beats_earlier_but_stronger_topic(self):
        from app.study_planner import TopicPriority, generate_plan

        topics = [
            TopicPriority(topic_name="Mở đầu", score=0.95, order_index=0),
            TopicPriority(topic_name="Chương cuối", score=0.1, order_index=9),
        ]
        plan = generate_plan(topics, days=2)
        self.assertEqual(plan[0].topics, ["Chương cuối"])

    def test_missing_order_index_still_works(self):
        from app.study_planner import TopicPriority, generate_plan

        topics = [
            TopicPriority(topic_name="A", score=0.2),
            TopicPriority(topic_name="B", score=0.8),
        ]
        plan = generate_plan(topics, days=2)
        self.assertEqual(plan[0].topics, ["A"])

    def test_forgotten_foundation_comes_before_topics_built_on_it(self):
        """Chủ đề nền tảng đã rơi xuống mức quên phải đứng TRƯỚC các chủ đề dựa
        trên nó, kể cả khi những chủ đề kia chưa từng học. Trước khi gộp hai
        nhóm "chưa học" và "đã quên", kế hoạch xếp "Learning Rate" trước
        "Gradient Descent" — đúng thứ tự ngược mà không ai học bao giờ."""
        from app.study_planner import TopicPriority, generate_plan

        topics = [
            TopicPriority(topic_name="Learning Rate", score=None, order_index=1),
            TopicPriority(topic_name="Các biến thể", score=None, order_index=2),
            TopicPriority(topic_name="Gradient Descent", score=0.11, order_index=0),
        ]
        plan = generate_plan(topics, days=3)
        self.assertEqual(
            [d.topics[0] for d in plan],
            ["Gradient Descent", "Learning Rate", "Các biến thể"],
        )

    def test_mastered_topic_still_goes_last(self):
        from app.study_planner import TopicPriority, generate_plan

        topics = [
            TopicPriority(topic_name="Đã thạo", score=0.95, order_index=0),
            TopicPriority(topic_name="Chưa học", score=None, order_index=9),
        ]
        plan = generate_plan(topics, days=2)
        self.assertEqual(plan[0].topics, ["Chưa học"])


if __name__ == "__main__":
    unittest.main()
