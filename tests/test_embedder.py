"""app/ingestion/embedder.py giờ gọi Cohere Embed API thay vì
sentence-transformers cục bộ — test bằng fake client (mirror cách
test_openai_client.py không cần network/API key thật)."""
import os
import sys
import unittest
from dataclasses import dataclass
from typing import List
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import cohere
import numpy as np

from app.ingestion import embedder


@dataclass
class _FakeEmbeddings:
    float: List[List[float]]


@dataclass
class _FakeResponse:
    embeddings: _FakeEmbeddings


class _FakeCohereClient:
    def __init__(self):
        self.calls = []

    def embed(self, *, model, input_type, texts, embedding_types):
        self.calls.append({"model": model, "input_type": input_type, "texts": list(texts)})
        # Vector dựng theo độ dài text để mỗi input cho ra vector khác nhau,
        # đủ để kiểm tra thứ tự/số lượng không bị xáo trộn qua các lượt gọi.
        vectors = [[float(len(t) % 7 + 1), 1.0, 0.0, 0.0] for t in texts]
        return _FakeResponse(embeddings=_FakeEmbeddings(float=vectors))


class TestEmbedTexts(unittest.TestCase):
    def setUp(self):
        self.fake_client = _FakeCohereClient()
        patcher = patch.object(embedder, "_get_client", return_value=self.fake_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_returns_l2_normalized_vectors(self):
        result = embedder.embed_texts(["một câu hỏi"])

        self.assertEqual(result.shape, (1, 4))
        self.assertAlmostEqual(float(np.linalg.norm(result[0])), 1.0, places=5)

    def test_empty_list_returns_empty_array_without_calling_api(self):
        result = embedder.embed_texts([])

        self.assertEqual(result.shape, (0, 0))
        self.assertEqual(self.fake_client.calls, [])

    def test_batches_requests_larger_than_96_texts(self):
        texts = [f"đoạn {i}" for i in range(150)]

        result = embedder.embed_texts(texts)

        self.assertEqual(result.shape[0], 150)
        self.assertEqual(len(self.fake_client.calls), 2)
        self.assertEqual(len(self.fake_client.calls[0]["texts"]), 96)
        self.assertEqual(len(self.fake_client.calls[1]["texts"]), 54)

    def test_embed_texts_defaults_to_search_document_input_type(self):
        embedder.embed_texts(["nội dung tài liệu"])

        self.assertEqual(self.fake_client.calls[0]["input_type"], "search_document")

    def test_embed_query_uses_search_query_input_type(self):
        vector = embedder.embed_query("câu hỏi của người dùng")

        self.assertEqual(self.fake_client.calls[0]["input_type"], "search_query")
        self.assertEqual(vector.shape, (4,))


class _FlakyRateLimitedClient:
    """Ném TooManyRequestsError (429) đúng `fail_times` lần đầu rồi mới trả kết quả —
    mô phỏng trial key Cohere hết token/phút giữa lúc xử lý một tài liệu dài."""

    def __init__(self, fail_times):
        self.fail_times = fail_times
        self.calls = 0

    def embed(self, *, model, input_type, texts, embedding_types):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise cohere.TooManyRequestsError(body={"message": "trial token rate limit exceeded"})
        vectors = [[1.0, 0.0, 0.0, 0.0] for _ in texts]
        return _FakeResponse(embeddings=_FakeEmbeddings(float=vectors))


class TestEmbedTextsRateLimitRetry(unittest.TestCase):
    def setUp(self):
        patcher = patch("time.sleep", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_retries_and_succeeds_after_transient_429(self):
        fake_client = _FlakyRateLimitedClient(fail_times=2)
        with patch.object(embedder, "_get_client", return_value=fake_client):
            result = embedder.embed_texts(["một đoạn văn bản"])

        self.assertEqual(result.shape, (1, 4))
        self.assertEqual(fake_client.calls, 3)

    def test_raises_after_exhausting_all_retries(self):
        fake_client = _FlakyRateLimitedClient(fail_times=999)
        with patch.object(embedder, "_get_client", return_value=fake_client):
            with self.assertRaises(cohere.TooManyRequestsError):
                embedder.embed_texts(["một đoạn văn bản"])

        self.assertEqual(fake_client.calls, embedder._MAX_RATE_LIMIT_RETRIES)


if __name__ == "__main__":
    unittest.main()
