import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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

    def test_items_passing_verification_are_returned(self):
        llm = FakeLLMClient(scripted_responses=[GENERATOR_JSON_TWO_ITEMS, "CÓ", "CÓ"])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=2)

        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], FlashcardItem)
        self.assertEqual(result[0].front, "CNN là gì?")
        self.assertEqual(result[0].source_document, "cnn.pdf")
        self.assertEqual(len(llm.prompts_received), 3)

    def test_item_failing_verification_is_filtered_out(self):
        llm = FakeLLMClient(scripted_responses=[GENERATOR_JSON_TWO_ITEMS, "CÓ", "KHÔNG"])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=2)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].front, "CNN là gì?")

    def test_malformed_json_returns_empty_list(self):
        llm = FakeLLMClient(scripted_responses=["không phải JSON"])
        result = generate_flashcards(chunks=[make_chunk()], llm_client=llm, num_cards=2)
        self.assertEqual(result, [])

    def test_item_with_missing_field_is_skipped_without_extra_verifier_call(self):
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


if __name__ == "__main__":
    unittest.main()
