import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.retrieval.query_context import build_retrieval_query, has_unresolved_reference, needs_context


class Turn:
    """Giả lập app.llm.rag.ConversationTurn mà không import nó."""

    def __init__(self, question, answer):
        self.question = question
        self.answer = answer


HISTORY = [Turn("Mạng CNN dùng convolution để làm gì?", "CNN dùng bộ lọc trượt để trích đặc trưng.")]


class TestNeedsContext(unittest.TestCase):
    def test_question_with_pronoun_needs_context(self):
        self.assertTrue(needs_context("tại sao nó lại tốt hơn?"))

    def test_very_short_question_needs_context(self):
        self.assertTrue(needs_context("còn cái kia?"))

    def test_self_contained_question_does_not(self):
        self.assertFalse(needs_context("Gradient Descent hoạt động như thế nào trong mạng nơ-ron?"))

    def test_english_pronoun_is_detected(self):
        self.assertTrue(needs_context("why is it better than the previous approach?"))


class TestBuildRetrievalQuery(unittest.TestCase):
    def test_without_history_returns_question_unchanged(self):
        q = "tại sao nó lại tốt hơn?"
        self.assertEqual(build_retrieval_query(q, None), q)
        self.assertEqual(build_retrieval_query(q, []), q)

    def test_self_contained_question_is_left_alone(self):
        q = "Gradient Descent hoạt động như thế nào trong mạng nơ-ron?"
        self.assertEqual(build_retrieval_query(q, HISTORY), q)

    def test_follow_up_gains_terms_from_previous_turn(self):
        result = build_retrieval_query("tại sao nó lại tốt hơn?", HISTORY)
        self.assertIn("tại sao nó lại tốt hơn?", result)
        self.assertIn("CNN", result)

    def test_does_not_duplicate_terms_already_in_question(self):
        result = build_retrieval_query("CNN có nhược điểm gì?", [Turn("CNN là gì?", "CNN là mạng tích chập.")])
        # câu này tự chứa nội dung nên không được đụng vào
        self.assertEqual(result, "CNN có nhược điểm gì?")

    def test_context_terms_are_capped(self):
        long_turn = [Turn(" ".join(f"thuatngu{i}" for i in range(50)), "trả lời dài")]
        result = build_retrieval_query("nó là gì?", long_turn, max_context_terms=3)
        added = [t for t in result.split() if t.startswith("thuatngu")]
        self.assertEqual(len(added), 3)

    def test_uses_most_recent_turn_first(self):
        history = [
            Turn("Decision Tree là gì?", "Cây quyết định chia dữ liệu."),
            Turn("Còn Random Forest?", "Random Forest là tập hợp nhiều cây."),
        ]
        result = build_retrieval_query("nó khác gì?", history, max_context_terms=4)
        self.assertIn("Random", result)

    def test_empty_question_is_safe(self):
        self.assertEqual(build_retrieval_query("", HISTORY), "")


