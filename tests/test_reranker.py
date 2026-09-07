import math
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.retrieval.reranker import CohereReranker, rerank
from app.vectorstore.types import IndexedChunk


def make_chunk(chunk_id, text="nội dung"):
    return IndexedChunk(chunk_id=chunk_id, document_id="doc1", document_name="d.pdf", position_ref="Trang 1", text=text)


class FakeReranker:
    """Reranker giả lập — trả điểm theo kịch bản, không tải model/gọi API thật."""

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


class _FakeResult:
    def __init__(self, index, relevance_score):
        self.index = index
        self.relevance_score = relevance_score


class _FakeRerankResponse:
    def __init__(self, results):
        self.results = results


class _FakeCohereClient:
    def __init__(self, results_by_call):
        # Danh sách kết quả trả về CHO TỪNG lượt gọi, theo thứ tự gọi.
        self.results_by_call = list(results_by_call)
        self.calls = []

    def rerank(self, *, model, query, documents, top_n):
        self.calls.append({"model": model, "query": query, "documents": list(documents), "top_n": top_n})
        return _FakeRerankResponse(results=self.results_by_call.pop(0))


class TestCohereReranker(unittest.TestCase):
    """`score()` phải trả điểm cho MỖI text, ĐÚNG THỨ TỰ đầu vào — dù Cohere
    trả kết quả theo thứ tự XẾP HẠNG kèm index trỏ ngược, không phải mảng
    song song với input."""

    def test_empty_texts_returns_empty_without_calling_api(self):
        client = _FakeCohereClient(results_by_call=[[]])
        with patch("app.retrieval.reranker._get_cohere_client", return_value=client):
            reranker = CohereReranker()
            self.assertEqual(reranker.score("hỏi gì đó", []), [])
        self.assertEqual(client.calls, [])

    def test_scores_reordered_back_to_original_input_order(self):
        # Cohere xếp "b" (input[1]) lên đầu, "a" (input[0]) xuống cuối.
        results = [_FakeResult(index=1, relevance_score=0.9), _FakeResult(index=0, relevance_score=0.1)]
        client = _FakeCohereClient(results_by_call=[results])
        with patch("app.retrieval.reranker._get_cohere_client", return_value=client):
            reranker = CohereReranker()
            scores = reranker.score("hỏi gì đó", ["văn bản a", "văn bản b"])

        # scores[0] ứng với "văn bản a" (relevance 0.1), scores[1] với "văn
        # bản b" (relevance 0.9) — logit đơn điệu tăng nên thứ tự phải giữ
        # đúng quan hệ b > a.
        self.assertGreater(scores[1], scores[0])

    def test_sigmoid_of_logit_recovers_original_relevance_score(self):
        """`rerank()` (hàm dùng chung) áp sigmoid lên MỌI điểm nhận được —
        score() phải trả logit NGƯỢC để sigmoid(logit(p)) == p, tức điểm cuối
        cùng người dùng thấy đúng bằng relevance_score gốc của Cohere, không
        bị nén qua hai lớp biến đổi chồng nhau."""
        results = [_FakeResult(index=0, relevance_score=0.83)]
        client = _FakeCohereClient(results_by_call=[results])
        with patch("app.retrieval.reranker._get_cohere_client", return_value=client):
            reranker = CohereReranker()
            scores = reranker.score("hỏi gì đó", ["văn bản a"])

        recovered = 1.0 / (1.0 + math.exp(-scores[0]))
        self.assertAlmostEqual(recovered, 0.83, places=5)

    def test_requests_top_n_equal_to_number_of_texts(self):
        """Phải xin ĐỦ điểm cho mọi text (top_n=len(texts)), không phải mặc
        định của Cohere (trả tất cả) hay một con số cố định nhỏ hơn — thiếu
        điểm cho dù chỉ một text sẽ làm scores[] có None lọt tới _sigmoid()."""
        client = _FakeCohereClient(
            results_by_call=[[_FakeResult(index=i, relevance_score=0.5) for i in range(5)]]
        )
        with patch("app.retrieval.reranker._get_cohere_client", return_value=client):
            CohereReranker().score("hỏi", ["t0", "t1", "t2", "t3", "t4"])

        self.assertEqual(client.calls[0]["top_n"], 5)

    def test_end_to_end_with_rerank_orchestration(self):
        """CohereReranker cắm thẳng vào rerank() (hàm dùng chung, không đổi)
        mà không cần lớp thích ứng nào — đúng hợp đồng RerankerClient."""
        candidates = [make_chunk("a", text="A"), make_chunk("b", text="B")]
        results = [_FakeResult(index=1, relevance_score=0.9), _FakeResult(index=0, relevance_score=0.05)]
        client = _FakeCohereClient(results_by_call=[results])
        with patch("app.retrieval.reranker._get_cohere_client", return_value=client):
            ranked = rerank("hỏi", candidates, CohereReranker(), top_k=2)

        self.assertEqual([c.chunk_id for c, _ in ranked], ["b", "a"])
        self.assertAlmostEqual(ranked[0][1], 0.9, places=5)


if __name__ == "__main__":
    unittest.main()
