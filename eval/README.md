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
├── golden_set.jsonl                    ← 393 case (77 case có thêm field in_regression_set: true, dùng cho chạy nhanh --regression-only)
├── golden_set_schema.json              ← schema JSON cho mỗi case
├── run_doc_mapping.json                ← map document_id trong case -> UUID/tên file thật đã upload
├── corpus/                             ← 13 tài liệu PDF nguồn (Wikipedia) + README.md mô tả nguồn
├── scripts/                            ← chạy lại eval
│   ├── run_local_backend.py
│   ├── run_golden_set.py
│   └── run_stateful_scenarios.py
├── results/                            ← kết quả đã chạy
│   ├── run_results.jsonl                ← 267 case Q&A
│   └── stateful_results.jsonl           ← 126 case hành vi (41 kịch bản)
└── reports/                            ← báo cáo
    ├── evaluation_report.md             ← số liệu, kết quả theo category
    └── failure_analysis.md              ← nguyên nhân gốc các vấn đề còn tồn tại
```

## Cách chạy lại từ đầu

```bash
# 1. Khởi động backend local đúng cấu hình (ghi đè DATABASE_URL/STORAGE_*
#    về Docker local edututor-pg/edututor-minio, không đụng production)
python eval/scripts/run_local_backend.py   # giữ chạy trong 1 terminal riêng

# 2. Chạy 267 case Q&A -> eval/results/run_results.jsonl
#    (resume-logic: bỏ qua case đã có request_ok=true trong file --out —
#    muốn chạy lại thật từ đầu, xoá file cũ hoặc dùng --out tên khác)
python eval/scripts/run_golden_set.py --out run_results.jsonl

# 3. Chạy 126 case hành vi -> eval/results/stateful_results.jsonl
python eval/scripts/run_stateful_scenarios.py

# (Tuỳ chọn) Chạy nhanh một tập con 77 case đại diện thay vì toàn bộ 267:
python eval/scripts/run_golden_set.py --regression-only --out quick_check.jsonl
```

Cả 3 script tự tìm đúng `golden_set.jsonl`/`run_doc_mapping.json` ở thư mục
cha (`eval/`) và ghi kết quả vào `eval/results/` — chạy từ bất kỳ đâu đều
được, không cần `cd` vào `eval/scripts/`.

## Ghi chú quan trọng

- Toàn bộ 393 case chạy trên **backend local** (Docker: `edututor-pg`, `edututor-minio`), **không đụng production** — bắt buộc dùng `run_local_backend.py` để khởi động, không chạy `uvicorn` trực tiếp (dễ vô tình đọc `DATABASE_URL`/`STORAGE_*` production từ `.env` gốc).
- Case có `expected_answer` được chấm thêm bằng LLM judge (cần `OPENAI_API_KEY` hoặc `GEMINI_API_KEY` hợp lệ, tự nạp từ `.env` gốc qua `run_local_backend.py`/script).
