# Corpus Golden Set mới (hoàn toàn độc lập với dữ liệu đã dùng trước đó)

13 file dưới đây được chọn và tải MỚI cho lần xây Golden Set này — không
trùng bất kỳ file nào trong `eval/documents/` (bộ cũ, đã xoá, gắn với
kiến trúc FAISS/sentence-transformers đã ngừng dùng) hay `real_test_documents/`
(bộ dùng để test outline/parser trước đó trong phiên làm việc, và 2 file
trong đó — Wikipedia "Học máy", "Trí tuệ nhân tạo" — đã được tải lên thử
nghiệm thật qua `/documents` trong phiên này). Mục tiêu: một corpus khách
quan, không bị ảnh hưởng bởi việc đã biết trước hệ thống xử lý tốt/kém với
tài liệu nào.

Toàn bộ tải qua API xuất PDF chính thức của Wikipedia
(`https://{lang}.wikipedia.org/api/rest_v1/page/pdf/{title}`) — cùng cơ chế
`real_test_documents/README.md` đã dùng, giấy phép CC BY-SA. Đã verify qua
đúng `parse_document()`/`extract_outline()` thật của app trước khi đưa vào.

## Danh sách và nguồn

| File | Nguồn | Vai trò trong Golden Set |
| --- | --- | --- |
| `01_hoc_sau_vi.pdf` | [vi.wikipedia.org/wiki/Học_sâu](https://vi.wikipedia.org/wiki/H%E1%BB%8Dc_s%C3%A2u) | Core DL — định nghĩa, kiến trúc, ứng dụng |
| `02_mang_than_kinh_nhan_tao_vi.pdf` | [vi.wikipedia.org/wiki/Mạng_thần_kinh_nhân_tạo](https://vi.wikipedia.org/wiki/M%E1%BA%A1ng_th%E1%BA%A7n_kinh_nh%C3%A2n_t%E1%BA%A1o) | Core DL — cấu trúc mạng, backprop, optimizer |
| `03_mang_than_kinh_tich_chap_vi.pdf` | [vi.wikipedia.org/wiki/Mạng_thần_kinh_tích_chập](https://vi.wikipedia.org/wiki/M%E1%BA%A1ng_th%E1%BA%A7n_kinh_t%C3%ADch_ch%E1%BA%ADp) | Core DL — CNN, local connectivity, weight sharing |
| `04_cay_quyet_dinh_vi.pdf` | [vi.wikipedia.org/wiki/Cây_quyết_định](https://vi.wikipedia.org/wiki/C%C3%A2y_quy%E1%BA%BFt_%C4%91%E1%BB%8Bnh) | Core ML cổ điển — mô hình dự báo dạng cây |
| `05_hoi_quy_tuyen_tinh_vi.pdf` | [vi.wikipedia.org/wiki/Hồi_quy_tuyến_tính](https://vi.wikipedia.org/wiki/H%E1%BB%93i_quy_tuy%E1%BA%BFn_t%C3%ADnh) | Core ML cổ điển — nội dung MỎNG (1485 ký tự, 2 section), chỉ đủ cho vài case định nghĩa/công thức cơ bản, không đủ cho case đa-hop |
| `06_su_qua_khop_vi.pdf` | [vi.wikipedia.org/wiki/Sự_quá_khớp](https://vi.wikipedia.org/wiki/S%E1%BB%B1_qu%C3%A1_kh%E1%BB%9Bp) | Core ML — overfitting/underfitting, bias-variance |
| `07_xac_suat_vi.pdf` | [vi.wikipedia.org/wiki/Xác_suất](https://vi.wikipedia.org/wiki/X%C3%A1c_su%E1%BA%A5t) | Nền tảng toán — thay cho "Xác suất thống kê" (bản đầu quá ngắn, 254 ký tự, đã loại) |
| `08_dich_may_bang_no_ron_vi.pdf` | [vi.wikipedia.org/wiki/Dịch_máy_bằng_nơ-ron](https://vi.wikipedia.org/wiki/D%E1%BB%8Bch_m%C3%A1y_b%E1%BA%B1ng_n%C6%A1-ron) | Ứng dụng DL — liên quan gián tiếp tới Attention/Transformer nhưng KHÔNG phải cùng tài liệu đã test |
| `09_random_forest_en.pdf` | [en.wikipedia.org/wiki/Random_forest](https://en.wikipedia.org/wiki/Random_forest) | Core ML (tiếng Anh) — ensemble method, không có bài Wikipedia tiếng Việt tương xứng |
| `10_gradient_descent_en.pdf` | [en.wikipedia.org/wiki/Gradient_descent](https://en.wikipedia.org/wiki/Gradient_descent) | Core ML (tiếng Anh) — thuật toán tối ưu |
| `11_precision_and_recall_en.pdf` | [en.wikipedia.org/wiki/Precision_and_recall](https://en.wikipedia.org/wiki/Precision_and_recall) | Model evaluation (tiếng Anh) — metric đánh giá mô hình |
| `12_reinforcement_learning_en.pdf` | [en.wikipedia.org/wiki/Reinforcement_learning](https://en.wikipedia.org/wiki/Reinforcement_learning) | Core ML (tiếng Anh) — file dài nhất (70k ký tự), tốt cho case multi-chunk/multi-section |
| `13_offtopic_am_thuc_vi.pdf` | [vi.wikipedia.org/wiki/Phở](https://vi.wikipedia.org/wiki/Ph%E1%BB%9F) | **Ngoài chủ đề, cố ý** — không liên quan ML/DL, dùng làm tài liệu âm tính cho case abstention/no-evidence và test "không lấy nhầm nguồn không liên quan" |

## Kết quả verify qua parser thật

| File | Sections | Ký tự | Outline entries |
| --- | ---: | ---: | ---: |
| 01_hoc_sau_vi.pdf | 16 | 49073 | 0 |
| 02_mang_than_kinh_nhan_tao_vi.pdf | 8 | 21420 | 0 |
| 03_mang_than_kinh_tich_chap_vi.pdf | 4 | 7397 | 1 |
| 04_cay_quyet_dinh_vi.pdf | 6 | 9713 | 0 |
| 05_hoi_quy_tuyen_tinh_vi.pdf | 2 | 1485 | 0 |
| 06_su_qua_khop_vi.pdf | 2 | 3187 | 1 |
| 07_xac_suat_vi.pdf | 8 | 22747 | 2 |
| 08_dich_may_bang_no_ron_vi.pdf | 3 | 5983 | 2 |
| 09_random_forest_en.pdf | 15 | 39298 | 1 |
| 10_gradient_descent_en.pdf | 13 | 29284 | 0 |
| 11_precision_and_recall_en.pdf | 12 | 31270 | 1 |
| 12_reinforcement_learning_en.pdf | 23 | 70228 | 1 |
| 13_offtopic_am_thuc_vi.pdf | 14 | 37212 | 0 |

**Lưu ý về outline**: phần lớn file có 0-2 outline entries vì Wikipedia PDF
export không dùng heading đánh số kiểu học thuật ("6.1 ...") mà
`_NUMBERED_SECTION_RE` yêu cầu (xem `app/ingestion/outline.py`, heuristic
Title-Case/ALL-CAPS đã bị bỏ vì gây nhiễu trên tài liệu thật) — đây là hành
vi ĐÚNG, không phải lỗi. Hệ quả: tính năng Tóm tắt (structural retrieval
theo `DocumentTopic`) sẽ có rất ít/không có chủ đề để tóm tắt trên hầu hết
các file này; case Summarize trong Golden Set nên tập trung vào các file có
outline entries (03, 06, 07, 08, 09, 11, 12) hoặc case này nên assert đúng
hành vi "không có chủ đề khả dụng" thay vì giả định luôn có outline.

## Case KHÔNG có trong bộ này (không phải "quên", cố ý để lại cho Phase 5)

Không tải lại file lỗi định dạng/corrupted — hai case này về bản chất luôn
phải tự tạo (không "tìm được thật"), sẽ tạo trực tiếp khi cần ở Phase 5
(adversarial), không phải một phần của corpus kiến thức.
