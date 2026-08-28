import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.citation import supporting_sentences


class TestSupportingSentences(unittest.TestCase):
    def test_returns_sentence_sharing_content_words(self):
        chunk = "Gradient Descent là thuật toán tối ưu lặp. Cây quyết định chia dữ liệu theo thuộc tính."
        answer = "Gradient Descent là một thuật toán tối ưu."
        result = supporting_sentences(answer, chunk)
        self.assertEqual(len(result), 1)
        self.assertIn("thuật toán tối ưu lặp", result[0])

    def test_returns_empty_when_nothing_overlaps(self):
        chunk = "Cây quyết định chia dữ liệu theo thuộc tính."
        answer = "Mạng nơ-ron tích chập dùng bộ lọc."
        self.assertEqual(supporting_sentences(answer, chunk), [])

    def test_ignores_stopwords_only_overlap(self):
        # chỉ trùng các từ chức năng ("là", "một", "của") thì KHÔNG tính là chống đỡ
        chunk = "Đây là một ví dụ của việc dùng từ nối."
        answer = "Đó là một phần của câu."
        self.assertEqual(supporting_sentences(answer, chunk), [])

    def test_empty_inputs_are_safe(self):
        self.assertEqual(supporting_sentences("", "abc"), [])
        self.assertEqual(supporting_sentences("abc", ""), [])

    def test_multiple_supporting_sentences_are_all_returned(self):
        chunk = "Convolution dùng bộ lọc trượt. Pooling giảm kích thước bản đồ đặc trưng."
        answer = "Convolution dùng bộ lọc trượt và pooling giảm kích thước bản đồ đặc trưng."
        self.assertEqual(len(supporting_sentences(answer, chunk)), 2)


if __name__ == "__main__":
    unittest.main()
