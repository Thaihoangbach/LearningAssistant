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


if __name__ == "__main__":
    unittest.main()
