"""Trích xuất text từ PDF/DOCX, trả về danh sách section có vị trí nguồn.

Mỗi section là tuple (position_ref, text):
- PDF: mỗi trang là một section, position_ref = "Trang {n}".
- DOCX: nhóm `paragraphs_per_section` đoạn văn liên tiếp thành một section,
  position_ref = "Mục {n}" — vì DOCX không có khái niệm trang cố định.

Output của module này là đầu vào cho `chunker.chunk_sections`.

Ghi chú kiểm thử: đường dẫn DOCX được test bằng file .docx thật (tạo bằng
`python-docx` trong `tests/test_parser.py`). Đường dẫn PDF dùng `pypdf`,
implementation đơn giản (mỗi trang → 1 section) nhưng KHÔNG có test tích hợp
chạy được trong sandbox này vì không tạo được file PDF fixture hợp lệ mà
không cần thêm thư viện (reportlab...) không có sẵn và không cài được do
sandbox không có mạng. Cần chạy thử với PDF thật ở máy local trước khi tin
tưởng nhánh này.
"""

import os
from typing import List, Tuple

from pypdf import PdfReader
from docx import Document as DocxDocument


class UnsupportedFileType(ValueError):
    pass


def parse_document(
    file_path: str,
    paragraphs_per_section: int = 10,
) -> List[Tuple[str, str]]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return _parse_pdf(file_path)
    if ext == ".docx":
        return _parse_docx(file_path, paragraphs_per_section)
    raise UnsupportedFileType(f"Định dạng không được hỗ trợ: {ext}")


def _parse_pdf(file_path: str) -> List[Tuple[str, str]]:
    reader = PdfReader(file_path)
    sections = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        sections.append((f"Trang {i}", text))
    return sections


def _parse_docx(file_path: str, paragraphs_per_section: int) -> List[Tuple[str, str]]:
    doc = DocxDocument(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    sections = []
    for i in range(0, len(paragraphs), paragraphs_per_section):
        group = paragraphs[i : i + paragraphs_per_section]
        section_index = i // paragraphs_per_section + 1
        sections.append((f"Mục {section_index}", "\n".join(group)))
    return sections
