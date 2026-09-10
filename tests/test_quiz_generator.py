import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.llm.quiz_generator import QuizItem, generate_quiz
from app.llm.rag import RetrievedChunk


class FakeLLMClient:
    def __init__(self, scripted_responses):
        self.scripted_responses = list(scripted_responses)
        self.prompts_received = []

    def complete(self, prompt: str) -> str:
        self.prompts_received.append(prompt)
        return self.scripted_responses.pop(0)


def make_chunk(text="Nội dung nguồn về RAG.", doc="slide1.pdf", pos="Trang 1"):
    return RetrievedChunk(text=text, document_name=doc, position_ref=pos, score=0.9)


def make_judge(valid=True, ambiguous=False, difficulty_match=True, content_type="concept"):
    """Chuỗi JSON phán quyết của LLM-judge (Learning Loop Phase 5) — thay cho
    verdict CÓ/KHÔNG đơn thuần trước đây, xem docstring ở
    app/llm/quiz_generator.py::_build_item_judge_prompt."""
    return (
        '{"valid": %s, "ambiguous": %s, "difficulty_match": %s, "content_type": "%s"}'
        % (str(valid).lower(), str(ambiguous).lower(), str(difficulty_match).lower(), content_type)
    )


GENERATOR_JSON_TWO_ITEMS = """
[
  {"question": "RAG là gì?", "options": ["A", "B", "C", "D"], "correct_answer": "A", "explanation": "vì...", "chunk_index": 0},
  {"question": "RAG dùng để làm gì?", "options": ["A", "B", "C", "D"], "correct_answer": "B", "explanation": "vì...", "chunk_index": 0}
]
"""


class TestGenerateQuiz(unittest.TestCase):
    def test_no_chunks_returns_empty_without_calling_llm(self):
        llm = FakeLLMClient(scripted_responses=[])
        result = generate_quiz(chunks=[], llm_client=llm, num_questions=5)
        self.assertEqual(result, [])
        self.assertEqual(len(llm.prompts_received), 0)

    def test_items_passing_judge_are_returned(self):
        llm = FakeLLMClient(scripted_responses=[GENERATOR_JSON_TWO_ITEMS, make_judge(), make_judge()])
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=2)

        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], QuizItem)
        self.assertEqual(result[0].question, "RAG là gì?")
        self.assertEqual(result[0].source_document, "slide1.pdf")
        self.assertEqual(result[0].source_position, "Trang 1")
        # 1 lượt gọi generator + 2 lượt gọi judge (1 mỗi item, verdict nội dung
        # + mơ hồ + độ khó + phân loại gộp làm MỘT lượt — Phase 5) = 3
        self.assertEqual(len(llm.prompts_received), 3)

    def test_item_failing_judge_is_filtered_out(self):
        # BUG-003: 1 câu hợp lệ (< 2 yêu cầu) là thành công MỘT PHẦN -> kích
        # hoạt lượt bù (xem TestBoundedRetryOnUndergeneration bên dưới); lượt
        # bù ở đây trả "[]" nên tổng vẫn dừng ở 1.
        llm = FakeLLMClient(
            scripted_responses=[GENERATOR_JSON_TWO_ITEMS, make_judge(), make_judge(valid=False), "[]"]
        )
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=2)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].question, "RAG là gì?")

    def test_malformed_json_returns_empty_list(self):
        llm = FakeLLMClient(scripted_responses=["đây không phải JSON hợp lệ"])
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=2)
        self.assertEqual(result, [])

    def test_item_with_missing_field_is_skipped_without_extra_judge_call(self):
        broken_json = '[{"question": "Thiếu đáp án", "options": ["A", "B"], "chunk_index": 0}]'
        llm = FakeLLMClient(scripted_responses=[broken_json])
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=1)
        self.assertEqual(result, [])
        # không được gọi judge cho item thiếu field - đỡ tốn quota Gemini free tier
        self.assertEqual(len(llm.prompts_received), 1)

    def test_item_with_invalid_chunk_index_is_skipped(self):
        bad_index_json = '[{"question": "Q?", "options": ["A","B"], "correct_answer": "A", "explanation": "x", "chunk_index": 5}]'
        llm = FakeLLMClient(scripted_responses=[bad_index_json])
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=1)
        self.assertEqual(result, [])
        self.assertEqual(len(llm.prompts_received), 1)

    def test_generator_prompt_includes_all_chunks_and_num_questions(self):
        llm = FakeLLMClient(scripted_responses=["[]"])
        chunks = [make_chunk(text="Đoạn A", pos="Trang 1"), make_chunk(text="Đoạn B", pos="Trang 2")]
        generate_quiz(chunks=chunks, llm_client=llm, num_questions=7)
        prompt = llm.prompts_received[0]
        self.assertIn("Đoạn A", prompt)
        self.assertIn("Đoạn B", prompt)
        self.assertIn("7", prompt)

    def test_difficulty_instruction_included_when_provided(self):
        llm = FakeLLMClient(scripted_responses=["[]"])
        generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=3, difficulty="beginner")
        prompt = llm.prompts_received[0]
        self.assertIn("định nghĩa/khái niệm cơ bản", prompt)

    def test_no_difficulty_produces_prompt_without_instruction(self):
        llm = FakeLLMClient(scripted_responses=["[]"])
        generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=3)
        prompt = llm.prompts_received[0]
        self.assertNotIn("định nghĩa/khái niệm cơ bản", prompt)


