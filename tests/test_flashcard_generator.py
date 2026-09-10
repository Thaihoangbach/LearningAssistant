import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.llm.flashcard_generator import FlashcardItem, generate_flashcards
from app.llm.rag import RetrievedChunk


class FakeLLMClient:
    def __init__(self, scripted_responses):
        self.scripted_responses = list(scripted_responses)
        self.prompts_received = []

    def complete(self, prompt: str) -> str:
        self.prompts_received.append(prompt)
        return self.scripted_responses.pop(0)


def make_chunk(text="Nội dung nguồn về CNN.", doc="cnn.pdf", pos="Trang 1"):
    return RetrievedChunk(text=text, document_name=doc, position_ref=pos, score=0.9)


def make_judge(valid=True, ambiguous=False, content_type="concept"):
    """Chuỗi JSON phán quyết của LLM-judge (Learning Loop Phase 5) — thay cho
    verdict CÓ/KHÔNG đơn thuần trước đây, mirror
    app/llm/quiz_generator.py::_build_item_judge_prompt (flashcard không có
    khái niệm "độ khó yêu cầu" nên không có trường difficulty_match)."""
    return '{"valid": %s, "ambiguous": %s, "content_type": "%s"}' % (
        str(valid).lower(),
        str(ambiguous).lower(),
        content_type,
    )


GENERATOR_JSON_TWO_ITEMS = """
[
  {"front": "CNN là gì?", "back": "Convolutional Neural Network.", "chunk_index": 0},
  {"front": "Convolution dùng để làm gì?", "back": "Trích xuất đặc trưng.", "chunk_index": 0}
]
"""


class TestGenerateFlashcards(unittest.TestCase):
    def test_no_chunks_returns_empty_without_calling_llm(self):
        llm = FakeLLMClient(scripted_responses=[])
        result = generate_flashcards(chunks=[], llm_client=llm, num_cards=5)
        self.assertEqual(result, [])
        self.assertEqual(len(llm.prompts_received), 0)

    def test_items_passing_judge_are_returned(self):
        llm = FakeLLMClient(scripted_responses=[GENERATOR_JSON_TWO_ITEMS, make_judge(), make_judge()])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=2)

        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], FlashcardItem)
        self.assertEqual(result[0].front, "CNN là gì?")
        self.assertEqual(result[0].source_document, "cnn.pdf")
        self.assertEqual(len(llm.prompts_received), 3)

    def test_item_failing_judge_is_filtered_out(self):
        # num_cards=1 (không phải 2): đủ ngay từ thẻ đầu, không kích hoạt lượt
        # bù (xem TestBoundedRetryOnUndergeneration bên dưới) — cô lập đúng
        # hành vi đang test.
        llm = FakeLLMClient(scripted_responses=[GENERATOR_JSON_TWO_ITEMS, make_judge(), make_judge(valid=False)])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].front, "CNN là gì?")

    def test_malformed_json_returns_empty_list(self):
        llm = FakeLLMClient(scripted_responses=["không phải JSON"])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=2)
        self.assertEqual(result, [])

    def test_item_with_missing_field_is_skipped_without_extra_judge_call(self):
        broken_json = '[{"front": "Thiếu back", "chunk_index": 0}]'
        llm = FakeLLMClient(scripted_responses=[broken_json])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=1)
        self.assertEqual(result, [])
        self.assertEqual(len(llm.prompts_received), 1)

    def test_item_with_invalid_chunk_index_is_skipped(self):
        bad_index_json = '[{"front": "F", "back": "B", "chunk_index": 5}]'
        llm = FakeLLMClient(scripted_responses=[bad_index_json])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=1)
        self.assertEqual(result, [])
        self.assertEqual(len(llm.prompts_received), 1)

    def test_generator_prompt_includes_all_chunks_and_num_cards(self):
        llm = FakeLLMClient(scripted_responses=["[]"])
        chunks = [make_chunk(text="Đoạn A", pos="Trang 1"), make_chunk(text="Đoạn B", pos="Trang 2")]
        generate_flashcards(chunks=chunks, llm_client=llm, num_cards=8)
        prompt = llm.prompts_received[0]
        self.assertIn("Đoạn A", prompt)
        self.assertIn("Đoạn B", prompt)
        self.assertIn("8", prompt)


ONE_ITEM_JSON = """
[{"front": "Thẻ bù thêm?", "back": "Đáp án.", "chunk_index": 0}]
"""


