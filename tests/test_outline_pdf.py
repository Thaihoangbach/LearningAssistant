"""Test heuristic đoán heading cho PDF (app/ingestion/outline.py::_outline_pdf).

Trước file này, nhánh PDF của outline.py hoàn toàn không có test — lý do ban
đầu (docstring cũ của parser.py) là "không tạo được PDF fixture hợp lệ mà
không cần thêm thư viện (reportlab...)". reportlab đã có sẵn trong venv nên
dùng nó dựng PDF thật, verify đúng hành vi thay vì chỉ tin heuristic.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.ingestion.outline import extract_outline


def _make_pdf(lines_per_page):
    """lines_per_page: list[list[str]] — mỗi trang là danh sách dòng đã wrap."""
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    c = canvas.Canvas(tmp.name, pagesize=A4)
    width, height = A4
    for lines in lines_per_page:
        c.setFont("Helvetica", 11)
        y = height - 60
        for line in lines:
            c.drawString(50, y, line)
            y -= 16
        c.showPage()
    c.save()
    return tmp.name


class TestOutlinePdf(unittest.TestCase):
    def test_numbered_section_is_detected(self):
        path = _make_pdf(
            [
                [
                    "1 Introduction",
                    "This is a long paragraph of body text that goes on for quite a while to satisfy the minimum length check.",
                    "2 Background",
                    "Another long paragraph of body text that goes on for quite a while to satisfy the minimum length check.",
                ]
            ]
        )
        try:
            outline = extract_outline(path)
            self.assertEqual([e.title for e in outline], ["1 Introduction", "2 Background"])
        finally:
            os.remove(path)

    def test_ordinary_wrapped_prose_line_is_not_a_heading(self):
        # Mo phong dung van de that: mot doan van dai bi pypdf ngat thanh
        # nhieu dong ngan, khong dong nao ket thuc bang dau cau tru dong cuoi.
        path = _make_pdf(
            [
                [
                    "cac he thong may tinh co the hieu va xu ly ngon ngu",
                    "tu nhien cua con nguoi thong qua nhieu ky thuat khac",
                    "nhau bao gom phan tich cu phap va ngu nghia hoc.",
                ]
            ]
        )
        try:
            outline = extract_outline(path)
            self.assertEqual(outline, [])
        finally:
            os.remove(path)

    def test_section_index_matches_chunk_section_index_for_same_page(self):
        # Cross-consistency PDF: heading tìm thấy ở trang 2 phải có
        # section_index == 1 (0-based), và một chunk sinh ra từ CÙNG file qua
        # chunk_sections() ở trang đó cũng phải mang đúng section_index == 1
        # — hai bên đọc từ cùng một `sections`, không phải suy luận riêng.
        from app.ingestion.chunker import chunk_sections
        from app.ingestion.parser import parse_document

        path = _make_pdf(
            [
                ["Trang một nội dung thường, không có heading nào ở đây cả cho đủ dài."],
                [
                    "2 Background",
                    "This is a long paragraph of body text that goes on for quite a while to satisfy the minimum length check.",
                ],
            ]
        )
        try:
            outline = extract_outline(path)
            self.assertEqual([e.section_index for e in outline], [1])

            sections = parse_document(path)
            chunks = chunk_sections(sections)
            chunk_section_indices = {c.section_index for c in chunks if c.position_ref == "Trang 2"}
            self.assertEqual(chunk_section_indices, {1})
        finally:
            os.remove(path)

    def test_title_case_heading_is_detected(self):
        path = _make_pdf(
            [
                [
                    "Multi-Head Attention Mechanism",
                    "This is a long paragraph of body text that goes on for quite a while to satisfy the minimum length check.",
                ]
            ]
        )
        try:
            outline = extract_outline(path)
            self.assertEqual([e.title for e in outline], ["Multi-Head Attention Mechanism"])
        finally:
            os.remove(path)

    def test_citation_like_numbered_line_is_rejected(self):
        path = _make_pdf(
            [
                [
                    "23. Russell & Norvig (2021), tr. 272.",
                    "This is a long paragraph of body text that goes on for quite a while to satisfy the minimum length check.",
                ]
            ]
        )
        try:
            outline = extract_outline(path)
            self.assertEqual(outline, [])
        finally:
            os.remove(path)

    def test_dense_reference_list_is_capped_not_unbounded(self):
        # Mo phong danh sach tham khao day dac, moi dong deu "trong" giong
        # heading (ngan, khong dau cau, co noi dung dai theo sau) - truoc khi
        # sua, day chinh la nguon sinh ra hang tram entry gia.
        lines = []
        for i in range(1, 61):
            lines.append(f"REFERENCE ENTRY NUMBER {i}")
            lines.append(
                "This is a long paragraph of body text that goes on for quite a while to satisfy the minimum length check."
            )
        path = _make_pdf([lines])
        try:
            outline = extract_outline(path)
            self.assertLessEqual(len(outline), 30)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
