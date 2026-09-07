"""Rút dàn ý chủ đề của tài liệu ngay lúc nạp.

Vì sao cần: trước module này, hệ thống chỉ trích text rồi embed — nó không hề
biết tài liệu NÓI VỀ NHỮNG GÌ. Hệ quả kép. Về phía người dùng, tải lên một
giáo trình 200 trang xong chỉ nhận được một ô chat trống, không biết nên hỏi
gì. Về phía hệ thống, `Topic` chỉ được tạo ra SAU khi người dùng tự gõ tên chủ
đề lúc sinh quiz, nên mastery và kế hoạch ôn tập không có gì để bám vào cho
tới tận lúc đó.

KHÔNG gọi LLM. Với DOCX, python-docx đã cho sẵn kiểu đoạn văn nên heading là
thông tin cho không mà parser.py hiện đang vứt đi. Với PDF thì không có thông
tin kiểu chữ qua pypdf, nên dùng phép suy đoán theo hình thức dòng: dòng ngắn,
không kết thúc bằng dấu câu, và có nội dung dài theo sau.

Tài liệu không có dàn ý nào rút được thì trả về danh sách rỗng — giao diện đơn
giản là không hiện phần dàn ý, chứ không bịa ra chủ đề.
"""

import os
import re
from dataclasses import dataclass
from typing import List

# Phải khớp `paragraphs_per_section` mặc định của app/ingestion/parser.py, nếu
# lệch thì position_ref của dàn ý sẽ trỏ sai section.
PARAGRAPHS_PER_SECTION = 10

# Ngưỡng suy đoán heading trong PDF.
_MAX_HEADING_CHARS = 80
_MIN_HEADING_CHARS = 3
_SENTENCE_END_RE = re.compile(r"[.!?:;,]\s*$")


@dataclass
class OutlineEntry:
    title: str
    position_ref: str
    order: int


def extract_outline(file_path: str) -> List[OutlineEntry]:
    if not os.path.exists(file_path):
        return []
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".docx":
        return _outline_docx(file_path)
    if ext == ".pdf":
        return _outline_pdf(file_path)
    return []


def _dedupe_keep_order(entries: List[OutlineEntry]) -> List[OutlineEntry]:
    seen = set()
    result = []
    for e in entries:
        key = e.title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(OutlineEntry(title=e.title, position_ref=e.position_ref, order=len(result)))
    return result


def _outline_docx(file_path: str) -> List[OutlineEntry]:
    from docx import Document as DocxDocument

    doc = DocxDocument(file_path)

    entries: List[OutlineEntry] = []
    # Đếm theo đoạn văn KHÔNG rỗng, đúng cách parser.py gom section — nếu đếm
    # cả đoạn rỗng thì position_ref sẽ lệch.
    non_empty_index = 0
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue

        style_name = (paragraph.style.name or "") if paragraph.style is not None else ""
        if style_name.startswith("Heading") or style_name.startswith("Title"):
            section_index = non_empty_index // PARAGRAPHS_PER_SECTION + 1
            entries.append(
                OutlineEntry(title=text, position_ref=f"Mục {section_index}", order=len(entries))
            )

        non_empty_index += 1

    return _dedupe_keep_order(entries)


def _looks_like_heading(line: str, following: str) -> bool:
    stripped = line.strip()
    if not (_MIN_HEADING_CHARS <= len(stripped) <= _MAX_HEADING_CHARS):
        return False
    if _SENTENCE_END_RE.search(stripped):
        return False
    # Heading phải có nội dung thật theo sau, nếu không thì đó chỉ là một dòng
    # cụt bình thường.
    return len(following.strip()) > _MAX_HEADING_CHARS


def _outline_pdf(file_path: str) -> List[OutlineEntry]:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    entries: List[OutlineEntry] = []

    for page_number, page in enumerate(reader.pages, start=1):
        lines = [ln for ln in (page.extract_text() or "").splitlines() if ln.strip()]
        for i, line in enumerate(lines):
            following = " ".join(lines[i + 1 : i + 3])
            if _looks_like_heading(line, following):
                entries.append(
                    OutlineEntry(
                        title=line.strip(),
                        position_ref=f"Trang {page_number}",
                        order=len(entries),
                    )
                )

    return _dedupe_keep_order(entries)
