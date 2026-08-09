import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.llm.rag import (
    NO_CONTEXT_MESSAGE,
    NOT_GROUNDED_MESSAGE,
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


if __name__ == "__main__":
    unittest.main()
