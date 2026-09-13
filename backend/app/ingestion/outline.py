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
from typing import List, Tuple

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
    if "," in stripped or ";" in stripped:
        # Một heading/tên chủ đề thật (kể cả mục đánh số như "6.1 Machine
        # Translation") hầu như không bao giờ chứa dấu phẩy/chấm phẩy GIỮA
        # câu — đó là dấu hiệu của một CÂU VĂN đầy đủ, không phải tiêu đề.
        # Tín hiệu này bắt được phần lớn các bước chứng minh/danh sách bị đánh
        # số nhầm thành heading (vd "3. Từ đỉnh A, vẽ một đường thẳng song
        # song với hai") mà không cần biết trước nội dung tài liệu nào.
        return False

    non_space = sum(1 for ch in stripped if not ch.isspace())
    if non_space == 0:
        return False
    letters = sum(1 for ch in stripped if ch.isalpha())
    if letters / non_space < _MIN_ALPHA_RATIO:
        return False

    return True


_REPEAT_SIMILARITY_THRESHOLD = 0.7
_REPEAT_MIN_OCCURRENCES = 3


def _normalize_for_repetition(title: str) -> str:
    """Giữ lại CHỈ chữ cái (bỏ số, dấu câu, khoảng trắng), viết thường — để so
    khớp gần đúng bỏ qua đúng loại nhiễu OCR hay gặp nhất: số trang chạy theo
    header/footer và lẫn lộn chữ số/chữ cái (vd "INTELLIGENCE" -> "INTK1X1OENCK")."""
    return re.sub(r"[^a-zA-ZÀ-ỹ]", "", title).lower()


def _drop_repeated_near_duplicates(titles: List[str]) -> List[str]:
    """Loại các dòng LẶP LẠI GẦN GIỐNG NHAU nhiều lần trong CÙNG một danh sách
    — dấu hiệu chung của header/footer chạy lặp trên mỗi trang một tài liệu
    scan (vd "COMPUTING MACHINERY AND INTELLIGENCE 435" lặp dưới hàng chục
    biến thể lỗi OCR khác nhau mỗi trang). Đây là tín hiệu Ở CẤP DANH SÁCH,
    không phát hiện được bằng cách nhìn một dòng riêng lẻ — mỗi biến thể lỗi
    OCR khác nhau đủ để không dòng nào TỰ NÓ trông bất thường, nhưng việc CÙNG
    một hình dạng xuất hiện lặp đi lặp lại mới là bằng chứng đó không phải
    một chủ đề học được.

    Không hardcode chuỗi cụ thể nào — so khớp gần đúng bằng
    `difflib.SequenceMatcher` trên phiên bản đã chuẩn hoá (chỉ giữ chữ cái)."""
    import difflib

    normalized = [_normalize_for_repetition(t) for t in titles]
    keep = [True] * len(titles)
    for i, ni in enumerate(normalized):
        if not ni:
            continue
        close = sum(
            1
            for j, nj in enumerate(normalized)
            if j != i and nj and difflib.SequenceMatcher(None, ni, nj).ratio() >= _REPEAT_SIMILARITY_THRESHOLD
        )
        if close >= _REPEAT_MIN_OCCURRENCES - 1:
            keep[i] = False
    return [t for t, k in zip(titles, keep) if k]


def filter_topic_titles(titles: List[str]) -> List[str]:
    """Bộ lọc chất lượng ĐẦY ĐỦ dùng ở mọi nơi tiêu thụ danh sách tên chủ đề
    (kế hoạch ôn tập, gợi ý chủ đề) — kết hợp lọc từng dòng (`is_plausible_topic`)
    VÀ lọc lặp lại ở cấp danh sách (`_drop_repeated_near_duplicates`). Nhận
    một danh sách chuỗi thô, trả về danh sách đã lọc (thứ tự giữ nguyên)."""
    plausible = [t for t in titles if is_plausible_topic(t)]
    return _drop_repeated_near_duplicates(plausible)


@dataclass
class OutlineEntry:
    title: str
    position_ref: str
    order: int
    # Chỉ số (0-based) của section trong CÙNG danh sách sections mà
    # app/ingestion/parser.py::parse_document tạo ra cho chunking — cho phép
    # lấy lại đúng dải chunk thuộc chủ đề này (structural retrieval, xem
    # app/services/structural_retrieval.py). Mặc định 0 để không phá các nơi
    # đang tự dựng OutlineEntry mà chưa quan tâm trường này (vd tests).
    section_index: int = 0


