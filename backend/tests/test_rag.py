import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.llm.rag import (
    NO_CONTEXT_MESSAGE,
    NOT_GROUNDED_MESSAGE,
    ConversationTurn,
    RetrievedChunk,
    answer_question,
)


class FakeLLMClient:
    """LLM giả lập để test orchestration logic mà không cần gọi Gemini thật.

    `scripted_responses` là danh sách câu trả lời sẽ trả về lần lượt theo
    đúng thứ tự gọi: [generator_response, verifier_response, ...].
    """

    def __init__(self, scripted_responses):
        self.scripted_responses = list(scripted_responses)
        self.prompts_received = []

    def complete(self, prompt: str) -> str:
        self.prompts_received.append(prompt)
        return self.scripted_responses.pop(0)


class TestAnswerQuestion(unittest.TestCase):
    def make_chunk(self, score=0.8, text="Nội dung nguồn.", doc="slide1.pdf", pos="Trang 1"):
        return RetrievedChunk(text=text, document_name=doc, position_ref=pos, score=score)

    def test_no_relevant_chunk_returns_no_context_message_without_calling_llm(self):
        llm = FakeLLMClient(scripted_responses=[])
        result = answer_question(
            question="RAG là gì?",
            retrieved_chunks=[self.make_chunk(score=0.1)],
            llm_client=llm,
            min_score=0.3,
        )
        self.assertEqual(result.answer, NO_CONTEXT_MESSAGE)
        self.assertFalse(result.is_grounded)
        self.assertEqual(result.sources, [])
        self.assertEqual(len(llm.prompts_received), 0)

    def test_grounded_answer_returned_when_verifier_confirms(self):
        llm = FakeLLMClient(scripted_responses=["Đây là câu trả lời dựa trên tài liệu.", "CÓ"])
        chunk = self.make_chunk(score=0.9)
        result = answer_question(
            question="RAG là gì?",
            retrieved_chunks=[chunk],
            llm_client=llm,
            min_score=0.3,
        )
        self.assertTrue(result.is_grounded)
        self.assertEqual(result.answer, "Đây là câu trả lời dựa trên tài liệu.")
        self.assertEqual(result.sources, [chunk])
        # đúng 2 lượt gọi: generator rồi verifier (kỹ thuật đã chốt trong architecture doc)
        self.assertEqual(len(llm.prompts_received), 2)

    def test_answer_rejected_when_verifier_denies(self):
        llm = FakeLLMClient(scripted_responses=["Câu trả lời nghe hợp lý nhưng không có trong tài liệu.", "KHÔNG"])
        result = answer_question(
            question="RAG là gì?",
            retrieved_chunks=[self.make_chunk(score=0.9)],
            llm_client=llm,
            min_score=0.3,
        )
        self.assertFalse(result.is_grounded)
        self.assertEqual(result.answer, NOT_GROUNDED_MESSAGE)
        self.assertEqual(result.sources, [])

    def test_chunks_below_threshold_are_filtered_out(self):
        llm = FakeLLMClient(scripted_responses=["Trả lời.", "CÓ"])
        strong = self.make_chunk(score=0.9, text="Chunk mạnh", pos="Trang 2")
        weak = self.make_chunk(score=0.05, text="Chunk yếu", pos="Trang 5")
        result = answer_question(
            question="RAG là gì?",
            retrieved_chunks=[weak, strong],
            llm_client=llm,
            min_score=0.3,
        )
        self.assertEqual(result.sources, [strong])

    def test_verifier_prompt_includes_draft_answer_and_context(self):
        llm = FakeLLMClient(scripted_responses=["Câu trả lời nháp.", "CÓ"])
        chunk = self.make_chunk(text="Đoạn trích gốc quan trọng.")
        answer_question(
            question="Hỏi gì đó?",
            retrieved_chunks=[chunk],
            llm_client=llm,
            min_score=0.3,
        )
        generator_prompt, verifier_prompt = llm.prompts_received
        self.assertIn("Hỏi gì đó?", generator_prompt)
        self.assertIn("Đoạn trích gốc quan trọng.", generator_prompt)
        self.assertIn("Câu trả lời nháp.", verifier_prompt)
        self.assertIn("Đoạn trích gốc quan trọng.", verifier_prompt)

    def test_verifier_prompt_accepts_inferred_content_not_only_verbatim(self):
        llm = FakeLLMClient(scripted_responses=["Trả lời.", "CÓ"])
        answer_question(
            question="RAG là gì?",
            retrieved_chunks=[self.make_chunk()],
            llm_client=llm,
            min_score=0.3,
        )
        _, verifier_prompt = llm.prompts_received
        self.assertIn("suy ra rõ ràng", verifier_prompt)

    def test_duplicate_sources_are_deduplicated_in_result_but_not_in_context(self):
        llm = FakeLLMClient(scripted_responses=["Trả lời tổng hợp.", "CÓ"])
        chunk_a = self.make_chunk(text="Đoạn A trong cùng section.", doc="d.docx", pos="Mục 1")
        chunk_b = self.make_chunk(text="Đoạn B trong cùng section.", doc="d.docx", pos="Mục 1")
        result = answer_question(
            question="Hỏi gì đó?",
            retrieved_chunks=[chunk_a, chunk_b],
            llm_client=llm,
            min_score=0.3,
        )
        self.assertEqual(len(result.sources), 1)
        generator_prompt, _ = llm.prompts_received
        self.assertIn("Đoạn A trong cùng section.", generator_prompt)
        self.assertIn("Đoạn B trong cùng section.", generator_prompt)

    def test_conversation_history_included_in_generator_but_not_verifier_prompt(self):
        llm = FakeLLMClient(scripted_responses=["Trả lời tiếp nối.", "CÓ"])
        chunk = self.make_chunk(text="Transformer không dùng RNN vì có self-attention.")
        history = [ConversationTurn(question="Transformer là gì?", answer="Là một kiến trúc mạng nơ-ron.")]
        answer_question(
            question="Vậy tại sao nó không cần RNN?",
            retrieved_chunks=[chunk],
            llm_client=llm,
            min_score=0.3,
            conversation_history=history,
        )
        generator_prompt, verifier_prompt = llm.prompts_received
        self.assertIn("Transformer là gì?", generator_prompt)
        self.assertIn("Là một kiến trúc mạng nơ-ron.", generator_prompt)
        self.assertNotIn("Transformer là gì?", verifier_prompt)

    def test_no_history_produces_prompt_without_history_block(self):
        llm = FakeLLMClient(scripted_responses=["Trả lời.", "CÓ"])
        answer_question(
            question="RAG là gì?",
            retrieved_chunks=[self.make_chunk()],
            llm_client=llm,
            min_score=0.3,
            conversation_history=None,
        )
        generator_prompt, _ = llm.prompts_received
        self.assertNotIn("Lịch sử hội thoại", generator_prompt)

    def test_simplify_request_adds_instruction_to_generator_prompt(self):
        llm = FakeLLMClient(scripted_responses=["Trả lời đơn giản.", "CÓ"])
        answer_question(
            question="Tôi chưa hiểu Attention hoạt động thế nào, giải thích đơn giản hơn được không?",
            retrieved_chunks=[self.make_chunk()],
            llm_client=llm,
            min_score=0.3,
        )
        generator_prompt, _ = llm.prompts_received
        self.assertIn("ví dụ cụ thể và thuật ngữ cơ bản", generator_prompt)

    def test_normal_question_does_not_add_simplify_instruction(self):
        llm = FakeLLMClient(scripted_responses=["Trả lời.", "CÓ"])
        answer_question(
            question="RAG là gì?",
            retrieved_chunks=[self.make_chunk()],
            llm_client=llm,
            min_score=0.3,
        )
        generator_prompt, _ = llm.prompts_received
        self.assertNotIn("ví dụ cụ thể và thuật ngữ cơ bản", generator_prompt)

    def test_generator_prompt_always_instructs_to_flag_conflicting_sources(self):
        llm = FakeLLMClient(scripted_responses=["Trả lời.", "CÓ"])
        answer_question(
            question="RAG là gì?",
            retrieved_chunks=[self.make_chunk()],
            llm_client=llm,
            min_score=0.3,
        )
        generator_prompt, _ = llm.prompts_received
        self.assertIn("mâu thuẫn", generator_prompt)

    def test_level_instruction_included_when_provided(self):
        llm = FakeLLMClient(scripted_responses=["Trả lời cho beginner.", "CÓ"])
        answer_question(
            question="Gradient Descent là gì?",
            retrieved_chunks=[self.make_chunk()],
            llm_client=llm,
            min_score=0.3,
            level="beginner",
        )
        generator_prompt, _ = llm.prompts_received
        self.assertIn("trình độ mới bắt đầu", generator_prompt)

    def test_different_levels_produce_different_instructions(self):
        llm = FakeLLMClient(scripted_responses=["Trả lời cho advanced.", "CÓ"])
        answer_question(
            question="Gradient Descent là gì?",
            retrieved_chunks=[self.make_chunk()],
            llm_client=llm,
            min_score=0.3,
            level="advanced",
        )
        generator_prompt, _ = llm.prompts_received
        self.assertIn("nâng cao", generator_prompt)
        self.assertNotIn("trình độ mới bắt đầu", generator_prompt)

    def test_no_level_produces_prompt_without_level_instruction(self):
        llm = FakeLLMClient(scripted_responses=["Trả lời.", "CÓ"])
        answer_question(
            question="Gradient Descent là gì?",
            retrieved_chunks=[self.make_chunk()],
            llm_client=llm,
            min_score=0.3,
        )
        generator_prompt, _ = llm.prompts_received
        self.assertNotIn("trình độ mới bắt đầu", generator_prompt)
        self.assertNotIn("nâng cao", generator_prompt)

    def test_multi_document_chunks_all_included_in_generator_context(self):
        llm = FakeLLMClient(scripted_responses=["Trả lời tổng hợp.", "CÓ"])
        cnn_chunk = self.make_chunk(text="CNN dùng convolution.", doc="cnn.pdf", pos="Trang 1")
        vit_chunk = self.make_chunk(text="Vision Transformer dùng self-attention.", doc="vit.pdf", pos="Trang 3")
        answer_question(
            question="So sánh CNN và Vision Transformer.",
            retrieved_chunks=[cnn_chunk, vit_chunk],
            llm_client=llm,
            min_score=0.3,
        )
        generator_prompt, _ = llm.prompts_received
        self.assertIn("cnn.pdf", generator_prompt)
        self.assertIn("vit.pdf", generator_prompt)
        self.assertIn("CNN dùng convolution.", generator_prompt)
        self.assertIn("Vision Transformer dùng self-attention.", generator_prompt)


if __name__ == "__main__":
    unittest.main()
