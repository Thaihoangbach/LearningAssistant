import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.vectorstore.hybrid import reciprocal_rank_fusion


class TestReciprocalRankFusion(unittest.TestCase):
    def test_empty_lists_returns_empty_dict(self):
        self.assertEqual(reciprocal_rank_fusion([]), {})
        self.assertEqual(reciprocal_rank_fusion([[], []]), {})

    def test_single_list_preserves_rank_order(self):
        scores = reciprocal_rank_fusion([["a", "b", "c"]])
        self.assertGreater(scores["a"], scores["b"])
        self.assertGreater(scores["b"], scores["c"])

    def test_item_in_both_lists_scores_higher_than_item_in_one(self):
        dense = ["a", "b", "c"]
        bm25 = ["b", "d", "e"]
        scores = reciprocal_rank_fusion([dense, bm25])
        # "b" xuất hiện ở cả hai danh sách -> điểm cộng dồn từ cả hai
        self.assertGreater(scores["b"], scores["a"])
        self.assertGreater(scores["b"], scores["d"])

    def test_item_ranked_first_in_both_lists_scores_highest(self):
        scores = reciprocal_rank_fusion([["x", "a"], ["x", "b"]])
        self.assertEqual(max(scores, key=scores.get), "x")

    def test_all_input_ids_present_in_output(self):
        scores = reciprocal_rank_fusion([["a", "b"], ["c"]])
        self.assertEqual(set(scores.keys()), {"a", "b", "c"})

    def test_custom_k_changes_score_magnitude_but_not_order(self):
        ranked = ["a", "b", "c"]
        scores_k60 = reciprocal_rank_fusion([ranked], k=60)
        scores_k1 = reciprocal_rank_fusion([ranked], k=1)
        self.assertNotEqual(scores_k60["a"], scores_k1["a"])
        self.assertGreater(scores_k1["a"], scores_k1["b"])


if __name__ == "__main__":
    unittest.main()
