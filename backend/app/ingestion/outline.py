"""Rút dàn ý chủ đề của tài liệu ngay lúc nạp.

Vì sao cần: trước module này, hệ thống chỉ trích text rồi embed — nó không hề
biết tài liệu NÓI VỀ NHỮNG GÌ. Hệ quả kép. Về phía người dùng, tải lên một
giáo trình 200 trang xong chỉ nhận được một ô chat trống, không biết nên hỏi
gì. Về phía hệ thống, `Topic` chỉ được tạo ra SAU khi người dùng tự gõ tên chủ
đề lúc sinh quiz, nên mastery và kế hoạch ôn tập không có gì để bám vào cho
tới tận lúc đó.

KHÔNG gọi LLM. Với DOCX, python-docx đã cho sẵn kiểu đoạn văn nên heading là
thông tin cho không mà parser.py hiện đang vứt đi. Với PDF thì không có thông
tin kiểu chữ qua pypdf, nên dùng phép suy đoán theo hình thức dòng.

Suy đoán heading PDF ban đầu chỉ dựa "dòng ngắn, không kết thúc bằng dấu câu,
có nội dung dài theo sau" — quá lỏng: pypdf ngắt dòng theo độ rộng trang in,
nên hầu như MỌI dòng không phải câu cuối một đoạn văn đều thoả điều kiện này.
Test bằng tài liệu PDF thật (arXiv, Wikipedia, sách scan) cho thấy heuristic
cũ sinh ra 68-851 "heading" giả trên một tài liệu — nhiễu tới mức phần dàn ý
vô dụng, còn lan sang cả gợi ý chủ đề (suggested_topics) và kế hoạch ôn tập
(vì Topic được tạo thẳng từ các heading này, xem app/routers/documents.py::
_save_outline). Giờ thêm hai tín hiệu chặt hơn trước khi chấp nhận một dòng:
mục đánh số kiểu "1 Introduction"/"3.2.1 Scaled Dot-..." (rất đặc trưng cho
văn bản học thuật, hầu như không false positive), hoặc phần lớn từ viết hoa
chữ cái đầu/toàn bộ viết hoa (văn xuôi bình thường hiếm khi thoả). Cộng thêm
một giới hạn tổng số mục làm lưới an toàn cuối cùng — dù heuristic vẫn có thể
sai ở vài mục lẻ, danh sách sẽ không bao giờ phình to tới mức vô dụng nữa.

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

# Tín hiệu mạnh: mục đánh số kiểu "1 Introduction", "3.2.1 Scaled Dot-Product
# Attention", "6.1 Machine Translation" — đặc trưng của văn bản học thuật,
# gần như không xuất hiện tình cờ trong văn xuôi bình thường.
_NUMBERED_SECTION_RE = re.compile(r"^\d{1,2}(\.\d{1,2}){0,3}\.?\s+\S")

# Danh sách tài liệu tham khảo cũng đánh số y hệt heading ("23. Russell &
# Norvig (2021), tr. 272.") — test bằng bài Wikipedia thật cho thấy đây là
# nguồn nhiễu chính còn sót lại sau _NUMBERED_SECTION_RE. Loại các dòng có
# dấu hiệu trích dẫn học thuật rõ ràng: năm trong ngoặc, ISBN/DOI, "tr./pp.".
_CITATION_LIKE_RE = re.compile(
    r"\(\d{4}[a-z]?[,)]|isbn|doi:|\btr\.\s*\d|\bpp?\.\s*\d",
    re.IGNORECASE,
)

# Lưới an toàn cuối cùng — dù heuristic có sai ở vài mục lẻ, dàn ý một tài
# liệu thật (kể cả sách/giáo trình dài) hiếm khi có quá chừng này đề mục thật.
_MAX_OUTLINE_ENTRIES = 30

# Dòng mở đầu bằng "BY ..."/"Bởi ..."/"Tác giả:..." là byline tác giả — không
# bao giờ là một chủ đề học được, dù OCR có đọc đúng tên hay không (vd bản
# scan lỗi "BY A. M. TUBING" thay vì "BY A. M. TURING"). Đây là quy tắc CẤU
# TRÚC chung cho mọi byline, không phải hardcode riêng một chuỗi lỗi cụ thể.
_BYLINE_RE = re.compile(r"^(by|bởi|tác giả)\b", re.IGNORECASE)

# Một dòng thật sự bị cắt giữa câu (do pypdf ngắt theo độ rộng trang) thường
# kết thúc bằng một từ nối/giới từ dang dở thay vì một danh từ/cụm từ hoàn
# chỉnh — tín hiệu chung, không đoán riêng cho một tài liệu nào.
_TRAILING_STOPWORD_RE = re.compile(
    r"\b(và|hoặc|với|của|cho|là|trong|những|các|một|ở|về|như|để|mà|thì|the|a|"
    r"an|of|in|on|and|or|with|to|for|is|are|as|by)$",
    re.IGNORECASE,
)

_MIN_TOPIC_CHARS = 3
_MAX_TOPIC_CHARS = 100
# Một chuỗi nội dung thật (kể cả thuật ngữ kỹ thuật) hiếm khi có tỉ lệ ký tự
# KHÔNG PHẢI chữ cái (số, ký hiệu, dấu câu vụn — dấu hiệu OCR nát) vượt quá
# mức này trên tổng ký tự không-khoảng-trắng.
_MIN_ALPHA_RATIO = 0.6


_BIBLIOGRAPHY_LINE_RATIO = 0.5


def is_bibliography_like_chunk(text: str) -> bool:
    """Đoạn trích được coi là "khu vực tham khảo/trích dẫn" khi PHẦN LỚN các
    dòng của nó khớp mẫu trích dẫn học thuật (`_CITATION_LIKE_RE` — năm trong
    ngoặc, ISBN/DOI, tr./pp.), dùng chung với `is_plausible_topic` ở trên.

    Dùng để HẠ ƯU TIÊN (không xoá khỏi corpus, không chặn hỏi đáp) khi sinh
    flashcard (BUG-007) — flashcard nên dạy nội dung cốt lõi trước, còn hỏi
    đáp tài liệu vẫn có thể cần trích dẫn một mục tham khảo cụ thể. Đo theo TỈ
    LỆ DÒNG thay vì một dòng đơn lẻ khớp là đủ, để không hạ nhầm một đoạn nội
    dung bình thường chỉ tình cờ nhắc một năm trong ngoặc."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False
    hits = sum(1 for ln in lines if _CITATION_LIKE_RE.search(ln))
    return (hits / len(lines)) >= _BIBLIOGRAPHY_LINE_RATIO