class TestHasUnresolvedReference(unittest.TestCase):
    """failure_analysis.md Phat hien #1 — case EDU-ABS-008/009/012/013: dai
    tu/chi dinh tu khong co antecedent khien retrieval tu "chon" mot doi
    tuong gan dung roi generator tra loi tu tin sai doi tuong (false
    grounding), nguy hiem hon tu choi "khong tim thay" thong thuong."""

    def test_single_turn_pronoun_no_history_is_unresolved(self):
        # EDU-ABS-008/013 — cau hoi don, khong co luot truoc nao ca.
        self.assertTrue(has_unresolved_reference("Nó hoạt động thế nào?", None))
        self.assertTrue(has_unresolved_reference("Ai đã phát minh ra nó?", []))

    def test_demonstrative_no_history_is_unresolved(self):
        # EDU-ABS-009/012.
        self.assertTrue(has_unresolved_reference("Cái này có chính xác không?", None))
        self.assertTrue(has_unresolved_reference("Cái đó dùng để làm gì?", None))

    def test_follow_up_with_resolvable_history_is_not_unresolved(self):
        # EDU-CONV-002 kieu follow-up hop le — KHONG duoc chan.
        self.assertFalse(has_unresolved_reference("Nó có mấy loại phổ biến?", HISTORY))

    def test_history_with_no_overlapping_terms_stays_unresolved(self):
        # Co lich su nhung khong co tu noi dung nao de bo sung (turn rong) —
        # build_retrieval_query tra ve y het cau hoi goc.
        empty_history = [Turn("", "")]
        self.assertTrue(has_unresolved_reference("Nó là gì?", empty_history))

    def test_short_self_contained_question_without_pronoun_is_not_unresolved(self):
        # Nguy co regression quan trong nhat: needs_context() coi ca cau
        # ngan <5 tu la "can ngu canh" du KHONG co dai tu nao — khong duoc
        # dung needs_context() cho gate nay, phai chi dung ANAPHORA_RE. Cac
        # case nay dang PASS that trong Golden Set (EDU-ABS-014 va tuong tu).
        self.assertFalse(has_unresolved_reference("Kernel là gì?", None))
        self.assertFalse(has_unresolved_reference("Overfitting là gì?", None))
        self.assertFalse(has_unresolved_reference("Gradient descent là gì?", None))

    def test_self_contained_question_with_history_is_not_unresolved(self):
        self.assertFalse(
            has_unresolved_reference("Gradient Descent hoạt động như thế nào trong mạng nơ-ron?", HISTORY)
        )

    def test_empty_question_is_not_unresolved(self):
        self.assertFalse(has_unresolved_reference("", HISTORY))
        self.assertFalse(has_unresolved_reference("   ", None))

    def test_antecedent_named_earlier_in_same_question_is_not_unresolved(self):
        # EDU-GRD-022 — regression bat duoc qua chay live: "no" tro ve
        # "Gradient descent" neu ngay truoc do trong CUNG cau hoi, khong can
        # lich su hoi thoai.
        self.assertFalse(
            has_unresolved_reference(
                "Gradient descent là gì, và nó luôn tìm được cực tiểu toàn cục cho mọi hàm mục tiêu, đúng không?",
                None,
            )
        )

    def test_pronoun_before_any_definition_clause_is_still_unresolved(self):
        # "la gi" xuat hien SAU dai tu (trong chinh cau hoi) khong tinh —
        # EDU-ABS-012 van phai bi chan dung nhu cu.
        self.assertTrue(has_unresolved_reference("Cái đó dùng để làm gì?", None))

    def test_long_compound_question_with_antecedent_not_using_la_gi_is_not_unresolved(self):
        # Hoi quy phat hien qua Golden Set live 2026-09-16: rag_qa 97.8%->80%,
        # retrieval 91.4%->80% sau khi them has_unresolved_reference o phien
        # truoc — _DEFINITION_ANTECEDENT_RE chi bat dung cum "la gi", khong
        # tong quat cho cau ghep khac. Cac case duoi day tung PASS that.
        self.assertFalse(
            has_unresolved_reference(
                "Mạng nơ-ron tích chập (CNN) được định nghĩa như thế nào và nó được thiết kế để xử lý loại dữ liệu gì?",
                None,
            )
        )  # EDU-QA-009
        self.assertFalse(
            has_unresolved_reference(
                "What is safe reinforcement learning (SRL), and how does risk-averse reinforcement learning differ from it?",
                None,
            )
        )  # EDU-QA-045
        self.assertFalse(
            has_unresolved_reference(
                "How many trees are typically used in a random forest, and how can this number be optimized?",
                None,
            )
        )  # EDU-QA-026
        self.assertFalse(
            has_unresolved_reference(
                "When were InstructGPT and ChatGPT released, and how were they trained?",
                None,
            )
        )  # EDU-QA-043
        self.assertFalse(
            has_unresolved_reference(
                "What is the credit assignment path (CAP) in deep learning, according to this document?",
                None,
            )
        )  # EDU-QA-004 — "this document" tu tro ve chinh no, khong mo ho

    def test_short_orphan_pronoun_stays_unresolved_even_with_new_threshold(self):
        # Bao ve true positive da co (EDU-ABS-008): 5 tu truoc "no", duoi
        # nguong 7 — khong duoc de nguong moi lam mat tac dung chan.
        self.assertTrue(has_unresolved_reference("Ai đã phát minh ra nó?", None))


if __name__ == "__main__":
    unittest.main()
