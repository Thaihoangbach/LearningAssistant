import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.learning_profile import (
    infer_level_from_mastery,
    resolve_effective_level,
    should_update_preference,
)


class TestResolveEffectiveLevel(unittest.TestCase):
    def test_requested_level_wins_over_stored_preference(self):
        self.assertEqual(resolve_effective_level("advanced", "beginner"), "advanced")

    def test_falls_back_to_stored_preference_when_not_requested(self):
        self.assertEqual(resolve_effective_level(None, "beginner"), "beginner")

    def test_none_when_nothing_provided(self):
        self.assertIsNone(resolve_effective_level(None, None))

    def test_requested_level_used_when_no_stored_preference(self):
        self.assertEqual(resolve_effective_level("beginner", None), "beginner")

    def test_falls_back_to_inferred_level_when_no_request_or_stored(self):
        self.assertEqual(resolve_effective_level(None, None, inferred_level="beginner"), "beginner")

    def test_stored_preference_wins_over_inferred_level(self):
        self.assertEqual(resolve_effective_level(None, "advanced", inferred_level="beginner"), "advanced")

    def test_requested_level_wins_over_inferred_level(self):
        self.assertEqual(resolve_effective_level("advanced", None, inferred_level="beginner"), "advanced")


class TestShouldUpdatePreference(unittest.TestCase):
    def test_true_when_level_explicitly_requested(self):
        self.assertTrue(should_update_preference("advanced"))

    def test_false_when_no_level_requested(self):
        self.assertFalse(should_update_preference(None))

    def test_false_when_empty_string_requested(self):
        self.assertFalse(should_update_preference(""))


class TestInferLevelFromMastery(unittest.TestCase):
    def test_none_when_no_mastery_data(self):
        self.assertIsNone(infer_level_from_mastery(None))

    def test_weak_mastery_infers_beginner(self):
        self.assertEqual(infer_level_from_mastery(0.2), "beginner")

    def test_good_mastery_infers_advanced(self):
        self.assertEqual(infer_level_from_mastery(0.9), "advanced")

    def test_average_mastery_infers_nothing(self):
        self.assertIsNone(infer_level_from_mastery(0.5))

    def test_boundary_at_075_infers_advanced(self):
        self.assertEqual(infer_level_from_mastery(0.75), "advanced")

    def test_boundary_at_04_infers_nothing(self):
        self.assertIsNone(infer_level_from_mastery(0.4))


if __name__ == "__main__":
    unittest.main()