ONE_ITEM_JSON = """
[{"question": "Câu bù thêm?", "options": ["A", "B", "C", "D"], "correct_answer": "A", "explanation": "vì...", "chunk_index": 0}]
"""


class TestBoundedRetryOnUndergeneration(unittest.TestCase):
    """BUG-003 — kết quả ít hơn num_questions yêu cầu không còn âm thầm trả về
    như vậy: nếu lượt đầu có kết quả THẬT (>0) nhưng vẫn thiếu, gọi thêm MỘT
    lượt bù bị chặn (không lặp vô hạn)."""

    def test_partial_result_triggers_one_top_up_attempt(self):
        # Lượt 1: 1/2 câu qua judge (KHÔNG cho câu 2). Lượt 2 (bù 1 câu còn
        # thiếu): trả về đúng 1 câu mới, judge hợp lệ.
        llm = FakeLLMClient(
            scripted_responses=[
                GENERATOR_JSON_TWO_ITEMS, make_judge(), make_judge(valid=False), ONE_ITEM_JSON, make_judge()
            ]
        )
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=2)

        self.assertEqual(len(result), 2)
        self.assertEqual({r.question for r in result}, {"RAG là gì?", "Câu bù thêm?"})

    def test_retry_is_bounded_not_infinite(self):
        # Lượt bù CŨNG chỉ ra 1 câu qua judge trong khi vẫn thiếu 1 -> KHÔNG
        # có lượt thứ ba, dừng lại ở kết quả đã có (bounded retry).
        llm = FakeLLMClient(
            scripted_responses=[
                GENERATOR_JSON_TWO_ITEMS, make_judge(), make_judge(valid=False), ONE_ITEM_JSON, make_judge()
            ]
        )
        generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=5)
        # 2 lượt sinh (1 generator + judge mỗi lượt): lượt1 = 1 gen + 2
        # judge (2 raw item), lượt2 = 1 gen + 1 judge (1 raw item) = 5 tổng.
        self.assertEqual(len(llm.prompts_received), 5)

    def test_zero_items_on_first_attempt_does_not_retry(self):
        # Lượt đầu ra 0 câu hoàn toàn (không phải thiếu MỘT PHẦN) -> không bù,
        # vẫn đúng hành vi cũ (test_malformed_json_returns_empty_list ở trên).
        llm = FakeLLMClient(scripted_responses=["không phải JSON"])
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=3)
        self.assertEqual(result, [])
        self.assertEqual(len(llm.prompts_received), 1)

    def test_top_up_attempt_does_not_duplicate_already_collected_questions(self):
        # LLM lặp lại chính câu hỏi đã có ở lượt bù -> bị lọc trùng, không
        # được cộng thêm vào kết quả.
        duplicate_question_json = (
            '[{"question": "RAG là gì?", "options": ["A","B","C","D"], '
            '"correct_answer": "A", "explanation": "x", "chunk_index": 0}]'
        )
        llm = FakeLLMClient(
            scripted_responses=[
                GENERATOR_JSON_TWO_ITEMS, make_judge(), make_judge(valid=False), duplicate_question_json
            ]
        )
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=2)
        self.assertEqual(len(result), 1)

    def test_exact_count_on_first_attempt_does_not_trigger_retry(self):
        llm = FakeLLMClient(scripted_responses=[GENERATOR_JSON_TWO_ITEMS, make_judge(), make_judge()])
        generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=2)
        self.assertEqual(len(llm.prompts_received), 3)  # không có lượt bù


