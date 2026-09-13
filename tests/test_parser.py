"""Test cho app/ingestion/parser.py::_parse_pdf.

Chỉ test bug NUL byte phát hiện khi chạy Golden Set thật (tài liệu Wikipedia
"Phở" khiến pypdf trích ra byte NUL (0x00) lẫn trong text, làm insert vào
cột text của Postgres crash và document kẹt mãi ở trạng thái "đang xử lý").
Không tái tạo được NUL byte thật qua reportlab (nguồn gốc là cách pypdf giải
mã một số PDF cụ thể, không phải nội dung text thông thường), nên test bằng
cách monkeypatch `PdfReader.pages[i].extract_text` để trả về text có lẫn
NUL byte, xác nhận `_parse_pdf` loại bỏ nó trước khi trả về.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.ingestion.parser import _parse_pdf


class TestParsePdfNulByteSanitization(unittest.TestCase):
    def test_nul_byte_is_stripped_from_extracted_text(self):
        fake_page = MagicMock()
        fake_page.extract_text.return_value = "Phở\x00 là món ăn Việt Nam."
        fake_reader = MagicMock()
        fake_reader.pages = [fake_page]

        with patch("app.ingestion.parser.PdfReader", return_value=fake_reader):
            sections = _parse_pdf("fake_path.pdf")

        self.assertEqual(len(sections), 1)
        position_ref, text = sections[0]
        self.assertEqual(position_ref, "Trang 1")
        self.assertNotIn("\x00", text)
        self.assertEqual(text, "Phở là món ăn Việt Nam.")

    def test_page_with_no_nul_bytes_is_unaffected(self):
        fake_page = MagicMock()
        fake_page.extract_text.return_value = "Nội dung bình thường."
        fake_reader = MagicMock()
        fake_reader.pages = [fake_page]

        with patch("app.ingestion.parser.PdfReader", return_value=fake_reader):
            sections = _parse_pdf("fake_path.pdf")

        self.assertEqual(sections, [("Trang 1", "Nội dung bình thường.")])


if __name__ == "__main__":
    unittest.main()