def is_plausible_topic(text: str) -> bool:
    """Lọc chất lượng DÙNG CHUNG cho mọi nơi hiển thị tên chủ đề cho người
    dùng — kế hoạch ôn tập (app/routers/chat.py, app/routers/study_plan.py)
    và gợi ý chủ đề khi từ chối trả lời (app/routers/chat.py::_suggest_topics).

    Cần một lớp lọc Ở ĐIỂM TIÊU THỤ, tách biệt với `_looks_like_heading` ở
    điểm TRÍCH XUẤT, vì hai lý do. Một, ngay cả heuristic trích xuất đã siết
    chặt vẫn có thể lọt vài dòng nhiễu — phòng thủ hai lớp. Hai, quan trọng
    hơn: `Topic`/`DocumentTopic` đã LƯU SẴN trong DB từ TRƯỚC khi
    `_looks_like_heading` được siết lại (xem lịch sử git — heuristic cũ từng
    sinh ra 68-851 "heading" giả/tài liệu) vẫn còn nguyên trong dữ liệu người
    dùng đã tồn tại. Sửa heuristic trích xuất KHÔNG tự động dọn lại các hàng
    đã lưu trước đó (chỉ áp dụng cho tài liệu tải lên/xử lý lại sau này), nên
    nơi tiêu thụ dữ liệu phải tự vệ thay vì tin thẳng vào những gì đã có sẵn
    trong DB.

    Cố tình bảo thủ (permissive hơn `_looks_like_heading`): mục tiêu ở đây là
    chặn nhiễu RÕ RÀNG (OCR vỡ, trích dẫn, byline, dòng bị cắt giữa câu, dòng
    dài bất thường), không phải tái hiện toàn bộ logic "có phải heading PDF
    không" — một Topic hợp lệ có thể không phải heading PDF gốc (vd người
    dùng tự gõ tên chủ đề lúc sinh quiz)."""
    stripped = (text or "").strip()
    if not (_MIN_TOPIC_CHARS <= len(stripped) <= _MAX_TOPIC_CHARS):
        return False
    if _CITATION_LIKE_RE.search(stripped):
        return False
    if _BYLINE_RE.match(stripped):
        return False
    if _TRAILING_STOPWORD_RE.search(stripped):
        return False

    non_space = sum(1 for ch in stripped if not ch.isspace())
    if non_space == 0:
        return False
    letters = sum(1 for ch in stripped if ch.isalpha())
    if letters / non_space < _MIN_ALPHA_RATIO:
        return False

    return True


def _is_title_case_or_caps(stripped: str) -> bool:
    """Hầu hết các từ viết hoa chữ cái đầu, hoặc toàn bộ viết hoa — cách viết
    tiêu đề phổ biến, khác với văn xuôi bình thường (chỉ viết hoa đầu câu và
    danh từ riêng)."""
    words = [w for w in re.findall(r"[^\W\d_]+", stripped) if len(w) > 1]
    if len(words) < 2:
        return False
    if stripped.isupper():
        return True
    capitalized = sum(1 for w in words if w[0].isupper())
    return capitalized / len(words) >= 0.7


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
    # Heading phải có nội dung thật theo sau, nếu không thì đó chỉ là một dòng
    # cụt bình thường.
    if len(following.strip()) <= _MAX_HEADING_CHARS:
        return False
    if _CITATION_LIKE_RE.search(stripped):
        return False
    if _NUMBERED_SECTION_RE.match(stripped):
        return True
    if _SENTENCE_END_RE.search(stripped):
        return False
    return _is_title_case_or_caps(stripped)


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

    return _dedupe_keep_order(entries)[:_MAX_OUTLINE_ENTRIES]