def extract_outline(file_path: str) -> List[OutlineEntry]:
    if not os.path.exists(file_path):
        return []
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".docx":
        return _outline_docx(file_path)
    if ext == ".pdf":
        # Dùng LẠI chính danh sách section mà chunking sẽ dùng (thay vì tự mở
        # lại PDF một lần nữa) — đây là điểm mấu chốt để section_index của một
        # heading và section_index của các chunk thuộc cùng trang LUÔN khớp
        # nhau, vì cả hai cùng đọc từ một list, không phải hai phép tính độc
        # lập hy vọng trùng nhau (khác nhánh DOCX bên dưới, xem _outline_docx).
        from app.ingestion.parser import parse_document

        sections = parse_document(file_path)
        return _outline_pdf(sections)
    return []


def _dedupe_keep_order(entries: List[OutlineEntry]) -> List[OutlineEntry]:
    seen = set()
    result = []
    for e in entries:
        key = e.title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(
            OutlineEntry(
                title=e.title,
                position_ref=e.position_ref,
                order=len(result),
                section_index=e.section_index,
            )
        )
    return result


def _outline_docx(file_path: str) -> List[OutlineEntry]:
    from docx import Document as DocxDocument

    from app.ingestion.parser import DEFAULT_PARAGRAPHS_PER_SECTION

    doc = DocxDocument(file_path)

    entries: List[OutlineEntry] = []
    # Đếm theo đoạn văn KHÔNG rỗng, đúng cách parser.py gom section — nếu đếm
    # cả đoạn rỗng thì position_ref sẽ lệch. Đây VẪN là một lượt đọc riêng với
    # parse_document (khác nhánh PDF ở extract_outline) vì cần style_name của
    # từng đoạn văn (python-docx), thứ đã mất khi parser.py gộp đoạn văn thành
    # text thuần cho chunking — nhưng dùng CHUNG hằng số
    # DEFAULT_PARAGRAPHS_PER_SECTION từ parser.py nên section_index tính ra ở
    # đây LUÔN khớp với section_index parser.py sẽ gán cho chunk, không còn là
    # hai con số hardcode ở hai file phải tự nhớ giữ đồng bộ với nhau.
    non_empty_index = 0
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue

        style_name = (paragraph.style.name or "") if paragraph.style is not None else ""
        if style_name.startswith("Heading") or style_name.startswith("Title"):
            section_index = non_empty_index // DEFAULT_PARAGRAPHS_PER_SECTION
            entries.append(
                OutlineEntry(
                    title=text,
                    position_ref=f"Mục {section_index + 1}",
                    order=len(entries),
                    section_index=section_index,
                )
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
    # Kết thúc bằng dấu câu hết-câu (. ! ? : ; ,) áp dụng cho MỌI ứng viên, kể
    # cả mục đánh số — trước đây mục đánh số return True ngay, bỏ qua kiểm
    # tra này, nên một câu văn bản thường được đánh số kiểu danh sách/bước
    # chứng minh ("3. Từ đỉnh A, vẽ một đường thẳng...") vẫn lọt qua y hệt một
    # heading đánh số thật ("6.1 Machine Translation").
    if _SENTENCE_END_RE.search(stripped):
        return False
    # CHỈ nhận mục đánh số kiểu học thuật ("6.1 Machine Translation") làm
    # heading — đã BỎ HẲN nhánh Title-Case/ALL-CAPS trước đây (từng đo được
    # sinh 68-851 "heading" giả trên PDF thật, xem real_test_documents/
    # README.md). Một đoạn văn bị pypdf ngắt dòng theo độ rộng trang gần như
    # LUÔN thoả điều kiện "dòng ngắn, không dấu câu, có nội dung dài theo
    # sau" — heuristic đó không phân biệt được với heading thật trên PDF (dù
    # dùng được cho DOCX vì có style Heading thật, xem _outline_docx). Tài
    # liệu không có mục đánh số sẽ có dàn ý rỗng thay vì nhiễu — đúng nguyên
    # tắc "không bịa chủ đề" đã áp dụng cho nhánh DOCX không có style Heading.
    return bool(_NUMBERED_SECTION_RE.match(stripped))


def _outline_pdf(sections: List[Tuple[str, str]]) -> List[OutlineEntry]:
    """Nhận `sections` đã parse sẵn (app/ingestion/parser.py::parse_document),
    KHÔNG tự mở lại file PDF — mỗi phần tử `sections[i]` là (position_ref,
    toàn bộ text của trang i+1), đúng đơn vị 1-trang-1-section mà chunking
    cũng dùng, nên `section_index = i` ở đây trỏ đúng section mà chunker sẽ
    sinh chunk từ đó."""
    entries: List[OutlineEntry] = []

    for section_index, (position_ref, text) in enumerate(sections):
        lines = [ln for ln in text.splitlines() if ln.strip()]
        for i, line in enumerate(lines):
            following = " ".join(lines[i + 1 : i + 3])
            if _looks_like_heading(line, following):
                entries.append(
                    OutlineEntry(
                        title=line.strip(),
                        position_ref=position_ref,
                        order=len(entries),
                        section_index=section_index,
                    )
                )

    return _dedupe_keep_order(entries)[:_MAX_OUTLINE_ENTRIES]
