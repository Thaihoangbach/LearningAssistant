import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.retrieval.reranker import rerank
from app.vectorstore.faiss_store import IndexedChunk


def make_chunk(chunk_id, text="nội dung"):
    return IndexedChunk(chunk_id=chunk_id, document_id="doc1", document_name="d.pdf", position_ref="Trang 1", text=text)


class FakeReranker:
    """Reranker giả lập — trả điểm theo kịch bản, không tải model thật."""

    def __init__(self, scripted_scores):
        self.scripted_scores = scripted_scores
        self.calls = []

    def score(self, query, texts):
        self.calls.append((query, texts))
        return self.scripted_scores


class TestRerank(unittest.TestCase):
    def test_empty_candidates_returns_empty_without_calling_reranker(self):
        reranker = FakeReranker(scripted_scores=[])
        result = rerank("câu hỏi", candidates=[], reranker=reranker, top_k=5)
        self.assertEqual(result, [])
        self.assertEqual(len(reranker.calls), 0)

    def test_reorders_candidates_by_score_descending(self):
        candidates = [make_chunk("low"), make_chunk("high"), make_chunk("mid")]
        # thứ tự điểm khớp với thứ tự candidates: low=-5 (thấp), high=5 (cao), mid=0
        reranker = FakeReranker(scripted_scores=[-5.0, 5.0, 0.0])
        result = rerank("câu hỏi", candidates=candidates, reranker=reranker, top_k=3)
        ids_in_order = [c.chunk_id for c, _ in result]
        self.assertEqual(ids_in_order, ["high", "mid", "low"])

    def test_scores_are_sigmoid_normalized_between_0_and_1(self):
        candidates = [make_chunk("a"), make_chunk("b")]
        reranker = FakeReranker(scripted_scores=[10.0, -10.0])
        result = rerank("câu hỏi", candidates=candidates, reranker=reranker, top_k=2)
        for _, score in result:
            self.assertGreater(score, 0.0)
            self.assertLess(score, 1.0)

    def test_truncates_to_top_k(self):
        candidates = [make_chunk("a"), make_chunk("b"), make_chunk("c")]
        reranker = FakeReranker(scripted_scores=[1.0, 2.0, 3.0])
        result = rerank("câu hỏi", candidates=candidates, reranker=reranker, top_k=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0].chunk_id, "c")

    def test_reranker_called_once_with_all_candidate_texts(self):
        candidates = [make_chunk("a", text="văn bản A"), make_chunk("b", text="văn bản B")]
        reranker = FakeReranker(scripted_scores=[1.0, 1.0])
        rerank("câu hỏi X", candidates=candidates, reranker=reranker, top_k=2)
        self.assertEqual(len(reranker.calls), 1)
        query, texts = reranker.calls[0]
        self.assertEqual(query, "câu hỏi X")
        self.assertEqual(texts, ["văn bản A", "văn bản B"])


if __name__ == "__main__":
    unittest.main()