class TestBoundedRetryOnUndergeneration(unittest.TestCase):
    """Mirror tests/test_quiz_generator.py::TestBoundedRetryOnUndergeneration
    (BUG-003) — flashcard dùng chung app/llm/rag.py::LLMClient nhưng trước
    Phase 4 chưa có cơ chế bù khi verifier loại bớt thẻ."""

    def test_partial_result_triggers_one_top_up_attempt(self):
        llm = FakeLLMClient(
            scripted_responses=[
                GENERATOR_JSON_TWO_ITEMS, make_judge(), make_judge(valid=False), ONE_ITEM_JSON, make_judge()
            ]
        )
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=2)

        self.assertEqual(len(result), 2)
        self.assertEqual({r.front for r in result}, {"CNN là gì?", "Thẻ bù thêm?"})

    def test_retry_is_bounded_not_infinite(self):
        llm = FakeLLMClient(
            scripted_responses=[
                GENERATOR_JSON_TWO_ITEMS, make_judge(), make_judge(valid=False), ONE_ITEM_JSON, make_judge()
            ]
        )
        generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=5)
        self.assertEqual(len(llm.prompts_received), 5)

    def test_zero_items_on_first_attempt_does_not_retry(self):
        llm = FakeLLMClient(scripted_responses=["không phải JSON"])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=3)
        self.assertEqual(result, [])
        self.assertEqual(len(llm.prompts_received), 1)

    def test_exact_count_on_first_attempt_does_not_trigger_retry(self):
        llm = FakeLLMClient(scripted_responses=[GENERATOR_JSON_TWO_ITEMS, make_judge(), make_judge()])
        generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=2)
        self.assertEqual(len(llm.prompts_received), 3)


class TestDuplicateDetection(unittest.TestCase):
    """Mirror tests/test_quiz_generator.py::TestDuplicateDetection."""

    def test_exact_duplicate_within_same_batch_is_dropped_without_extra_judge_call(self):
        json_with_exact_dup = """
        [
          {"front": "CNN là gì?", "back": "Convolutional Neural Network.", "chunk_index": 0},
          {"front": "CNN là gì?", "back": "Convolutional Neural Network.", "chunk_index": 0}
        ]
        """
        llm = FakeLLMClient(scripted_responses=[json_with_exact_dup, make_judge()])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=1)

        self.assertEqual(len(result), 1)
        self.assertEqual(len(llm.prompts_received), 2)

    def test_paraphrased_duplicate_within_same_batch_is_dropped(self):
        json_with_paraphrase = """
        [
          {"front": "CNN là kỹ thuật gì trong xử lý ảnh?", "back": "A", "chunk_index": 0},
          {"front": "Kỹ thuật CNN trong xử lý ảnh là gì?", "back": "A", "chunk_index": 0}
        ]
        """
        llm = FakeLLMClient(scripted_responses=[json_with_paraphrase, make_judge()])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=1)

        self.assertEqual(len(result), 1)


class TestLLMJudgeQualityGate(unittest.TestCase):
    """Learning Loop Phase 5 — mirror tests/test_quiz_generator.py::
    TestLLMJudgeQualityGate. Flashcard không có "độ khó yêu cầu" nên chỉ xét
    ambiguous + content_type, không có difficulty_match."""

    ONE_ITEM_JSON = '[{"front": "CNN là gì?", "back": "Convolutional Neural Network.", "chunk_index": 0}]'

    def test_ambiguous_item_is_filtered_out_even_if_content_valid(self):
        llm = FakeLLMClient(scripted_responses=[self.ONE_ITEM_JSON, make_judge(ambiguous=True)])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=1)
        self.assertEqual(result, [])

    def test_content_type_is_attached_to_returned_item(self):
        llm = FakeLLMClient(scripted_responses=[self.ONE_ITEM_JSON, make_judge(content_type="definition")])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=1)
        self.assertEqual(result[0].content_type, "definition")

    def test_malformed_judge_json_filters_item_out(self):
        llm = FakeLLMClient(scripted_responses=[self.ONE_ITEM_JSON, "không phải JSON"])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=1)
        self.assertEqual(result, [])

    def test_judge_json_missing_required_field_filters_item_out(self):
        incomplete_judgment = '{"valid": true}'
        llm = FakeLLMClient(scripted_responses=[self.ONE_ITEM_JSON, incomplete_judgment])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=1)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
