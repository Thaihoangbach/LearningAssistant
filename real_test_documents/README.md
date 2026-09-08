# Tài liệu test THẬT (tải từ nguồn công khai, không tự tạo)

8 file dưới đây đều tải trực tiếp từ arXiv, archive.org, Wikipedia và Project
Gutenberg — không phải nội dung tôi soạn ra. Mỗi file đã được chạy qua
`parse_document()`/`extract_outline()` thật (`backend/app/ingestion/`) để xác
nhận hành vi trước khi đưa vào đây, kết quả ở bảng cuối file.

## Nguồn và giấy phép

| File | Nguồn | Giấy phép/tình trạng |
| --- | --- | --- |
| `01_happy_attention_is_all_you_need.pdf` | [arXiv:1706.03762](https://arxiv.org/abs/1706.03762) — Vaswani et al., 2017 | arXiv cho phép tải về đọc/nghiên cứu cá nhân |
| `02_edge_deep_learning_survey_88trang.pdf` | [arXiv:1404.7828](https://arxiv.org/abs/1404.7828) — Schmidhuber, 2014 | arXiv, như trên |
| `03_edge_turing_1950_scanned.pdf` | [archive.org](https://archive.org/details/MIND--COMPUTING-MACHINERY-AND-INTELLIGENCE) — bản scan tạp chí Mind, 1950 | Công trình đã hết hạn bản quyền (public domain) |
| `04_happy_huong_dan_dinh_dang_bai_bao_vi.docx` | [Đại học Lạc Hồng - phòng NCKH](https://nckh.lhu.edu.vn/Data/News/339/files/08_Huong_dan_dinh_dang_bai_bao.docx) | Tài liệu hướng dẫn công khai của trường |
| `05_happy_wikipedia_tri_tue_nhan_tao_vi.pdf` | Wikipedia tiếng Việt, mục "Trí tuệ nhân tạo" (xuất PDF qua API chính thức) | CC BY-SA |
| `06_edge_wikipedia_dinh_ly_pythagoras_ngan.pdf` | Wikipedia tiếng Việt, mục "Định lý Pythagoras" | CC BY-SA |
| `07_unhappy_gutenberg_alice_wonderland.txt` | [Project Gutenberg #11](https://www.gutenberg.org/ebooks/11) — Alice's Adventures in Wonderland | Public domain |
| `08_happy_wikipedia_hoc_may_vi.pdf` | Wikipedia tiếng Việt, mục "Học máy" | CC BY-SA |

Dùng cho mục đích test nội bộ dự án — nếu định publish/redistribute lại các
file này ở nơi khác thì cần tuân theo giấy phép tương ứng của từng nguồn.

## Phát hiện quan trọng: outline PDF bị nhiễu nặng trên tài liệu thật

Đây là điều đáng chú ý nhất rút ra được từ việc test bằng tài liệu thật thay
vì tự tạo: **CẢ 6 file PDF thật đều khiến outline extraction sinh ra hàng
chục tới hàng trăm mục "dàn ý" sai**:

| File | Số trang (section) | Số mục outline rút được |
| --- | --- | --- |
| 01 - Attention Is All You Need | 15 | **68** |
| 02 - Deep Learning survey | 88 | **82** |
| 03 - Turing 1950 (scan/OCR) | 28 | **851** |
| 05 - Wikipedia: Trí tuệ nhân tạo | 17 | **185** |
| 06 - Wikipedia: Định lý Pythagoras | 29 | **283** |
| 08 - Wikipedia: Học máy | 11 | **84** |

Nguyên nhân: `_looks_like_heading()` trong `app/ingestion/outline.py` đoán
heading dựa trên "dòng ngắn (3-80 ký tự), không kết thúc bằng dấu câu, có nội
dung dài theo sau" — đây là heuristic hợp lý cho DOCX (có style Heading thật)
nhưng KHÔNG đáng tin cho PDF: một đoạn văn bình thường bị pypdf tách dòng theo
đúng độ rộng trang in, nên rất nhiều dòng bị ngắt giữa câu — trông giống hệt
một "heading ngắn" theo định nghĩa hiện tại dù thực chất chỉ là chỗ xuống dòng
tình cờ.

File `02_happy_pdf_co_dan_y.pdf` trong bộ test tự tạo trước (thư mục
`manual_test_documents/`) KHÔNG gặp vấn đề này vì tôi tự kiểm soát từng dòng
lúc sinh PDF (mỗi dòng heading do tôi vẽ luôn ngắn hơn 80 ký tự và không có
dấu câu) — đây chính xác là lý do test bằng tài liệu tự tạo dễ che giấu bug
mà tài liệu thật lộ ra ngay.

**Ảnh hưởng thực tế:** hầu hết người dùng tải lên một PDF thật (giáo trình,
paper, tài liệu scan) sẽ thấy phần "dàn ý" trên UI hiện ra hàng chục/hàng
trăm mục vô nghĩa thay vì vài chủ đề rõ ràng. Đây là bug đáng sửa nếu bạn
muốn — tôi chưa sửa vì bạn chỉ yêu cầu tìm tài liệu test, nhưng có thể sửa
ngay nếu bạn muốn (hướng khả thi: bỏ hẳn heuristic dòng-ngắn cho PDF, hoặc
thêm điều kiện lọc nghiêm hơn như yêu cầu dòng heading viết hoa toàn bộ hoặc
đứng ngay sau dòng trống).

## Bảng test case

| File | Loại | Điều cần theo dõi khi upload |
| --- | --- | --- |
| `01_happy_attention_is_all_you_need.pdf` | Happy (nhưng lộ bug outline) | Nội dung tiếng Anh chuẩn, RAG/quiz nên hoạt động tốt dù dàn ý hiển thị rối; test hỏi đáp bằng câu hỏi tiếng Anh lẫn tiếng Việt về multi-head attention, positional encoding. |
| `02_edge_deep_learning_survey_88trang.pdf` | Edge - tài liệu dài | 88 trang, nhiều chủ đề con — test hiệu năng xử lý nền (thời gian embed 88 section), và truy hồi mở rộng khi tài liệu lớn. |
| `03_edge_turing_1950_scanned.pdf` | Edge - OCR nhiễu | Văn bản có lỗi OCR thật (vd "TUBING" thay vì "TURING", từ bị ngắt sai). Test khả năng chịu lỗi của embedding/hỏi đáp khi nguồn có nhiễu ký tự. |
| `04_happy_huong_dan_dinh_dang_bai_bao_vi.docx` | Happy/Edge | DOCX tiếng Việt thật nhưng KHÔNG dùng style Heading (đa số văn bản hành chính Việt Nam định dạng bằng bold thủ công) → outline rỗng, đúng hành vi "không bịa chủ đề" của hệ thống. |
| `05_happy_wikipedia_tri_tue_nhan_tao_vi.pdf` | Happy (lộ bug outline) | Nội dung tiếng Việt có dấu đầy đủ, nhiều chú thích số [1][2]... — test full-text search có xử lý đúng ký tự đặc biệt trong ngoặc vuông không. |
| `06_edge_wikipedia_dinh_ly_pythagoras_ngan.pdf` | Edge | Có công thức toán, ký tự Hy Lạp (Πυθαγόρας) — test parser/embedding với ký tự Unicode ngoài bảng chữ cái Latin/Việt thông thường. |
| `07_unhappy_gutenberg_alice_wonderland.txt` | Unhappy | Đuôi `.txt` — phải bị từ chối ngay ở bước upload (`ALLOWED_EXTENSIONS` trong `app/routers/documents.py`), không tạo Document nào trong DB. |
| `08_happy_wikipedia_hoc_may_vi.pdf` | Happy (lộ bug outline) | Nội dung đúng chủ đề app đang phục vụ (học máy) — tốt để test quiz/flashcard sinh ra có bám sát nội dung thật không. |

## Case không thể "tìm được thật"

Hai case sau về bản chất KHÔNG tồn tại "trong tự nhiên" — một file bị hỏng
hay một file đổi nhầm đuôi luôn là kết quả của một hành động cụ thể (lỗi
upload, nhầm lẫn), không phải nội dung ai đó xuất bản. Tôi vẫn giữ lại 2 file
tự tạo trước đó cho hai case này thay vì cố "tìm" ra một thứ không có thật:

- `manual_test_documents/09_unhappy_sai_dinh_dang.txt`
- `manual_test_documents/10_unhappy_pdf_gia_bi_hong.pdf`

## Case bổ sung không có file (giống ghi chú lần trước)

- **File >30MB**: cả 8 file thật ở đây đều dưới 2.2MB (văn bản thuần chữ hiếm
  khi vượt 30MB) — cần một PDF ảnh/scan chất lượng cao thật lớn mới chạm
  ngưỡng `MAX_FILE_MB`. Dùng tạm một file scan lớn bạn có sẵn để test.
- **Upload trùng tên + môn học** để test versioning: upload lại
  `01_happy_attention_is_all_you_need.pdf` lần thứ hai với cùng tên môn học.
