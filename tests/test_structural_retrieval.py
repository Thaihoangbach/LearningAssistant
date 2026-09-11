import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.structural_retrieval import TopicSectionInfo, compute_section_bounds


class TestComputeSectionBounds(unittest.TestCase):
    def test_topic_not_found_returns_none(self):
        topics = [TopicSectionInfo(topic_id="t1", section_index=0)]
        self.assertIsNone(compute_section_bounds(topics, "unknown"))

    def test_topic_without_section_index_returns_none(self):
        topics = [TopicSectionInfo(topic_id="t1", section_index=None)]
        self.assertIsNone(compute_section_bounds(topics, "t1"))

    def test_only_topic_in_document_has_no_upper_bound(self):
        topics = [TopicSectionInfo(topic_id="t1", section_index=2)]
        self.assertEqual(compute_section_bounds(topics, "t1"), (2, None))

    def test_next_topic_by_section_index_becomes_upper_bound(self):
        topics = [
            TopicSectionInfo(topic_id="t1", section_index=0),
            TopicSectionInfo(topic_id="t2", section_index=5),
        ]
        self.assertEqual(compute_section_bounds(topics, "t1"), (0, 5))

    def test_closest_later_section_index_is_used_not_just_any_later_one(self):
        topics = [
            TopicSectionInfo(topic_id="t1", section_index=0),
            TopicSectionInfo(topic_id="t2", section_index=9),
            TopicSectionInfo(topic_id="t3", section_index=3),
        ]
        # t3 (section_index=3) là mốc gần nhất, không phải t2 (section_index=9)
        self.assertEqual(compute_section_bounds(topics, "t1"), (0, 3))

    def test_list_order_does_not_matter_only_section_index_value(self):
        topics = [
            TopicSectionInfo(topic_id="t2", section_index=5),
            TopicSectionInfo(topic_id="t1", section_index=0),
        ]
        self.assertEqual(compute_section_bounds(topics, "t1"), (0, 5))

    def test_topics_without_section_index_are_ignored_as_bound_candidates(self):
        topics = [
            TopicSectionInfo(topic_id="t1", section_index=0),
            TopicSectionInfo(topic_id="t_old", section_index=None),
            TopicSectionInfo(topic_id="t2", section_index=4),
        ]
        self.assertEqual(compute_section_bounds(topics, "t1"), (0, 4))

    def test_last_topic_in_document_has_no_upper_bound(self):
        topics = [
            TopicSectionInfo(topic_id="t1", section_index=0),
            TopicSectionInfo(topic_id="t2", section_index=5),
        ]
        self.assertEqual(compute_section_bounds(topics, "t2"), (5, None))


if __name__ == "__main__":
    unittest.main()