class TestDuplicateDetection(unittest.TestCase):
    """Learning Loop Phase 4 — phát hiện trùng lặp DETERMINISTIC (so từ khoá,
    không dùng LLM-judge), mở rộng dedup đã có
    (test_top_up_attempt_does_not_duplicate_already_collected_questions) từ
    so khớp CHÍNH XÁC sang phát hiện câu hỏi GẦN GIỐNG (diễn đạt lại), và
    chặn TRƯỚC khi gọi judge để đỡ tốn quota thay vì lọc sau khi đã đánh giá."""

    def test_exact_duplicate_within_same_batch_is_dropped_without_extra_judge_call(self):
        # num_questions=1 (không phải 2): đủ ngay từ câu đầu, không kích hoạt
        # lượt bù BUG-003 — cô lập đúng hành vi đang test (dedup TRƯỚC judge),
        # không lẫn với cơ chế bù thiếu vốn đã có sẵn.
        json_with_exact_dup = """
        [
          {"question": "RAG là gì?", "options": ["A","B","C","D"], "correct_answer": "A", "explanation": "vì...", "chunk_index": 0},
          {"question": "RAG là gì?", "options": ["A","B","C","D"], "correct_answer": "A", "explanation": "vì...", "chunk_index": 0}
        ]
        """
        llm = FakeLLMClient(scripted_responses=[json_with_exact_dup, make_judge()])
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=1)

        self.assertEqual(len(result), 1)
        # 1 lượt gọi generator + 1 lượt judge (câu 2 bị bỏ TRƯỚC khi judge vì
        # trùng câu 1) = 2, không phải 3.
        self.assertEqual(len(llm.prompts_received), 2)

    def test_paraphrased_duplicate_within_same_batch_is_dropped(self):
        json_with_paraphrase = """
        [
          {"question": "RAG là kỹ thuật gì trong xử lý ngôn ngữ tự nhiên?", "options": ["A","B","C","D"], "correct_answer": "A", "explanation": "vì...", "chunk_index": 0},
          {"question": "Kỹ thuật RAG trong xử lý ngôn ngữ tự nhiên là gì?", "options": ["A","B","C","D"], "correct_answer": "A", "explanation": "vì...", "chunk_index": 0}
        ]
        """
        llm = FakeLLMClient(scripted_responses=[json_with_paraphrase, make_judge()])
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=1)

        self.assertEqual(len(result), 1)

    def test_questions_about_different_things_are_both_kept(self):
        llm = FakeLLMClient(scripted_responses=[GENERATOR_JSON_TWO_ITEMS, make_judge(), make_judge()])
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=2)

        self.assertEqual(len(result), 2)

    def test_paraphrased_duplicate_against_earlier_top_up_batch_is_dropped(self):
        # Mirror test_top_up_attempt_does_not_duplicate_already_collected_questions
        # nhưng câu ở lượt bù được DIỄN ĐẠT LẠI thay vì lặp y hệt — dedup chỉ
        # so chuỗi chính xác sẽ bỏ lọt trường hợp này.
        paraphrased_top_up_json = (
            '[{"question": "Định nghĩa của RAG là gì?", "options": ["A","B","C","D"], '
            '"correct_answer": "A", "explanation": "x", "chunk_index": 0}]'
        )
        llm = FakeLLMClient(
            scripted_responses=[
                GENERATOR_JSON_TWO_ITEMS, make_judge(), make_judge(valid=False), paraphrased_top_up_json
            ]
        )
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=2)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].question, "RAG là gì?")


