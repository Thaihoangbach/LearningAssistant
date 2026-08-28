import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.llm.rag import RetrievedChunk
from app.qa_pipeline import answer_with_fallback


class FakeLLMClient:
    def __init__(self, scripted_responses):
        self.scripted_responses = list(scripted_responses)
        self.prompts_received = []

    def complete(self, prompt):
        self.prompts_received.append(prompt)
        return self.scripted_responses.pop(0)


def _chunk(text="Nội dung.", doc="a.pdf", pos="Trang 1", score=0.8, cid="c1", did="d1"):
    return RetrievedChunk(
        text=text, document_name=doc, position_ref=pos, score=score, chunk_id=cid, document_id=did
    )


DOCS = [{"id": "d1", "file_name": "a.pdf"}]


class TestAnswerWithFallback(unittest.TestCase):
    def test_first_pass_success_does_not_trigger_second_pass(self):
        calls = []

        def retrieve(query, top_k, mode):
            calls.append(mode)
            return [_chunk()]

        llm = FakeLLMClient(["Trả lời tốt. [1]", "CÓ"])
        result = answer_with_fallback(
            question="Hỏi?", llm_client=llm, retrieve_fn=retrieve, searched_documents=DOCS
        )
        self.assertTrue(result.is_grounded)
        self.assertFalse(result.abstained)
        self.assertEqual(calls, ["strict"])

    def test_second_pass_runs_when_first_pass_not_grounded(self):
        calls = []

        def retrieve(query, top_k, mode):
            calls.append(mode)
            return [_chunk()]

        # lượt 1: verifier bác; lượt 2: verifier chấp nhận
        llm = FakeLLMClient(["Nháp sai. [1]", "KHÔNG", "Nháp đúng. [1]", "CÓ"])
        result = answer_with_fallback(
            question="Hỏi?", llm_client=llm, retrieve_fn=retrieve, searched_documents=DOCS
        )
        self.assertTrue(result.is_grounded)
        self.assertEqual(calls, ["strict", "wide"])
        self.assertEqual(result.search_report.passes_run, 2)

    def test_abstains_with_negative_evidence_when_both_passes_fail(self):
        def retrieve(query, top_k, mode):
            return [_chunk(text="Nội dung không liên quan.", score=0.11)]

        llm = FakeLLMClient(["Nháp 1. [1]", "KHÔNG", "Nháp 2. [1]", "KHÔNG"])
        result = answer_with_fallback(
            question="Hỏi?", llm_client=llm, retrieve_fn=retrieve, searched_documents=DOCS
        )
        self.assertTrue(result.abstained)
        self.assertFalse(result.is_grounded)
        self.assertEqual(result.search_report.passes_run, 2)
        self.assertEqual(result.search_report.searched_documents, DOCS)
        self.assertEqual(len(result.search_report.near_misses), 1)
        self.assertEqual(result.search_report.near_misses[0].position_ref, "Trang 1")

    def test_near_misses_are_capped_and_sorted_by_score(self):
        # chunk_id phải khác nhau như dữ liệu thật — nếu trùng, chúng bị khử
        # trùng thành một đoạn duy nhất (xem _dedupe_key trong qa_pipeline).
        def retrieve(query, top_k, mode):
            return [
                _chunk(pos="Trang 1", score=0.05, cid="c1"),
                _chunk(pos="Trang 2", score=0.30, cid="c2"),
                _chunk(pos="Trang 3", score=0.20, cid="c3"),
                _chunk(pos="Trang 4", score=0.01, cid="c4"),
            ]

        llm = FakeLLMClient(["Nháp 1. [1]", "KHÔNG", "Nháp 2. [1]", "KHÔNG"])
        result = answer_with_fallback(
            question="Hỏi?",
            llm_client=llm,
            retrieve_fn=retrieve,
            searched_documents=DOCS,
            max_near_misses=2,
        )
        refs = [n.position_ref for n in result.search_report.near_misses]
        self.assertEqual(refs, ["Trang 2", "Trang 3"])

    def test_abstention_message_mentions_two_passes(self):
        def retrieve(query, top_k, mode):
            return []

        llm = FakeLLMClient([])
        result = answer_with_fallback(
            question="Hỏi?", llm_client=llm, retrieve_fn=retrieve, searched_documents=DOCS
        )
        self.assertTrue(result.abstained)
        self.assertIn("2 lượt", result.answer)

    def test_retrieval_uses_augmented_query_but_generator_sees_original(self):
        seen_queries = []

        def retrieve(query, top_k, mode):
            seen_queries.append(query)
            return [_chunk()]

        llm = FakeLLMClient(["Trả lời. [1]", "CÓ"])
        answer_with_fallback(
            question="tại sao nó tốt hơn?",
            llm_client=llm,
            retrieve_fn=retrieve,
            searched_documents=DOCS,
            retrieval_query="tại sao nó tốt hơn? CNN convolution",
        )
        # truy hồi dùng truy vấn đã bổ sung ngữ cảnh
        self.assertEqual(seen_queries, ["tại sao nó tốt hơn? CNN convolution"])
        # nhưng generator vẫn thấy đúng câu hỏi gốc
        generator_prompt = llm.prompts_received[0]
        self.assertIn("tại sao nó tốt hơn?", generator_prompt)
        self.assertNotIn("CNN convolution", generator_prompt)

    def test_retrieval_query_defaults_to_question(self):
        seen_queries = []

        def retrieve(query, top_k, mode):
            seen_queries.append(query)
            return [_chunk()]

        llm = FakeLLMClient(["Trả lời. [1]", "CÓ"])
        answer_with_fallback(
            question="Hỏi gì đó?", llm_client=llm, retrieve_fn=retrieve, searched_documents=DOCS
        )
        self.assertEqual(seen_queries, ["Hỏi gì đó?"])

    def test_abstention_suggests_topics_that_do_exist(self):
        def retrieve(query, top_k, mode):
            return []

        llm = FakeLLMClient([])
        result = answer_with_fallback(
            question="Vision Transformer là gì?",
            llm_client=llm,
            retrieve_fn=retrieve,
            searched_documents=DOCS,
            suggest_topics_fn=lambda q: ["Kiến trúc Transformer", "Cơ chế chú ý"],
        )
        self.assertTrue(result.abstained)
        self.assertEqual(
            result.search_report.suggested_topics, ["Kiến trúc Transformer", "Cơ chế chú ý"]
        )

    def test_topic_suggestion_is_not_called_when_answer_succeeds(self):
        calls = []

        def retrieve(query, top_k, mode):
            return [_chunk()]

        llm = FakeLLMClient(["Trả lời. [1]", "CÓ"])
        answer_with_fallback(
            question="Hỏi?",
            llm_client=llm,
            retrieve_fn=retrieve,
            searched_documents=DOCS,
            suggest_topics_fn=lambda q: calls.append(q) or [],
        )
        self.assertEqual(calls, [])

    def test_suggested_topics_empty_without_suggester(self):
        def retrieve(query, top_k, mode):
            return []

        result = answer_with_fallback(
            question="Hỏi?", llm_client=FakeLLMClient([]), retrieve_fn=retrieve, searched_documents=DOCS
        )
        self.assertEqual(result.search_report.suggested_topics, [])

    def test_no_chunks_at_all_skips_llm_entirely(self):
        def retrieve(query, top_k, mode):
            return []

        llm = FakeLLMClient([])
        answer_with_fallback(
            question="Hỏi?", llm_client=llm, retrieve_fn=retrieve, searched_documents=DOCS
        )
        self.assertEqual(llm.prompts_received, [])


if __name__ == "__main__":
    unittest.main()
