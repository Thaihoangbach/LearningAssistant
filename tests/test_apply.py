import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.apply import is_apply_request


class TestIsApplyRequest(unittest.TestCase):
    def test_vietnamese_apply_phrasing_is_detected(self):
        self.assertTrue(is_apply_request("Áp dụng Gradient Descent vào một bài toán cụ thể"))
        self.assertTrue(is_apply_request("Cho một ví dụ áp dụng Attention giúp tôi"))
        self.assertTrue(is_apply_request("Cho bài tập vận dụng công thức này"))

    def test_english_apply_phrasing_is_detected(self):
        self.assertTrue(is_apply_request("Apply Gradient Descent to a real dataset"))
        self.assertTrue(is_apply_request("Give me a worked example of this"))
        self.assertTrue(is_apply_request("I need a practice problem for this concept"))

    def test_ordinary_question_is_not_detected(self):
        self.assertFalse(is_apply_request("Gradient Descent là gì?"))
        self.assertFalse(is_apply_request("Tóm tắt chương 3 giúp tôi"))
        self.assertFalse(is_apply_request("So sánh Attention và RNN"))


if __name__ == "__main__":
    unittest.main()
