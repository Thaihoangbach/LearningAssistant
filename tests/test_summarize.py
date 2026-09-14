import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.summarize import TopicCandidate, is_summarize_request, resolve_topic


class TestIsSummarizeRequest(unittest.TestCase):
    def test_vietnamese_summarize_phrasing_is_detected(self):
        self.assertTrue(is_summarize_request("Tóm tắt chương 3 giúp tôi"))
        self.assertTrue(is_summarize_request("tổng hợp giúp tôi phần Gradient Descent"))

    def test_english_summarize_phrasing_is_detected(self):
        self.assertTrue(is_summarize_request("Can you summarize chapter 2?"))
        self.assertTrue(is_summarize_request("give me a summary of attention mechanisms"))

    def test_ordinary_question_is_not_detected(self):
        self.assertFalse(is_summarize_request("Gradient Descent là gì?"))
        self.assertFalse(is_summarize_request("So sánh Gradient Descent và Adam"))


class TestResolveTopic(unittest.TestCase):
    def test_no_candidates_returns_none(self):
        self.assertIsNone(resolve_topic("tóm tắt chương 3", []))

    def test_best_matching_title_by_content_word_overlap_wins(self):
        candidates = [
            TopicCandidate(topic_id="t1", document_id="d1", title="Gradient Descent"),
            TopicCandidate(topic_id="t2", document_id="d1", title="Learning Rate"),
        ]
        result = resolve_topic("tóm tắt Gradient Descent giúp tôi", candidates)
        self.assertEqual(result.topic_id, "t1")

    def test_no_word_overlap_returns_none_instead_of_guessing(self):
        candidates = [TopicCandidate(topic_id="t1", document_id="d1", title="Gradient Descent")]
        result = resolve_topic("tóm tắt chương này giúp tôi", candidates)
        self.assertIsNone(result)

    def test_content_description_matches_via_preview_not_just_title(self):
        # Golden Set Finding #4 (eval/reports/failure_analysis.md): nguoi dung
        # hay mo ta chu de theo NOI DUNG ben trong thay vi lap lai dung tu
        # trong heading ngan. Tieu de rieng khong trung tu nao voi cau hoi,
        # nhung preview (doan trich dau chu de) thi co.
        candidates = [
            TopicCandidate(
                topic_id="t1",
                document_id="d1",
                title="Kiến trúc",
                preview="CNN tận dụng nguyên lý kết nối cục bộ và có nhiều ứng dụng trong thị giác máy tính.",
            ),
            TopicCandidate(topic_id="t2", document_id="d1", title="Lịch sử", preview="Ra đời từ thập niên 1980."),
        ]
        result = resolve_topic("Tóm tắt phần nói về nguyên lý và ứng dụng của CNN", candidates)
        self.assertEqual(result.topic_id, "t1")

    def test_title_only_match_still_wins_over_unrelated_preview(self):
        # Preview chi MO RONG tu vung, khong duoc ghi de/lam mat mot match da
        # co qua tieu de — hanh vi cu (title-only) phai giu nguyen.
        candidates = [
            TopicCandidate(topic_id="t1", document_id="d1", title="Gradient Descent", preview="Bất kỳ nội dung nào."),
            TopicCandidate(topic_id="t2", document_id="d1", title="Learning Rate", preview="Gradient Descent hội tụ nhanh hơn."),
        ]
        result = resolve_topic("tóm tắt Gradient Descent giúp tôi", candidates)
        self.assertEqual(result.topic_id, "t1")

    def test_no_overlap_in_title_or_preview_still_returns_none(self):
        candidates = [
            TopicCandidate(topic_id="t1", document_id="d1", title="Gradient Descent", preview="Hội tụ về cực tiểu.")
        ]
        result = resolve_topic("tóm tắt chương này giúp tôi", candidates)
        self.assertIsNone(result)

    def test_single_coincidental_word_in_preview_does_not_cause_false_match(self):
        # Regression that fix (EDU-SUM-008 trong Golden Set regression run):
        # cau hoi ve tai lieu "Hoc sau" (khong co chu de nao de tom tat) bi
        # khop nham sang chu de "Overfitting" cua MOT TAI LIEU KHAC chi vi
        # preview cua no tinh co chua tu "lieu" (tu "du lieu") trung voi tu
        # "lieu" tach ra tu "tai lieu" trong cau hoi — 1 tu trung ngau nhien,
        # khong phai dau hieu that su lien quan. Phai tra None, khong doan.
        candidates = [
            TopicCandidate(
                topic_id="t1",
                document_id="d1",
                title="1. Definition of overfitting",
                preview="Đường màu xanh lục thể hiện mô hình quá khớp trên dữ liệu huấn luyện.",
            )
        ]
        result = resolve_topic("Tóm tắt tài liệu Học sâu (Deep Learning) giúp tôi", candidates)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
