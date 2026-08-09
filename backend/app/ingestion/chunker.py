"""Chunking logic cho pipeline nạp tài liệu (F1).

Nhận đầu vào là danh sách các "section" đã được parser.py trích xuất —
mỗi section là một tuple (position_ref, text), ví dụ (position_ref="Trang 3",
text="...") với PDF, hoặc (position_ref="Mục 2", text="...") với DOCX.

Chia mỗi section thành các Chunk không vượt quá `max_chars`, có phần chồng
lấn `overlap_chars` giữa hai chunk liên tiếp trong cùng section để không cắt
đứt ngữ cảnh ở ranh giới chunk. `position_ref` được giữ nguyên cho mọi chunk
sinh ra từ cùng một section, để F2 có thể trích dẫn đúng vị trí nguồn.
"""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class Chunk:
    text: str
    position_ref: str
    chunk_index: int


def chunk_sections(
    sections: List[Tuple[str, str]],
    max_chars: int = 800,
    overlap_chars: int = 100,
) -> List[Chunk]:
    if overlap_chars >= max_chars:
        raise ValueError("overlap_chars phải nhỏ hơn max_chars")

    chunks: List[Chunk] = []
    step = max_chars - overlap_chars

    for position_ref, text in sections:
        stripped = text.strip()
        if not stripped:
            continue

        start = 0
        while start < len(stripped):
            piece = stripped[start : start + max_chars]
            chunks.append(
                Chunk(
                    text=piece,
                    position_ref=position_ref,
                    chunk_index=len(chunks),
                )
            )
            if start + max_chars >= len(stripped):
                break
            start += step

    return chunks
