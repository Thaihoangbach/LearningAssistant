# EduTutor Golden Set — Bộ đánh giá Q&A và hành vi

Bộ Golden Set độc lập gồm **393 case** (267 case Q&A + 126 case hành vi),
chạy thật trên backend local, dùng để đánh giá EduTutor. Xem
**[reports/evaluation_report.md](reports/evaluation_report.md)** cho số
liệu và **[reports/failure_analysis.md](reports/failure_analysis.md)** cho
phân tích nguyên nhân gốc các vấn đề còn tồn tại — các mục dưới đây chỉ mô
tả cấu trúc thư mục.

## Cấu trúc

```
eval/
├── README.md                          ← file này
├── golden_set/                        ← bộ case (dữ liệu ĐẦU VÀO của eval)
│   ├── README.md                       ← cấu trúc + quy ước versioning
│   ├── data/golden_set.jsonl           ← 393 case hiện hành
│   ├── schema/golden_set.schema.json   ← schema JSON, dùng bởi validate_golden_set.py
│   ├── sources/run_doc_mapping.json    ← map document_id trong case -> UUID/tên file thật đã upload
│   ├── annotations/annotation_guidelines.md ← nguyên tắc viết/soát case
│   └── changelog/CHANGELOG.md          ← lịch sử thay đổi bộ case
├── corpus/                             ← 13 tài liệu PDF nguồn (Wikipedia) + README.md mô tả nguồn
├── scripts/                            ← chạy lại eval
│   ├── run_local_backend.py
│   ├── run_golden_set.py
│   ├── run_stateful_scenarios.py
│   ├── validate_golden_set.py          ← kiểm tra chất lượng bộ case, không gọi API
│   └── analyze_failures.py             ← tóm tắt/so sánh kết quả theo category, không gọi API
├── results/                            ← kết quả đã chạy (KHÔNG ghi đè giữa các lần chạy)
│   ├── README.md                       ← mục lục các lần chạy
│   └── baseline/                       ← lần đo đầu tiên, mốc so sánh gốc
└── reports/                            ← báo cáo
    ├── evaluation_report.md             ← số liệu, kết quả theo category
    └── failure_analysis.md              ← nguyên nhân gốc các vấn đề còn tồn tại
```

## Cách chạy lại từ đầu

```bash
# 0. (Tuỳ chọn) Kiểm tra bộ case không có lỗi tiền đề trước khi chạy thật —
#    nhanh, không gọi API nào
python eval/scripts/validate_golden_set.py

# 1. Khởi động backend local đúng cấu hình (ghi đè DATABASE_URL/STORAGE_*
#    về Docker local edututor-pg/edututor-minio, không đụng production)
python eval/scripts/run_local_backend.py   # giữ chạy trong 1 terminal riêng

# 2. Chạy 267 case Q&A -> eval/results/run_results_<ngày>.jsonl (tên file
#    tự động, không ghi đè lần chạy trước)
python eval/scripts/run_golden_set.py

# 3. Chạy 126 case hành vi -> eval/results/stateful_results_<ngày>.jsonl
python eval/scripts/run_stateful_scenarios.py

# 4. Xem tóm tắt kết quả theo category, hoặc so sánh với lần chạy trước
python eval/scripts/analyze_failures.py --file eval/results/run_results_<ngày>.jsonl
python eval/scripts/analyze_failures.py --file eval/results/run_results_<ngày-moi>.jsonl --compare eval/results/baseline/run_results.jsonl

# (Tuỳ chọn) Chạy nhanh một tập con 77 case đại diện thay vì toàn bộ 267:
python eval/scripts/run_golden_set.py --regression-only
```

Muốn TIẾP TỤC một lần chạy bị dang dở (vd crash giữa chừng vì hết hạn mức
API), truyền lại đúng `--out <filename>` đã dùng lần đó — script tự resume
dựa trên case nào đã có `request_ok=true`, không chạy lại từ đầu.

Mọi script tự tìm đúng `golden_set/data/golden_set.jsonl`/`golden_set/
sources/run_doc_mapping.json` và ghi kết quả vào `eval/results/` — chạy từ
bất kỳ đâu đều được, không cần `cd` vào `eval/scripts/`.

## Ghi chú quan trọng

- Toàn bộ 393 case chạy trên **backend local** (Docker: `edututor-pg`, `edututor-minio`), **không đụng production** — bắt buộc dùng `run_local_backend.py` để khởi động, không chạy `uvicorn` trực tiếp (dễ vô tình đọc `DATABASE_URL`/`STORAGE_*` production từ `.env` gốc).
- Case có `expected_answer` được chấm thêm bằng LLM judge (cần `OPENAI_API_KEY` hoặc `GEMINI_API_KEY` hợp lệ, tự nạp từ `.env` gốc qua `run_local_backend.py`/script).
- Sửa bộ case (`golden_set/data/golden_set.jsonl`)? Đọc `golden_set/README.md` (quy ước versioning) và `golden_set/annotations/annotation_guidelines.md` (lỗi thật từng gặp) trước.
