import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.vectorstore.bm25_index import Bm25Index
from app.vectorstore.faiss_store import IndexedChunk


def make_chunk(chunk_id, text, doc_id="doc1"):
    return IndexedChunk(chunk_id=chunk_id, document_id=doc_id, document_name="d.pdf", position_ref="Trang 1", text=text)


class TestBm25Index(unittest.TestCase):
    def test_empty_chunks_returns_empty_results(self):
        index = Bm25Index([])
        self.assertEqual(index.search("gradient descent", top_k=5), [])

    def test_finds_chunk_containing_rare_term(self):
        chunks = [
            make_chunk("c1", "Gradient Descent là thuật toán tối ưu phổ biến."),
            make_chunk("c2", "Vanishing Gradient xảy ra khi mạng nơ-ron quá sâu."),
            make_chunk("c3", "Decision Tree dùng để phân loại dữ liệu."),
        ]
        index = Bm25Index(chunks)
        results = index.search("Vanishing Gradient", top_k=2)
        self.assertEqual(results[0][0].chunk_id, "c2")

    def test_query_with_no_overlapping_terms_returns_empty(self):
        chunks = [make_chunk("c1", "Gradient Descent là thuật toán tối ưu.")]
        index = Bm25Index(chunks)
        results = index.search("công thức nấu phở bò", top_k=5)
        self.assertEqual(results, [])

    def test_results_sorted_by_score_descending(self):
        # Dùng corpus 5 tài liệu (thay vì 2) để tránh edge case idf âm của
        # BM25 khi corpus quá nhỏ và một từ xuất hiện ở hầu hết tài liệu —
        # xem ghi chú trong app/vectorstore/bm25_index.py.
        chunks = [
            make_chunk("c1", "CNN dùng convolution để trích xuất đặc trưng ảnh."),
            make_chunk("c2", "CNN CNN CNN convolution convolution là kỹ thuật quan trọng trong thị giác máy tính."),
            make_chunk("c3", "Decision Tree dùng để phân loại dữ liệu."),
            make_chunk("c4", "RNN xử lý dữ liệu tuần tự theo thời gian."),
            make_chunk("c5", "Attention dùng Query Key Value để tính trọng số."),
        ]
        index = Bm25Index(chunks)
        results = index.search("CNN convolution", top_k=2)
        self.assertEqual(results[0][0].chunk_id, "c2")
        self.assertGreaterEqual(results[0][1], results[1][1])


if __name__ == "__main__":
    unittest.main()