class TestIntermediateDifficulty(unittest.TestCase):
    def test_intermediate_instruction_is_included_in_prompt(self):
        llm = FakeLLMClient(scripted_responses=["[]"])
        generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=3, difficulty="intermediate")
        prompt = llm.prompts_received[0]
        self.assertIn("vận dụng", prompt)

    def test_three_difficulty_levels_give_three_distinct_instructions(self):
        from app.llm.quiz_generator import _DIFFICULTY_INSTRUCTIONS

        texts = {
            _DIFFICULTY_INSTRUCTIONS["beginner"],
            _DIFFICULTY_INSTRUCTIONS["intermediate"],
            _DIFFICULTY_INSTRUCTIONS["advanced"],
        }
        self.assertEqual(len(texts), 3)


class TestLLMJudgeQualityGate(unittest.TestCase):
    """Learning Loop Phase 5 — LLM-judge cho độ mơ hồ/độ khó phù hợp và phân
    loại nội dung theo dạng kiến thức. Gộp vào MỘT lượt gọi cùng với việc
    xác minh nội dung đã có (không thêm lượt gọi LLM riêng) để không tăng
    thêm chi phí/độ trễ so với trước — đây chính là lý do phase này từng bị
    hoãn lại (xem docstring _build_item_judge_prompt)."""

    ONE_ITEM_JSON = (
        '[{"question": "RAG là gì?", "options": ["A","B","C","D"], "correct_answer": "A", '
        '"explanation": "vì...", "chunk_index": 0}]'
    )

    def test_ambiguous_item_is_filtered_out_even_if_content_valid(self):
        llm = FakeLLMClient(scripted_responses=[self.ONE_ITEM_JSON, make_judge(ambiguous=True)])
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=1)
        self.assertEqual(result, [])

    def test_off_difficulty_item_is_filtered_out_when_difficulty_requested(self):
        llm = FakeLLMClient(scripted_responses=[self.ONE_ITEM_JSON, make_judge(difficulty_match=False)])
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=1, difficulty="beginner")
        self.assertEqual(result, [])

    def test_difficulty_match_is_ignored_when_no_difficulty_was_requested(self):
        # Không truyền difficulty -> không có gì để so khớp, difficulty_match
        # (dù LLM trả false) không được dùng để loại câu hỏi.
        llm = FakeLLMClient(scripted_responses=[self.ONE_ITEM_JSON, make_judge(difficulty_match=False)])
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=1)
        self.assertEqual(len(result), 1)

    def test_content_type_is_attached_to_returned_item(self):
        llm = FakeLLMClient(scripted_responses=[self.ONE_ITEM_JSON, make_judge(content_type="formula")])
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=1)
        self.assertEqual(result[0].content_type, "formula")

    def test_malformed_judge_json_filters_item_out(self):
        llm = FakeLLMClient(scripted_responses=[self.ONE_ITEM_JSON, "không phải JSON"])
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=1)
        self.assertEqual(result, [])

    def test_judge_json_missing_required_field_filters_item_out(self):
        incomplete_judgment = '{"valid": true, "ambiguous": false}'
        llm = FakeLLMClient(scripted_responses=[self.ONE_ITEM_JSON, incomplete_judgment])
        result = generate_quiz(chunks=[make_chunk()], llm_client=llm, num_questions=1)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
