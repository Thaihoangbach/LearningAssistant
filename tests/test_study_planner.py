import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.study_planner import DayPlan, TopicPriority, generate_plan


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
        from app.services.study_planner import TopicPriority, generate_plan

        topics = [
            TopicPriority(topic_name="Chương 3", score=None, order_index=2),
            TopicPriority(topic_name="Chương 1", score=None, order_index=0),
            TopicPriority(topic_name="Chương 2", score=None, order_index=1),
        ]
        plan = generate_plan(topics, days=3)
        self.assertEqual([d.topics[0] for d in plan], ["Chương 1", "Chương 2", "Chương 3"])

    def test_weak_topic_still_beats_earlier_but_stronger_topic(self):
        from app.services.study_planner import TopicPriority, generate_plan

        topics = [
            TopicPriority(topic_name="Mở đầu", score=0.95, order_index=0),
            TopicPriority(topic_name="Chương cuối", score=0.1, order_index=9),
        ]
        plan = generate_plan(topics, days=2)
        self.assertEqual(plan[0].topics, ["Chương cuối"])

    def test_missing_order_index_still_works(self):
        from app.services.study_planner import TopicPriority, generate_plan

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
        from app.services.study_planner import TopicPriority, generate_plan

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
        from app.services.study_planner import TopicPriority, generate_plan

        topics = [
            TopicPriority(topic_name="Đã thạo", score=0.95, order_index=0),
            TopicPriority(topic_name="Chưa học", score=None, order_index=9),
        ]
        plan = generate_plan(topics, days=2)
        self.assertEqual(plan[0].topics, ["Chưa học"])


class TestMaxPlanTopicsSafetyCap(unittest.TestCase):
    """BUG-001 — lưới an toàn cuối cùng: dù topic đã qua lọc chất lượng ở tầng
    gọi (app/ingestion/outline.py::is_plausible_topic), một tài khoản nhiều
    tài liệu vẫn có thể dồn hàng trăm Topic hợp lệ về một "kế hoạch" quá dài."""

    def test_plan_never_exceeds_max_plan_topics(self):
        from app.services.study_planner import _MAX_PLAN_TOPICS

        topics = [
            TopicPriority(topic_name=f"Chủ đề {i}", score=None, order_index=i)
            for i in range(_MAX_PLAN_TOPICS + 50)
        ]
        plan = generate_plan(topics, days=3)
        total = sum(len(d.topics) for d in plan)
        self.assertLessEqual(total, _MAX_PLAN_TOPICS)

    def test_below_cap_keeps_all_topics(self):
        from app.services.study_planner import _MAX_PLAN_TOPICS

        topics = [TopicPriority(topic_name=f"T{i}", score=None) for i in range(5)]
        self.assertLess(5, _MAX_PLAN_TOPICS)
        plan = generate_plan(topics, days=2)
        total = sum(len(d.topics) for d in plan)
        self.assertEqual(total, 5)


class TestGenerateMultiCoursePlan(unittest.TestCase):
    def test_no_courses_returns_empty_plan(self):
        from app.services.study_planner import generate_multi_course_plan

        self.assertEqual(generate_multi_course_plan([]), [])

    def test_single_course_matches_plain_generate_plan(self):
        from app.services.study_planner import CoursePlanInput, generate_multi_course_plan

        topics = [TopicPriority(topic_name="A", score=0.1), TopicPriority(topic_name="B", score=0.9)]
        result = generate_multi_course_plan(
            [CoursePlanInput(course_name="CSDL", topics=topics, days_left=2)]
        )
        self.assertEqual(len(result), 2)
        self.assertEqual([t.name for t in result[0].topics], ["A"])
        self.assertEqual([t.course_name for t in result[0].topics], ["CSDL"])

    def test_near_deadline_course_is_denser_than_far_deadline_course(self):
        """Môn thi gần (days_left nhỏ) phải dồn nhiều chủ đề/ngày hơn môn thi
        xa có cùng số lượng chủ đề — đúng nguyên tắc mật độ đã thống nhất khi
        thiết kế (spec §6), không phải áp dụng luật chia đều."""
        from app.services.study_planner import CoursePlanInput, generate_multi_course_plan

        near_topics = [TopicPriority(topic_name=f"CSDL-{i}", score=None) for i in range(4)]
        far_topics = [TopicPriority(topic_name=f"MMT-{i}", score=None) for i in range(4)]
        result = generate_multi_course_plan(
            [
                CoursePlanInput(course_name="CSDL", topics=near_topics, days_left=2),
                CoursePlanInput(course_name="Mạng máy tính", topics=far_topics, days_left=4),
            ]
        )

        day1_csdl = [t for t in result[0].topics if t.course_name == "CSDL"]
        day1_mmt = [t for t in result[0].topics if t.course_name == "Mạng máy tính"]
        self.assertGreater(len(day1_csdl), len(day1_mmt))

    def test_multiple_courses_can_share_a_day(self):
        from app.services.study_planner import CoursePlanInput, generate_multi_course_plan

        result = generate_multi_course_plan(
            [
                CoursePlanInput(course_name="CSDL", topics=[TopicPriority(topic_name="A", score=None)], days_left=3),
                CoursePlanInput(course_name="MMT", topics=[TopicPriority(topic_name="B", score=None)], days_left=3),
            ]
        )
        day1_courses = {t.course_name for t in result[0].topics}
        self.assertEqual(day1_courses, {"CSDL", "MMT"})

    def test_course_past_its_own_deadline_stops_contributing(self):
        """days_left=1 chỉ góp mặt ở ngày 1 của lịch gộp, không tràn sang các
        ngày sau dù lịch tổng dài hơn (vì môn khác có deadline xa hơn)."""
        from app.services.study_planner import CoursePlanInput, generate_multi_course_plan

        result = generate_multi_course_plan(
            [
                CoursePlanInput(course_name="CSDL", topics=[TopicPriority(topic_name="A", score=None)], days_left=1),
                CoursePlanInput(course_name="MMT", topics=[TopicPriority(topic_name="B", score=None)], days_left=3),
            ]
        )
        self.assertEqual(len(result), 3)
        courses_by_day = [{t.course_name for t in d.topics} for d in result]
        self.assertNotIn("CSDL", courses_by_day[1])
        self.assertNotIn("CSDL", courses_by_day[2])


if __name__ == "__main__":
    unittest.main()
