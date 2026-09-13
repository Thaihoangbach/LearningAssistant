"""Chunking logic cho pipeline nạp tài liệu (F1).

Nhận đầu vào là danh sách "section" đã được parser.py trích xuất — mỗi section
là tuple (position_ref, text), ví dụ ("Trang 3", "...") với PDF hoặc
("Mục 2", "...") với DOCX.

Hai nguyên tắc:

1. Cắt theo RANH GIỚI CÂU, không cắt theo ký tự. Bản trước cắt thẳng
   `text[start:start+max_chars]` nên cắt giữa câu, thậm chí giữa từ — embedding
   của một mẩu cụt kém hơn hẳn, và panel trích dẫn hiện ra đoạn dở dang. Chỉ
   khi một câu đơn lẻ dài hơn max_chars mới buộc phải cắt cứng.

2. BẮC CẦU qua ranh giới section. Chồng lấn trong cùng một section không cứu
   được nội dung vắt từ cuối trang này sang đầu trang sau — với PDF mỗi trang
   là một section nên đó là ranh giới cứng, không có chunk nào chứa cả hai
   phía. Chunk bắc cầu ghi rõ CẢ HAI vị trí trong position_ref để trích dẫn
   vẫn trung thực, không gán bừa vào một bên.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple

# Ranh giới câu: sau dấu kết câu và khoảng trắng, hoặc xuống dòng.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass
class Chunk:
    text: str
    position_ref: str
    chunk_index: int
    # Chỉ số (0-based) của section trong danh sách `sections` truyền vào
    # chunk_sections() mà chunk này sinh ra từ đó — dùng để lấy lại TOÀN BỘ
    # chunk thuộc một DocumentTopic theo đúng thứ tự đọc gốc (structural
    # retrieval cho Summarize), khác với truy hồi theo độ liên quan ngữ nghĩa.
    # Chunk bắc cầu (nối 2 section) mang section_index của section ĐẦU (bên
    # trái) — coi như thuộc về section đó, phần nội dung bắc cầu chỉ là phần
    # đuôi/đầu chồng lấn.
    section_index: int = 0


def _hard_split(text: str, max_chars: int, overlap_chars: int) -> List[str]:
    """Cắt cứng theo ký tự — chỉ dùng cho câu đơn lẻ dài hơn max_chars.

    Giữ nguyên ngữ nghĩa chồng lấn của bản cũ (bước nhảy = max_chars -
    overlap_chars) để ghép lại vẫn khôi phục đúng văn bản gốc."""
    step = max_chars - overlap_chars
    pieces = []
    start = 0
    while start < len(text):
        pieces.append(text[start : start + max_chars])
        if start + max_chars >= len(text):
            break
        start += step
    return pieces


def _split_text(text: str, max_chars: int, overlap_chars: int) -> List[str]:
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if not sentences:
        return []

    pieces: List[str] = []
    current: List[str] = []
    current_len = 0

    def flush():
        """Xả phần đang gom thành một chunk, rồi giữ lại vài câu cuối làm phần
        chồng lấn cho chunk kế tiếp."""
        nonlocal current, current_len
        if current:
            pieces.append(" ".join(current))
        carried: List[str] = []
        carried_len = 0
        for s in reversed(current):
            if carried_len + len(s) > overlap_chars:
                break
            carried.insert(0, s)
            carried_len += len(s) + 1
        current = carried
        current_len = carried_len

    for sentence in sentences:
        if len(sentence) > max_chars:
            # Câu dài hơn cả một chunk: xả phần đang gom rồi cắt cứng riêng nó.
            if current:
                pieces.append(" ".join(current))
                current, current_len = [], 0
            pieces.extend(_hard_split(sentence, max_chars, overlap_chars))
            continue

        if current_len + len(sentence) + 1 > max_chars and current:
            flush()

        current.append(sentence)
        current_len += len(sentence) + 1

    if current:
        pieces.append(" ".join(current))

    # Phần chồng lấn ở cuối có thể sinh ra một chunk trùng hệt chunk trước.
    deduped: List[str] = []
    for p in pieces:
        if not deduped or p != deduped[-1]:
            deduped.append(p)
    return deduped


def chunk_sections(
    sections: List[Tuple[str, str]],
    max_chars: int = 800,
    overlap_chars: int = 100,
    bridge_sections: bool = True,
) -> List[Chunk]:
    if overlap_chars >= max_chars:
        raise ValueError("overlap_chars phải nhỏ hơn max_chars")

    chunks: List[Chunk] = []
    prev_ref = None
    prev_text = None
    prev_section_index = None

    for section_index, (position_ref, text) in enumerate(sections):
        stripped = text.strip()
        if not stripped:
            continue

        # Chunk bắc cầu — chỉ tạo khi CẢ HAI section đủ dài. Section ngắn hơn
        # cửa sổ chồng lấn đã nằm trọn trong chunk của chính nó rồi, bắc cầu
        # chỉ thêm nhiễu.
        if (
            bridge_sections
            and prev_text is not None
            and len(prev_text) >= overlap_chars
            and len(stripped) >= overlap_chars
        ):
            bridge = f"{prev_text[-overlap_chars:].strip()} {stripped[:overlap_chars].strip()}"
            chunks.append(
                Chunk(
                    text=bridge,
                    position_ref=f"{prev_ref}–{position_ref}",
                    chunk_index=len(chunks),
                    # Gán cho section BÊN TRÁI — xem docstring `Chunk.section_index`.
                    section_index=prev_section_index,
                )
            )

        for piece in _split_text(stripped, max_chars, overlap_chars):
            chunks.append(
                Chunk(
                    text=piece,
                    position_ref=position_ref,
                    chunk_index=len(chunks),
                    section_index=section_index,
                )
            )

        prev_ref = position_ref
        prev_text = stripped
        prev_section_index = section_index

    return chunks
