# Kết quả các lần chạy

Mỗi mốc so sánh có ý nghĩa được đóng gói thành một thư mục `baseline/`/`vN/`
gồm 2 file cố định: `run_results.jsonl` (case Q&A, `run_golden_set.py`) và
`stateful_results.jsonl` (case hành vi, `run_stateful_scenarios.py`) — xem
`eval/README.md` cho lệnh chạy. Các lần chạy nháp/trung gian trong lúc debug
không được giữ lại ở đây, chỉ mốc cuối cùng của mỗi đợt thay đổi mới được
đóng gói thành thư mục mới. File này chỉ là mục lục, cập nhật thủ công sau
mỗi mốc mới.

| Thư mục | Ngày | Ghi chú |
|---|---|---|
| `baseline/` | 2026-09-14 | Lần đo đầu tiên, mốc so sánh gốc (393 case: 267 Q&A + 126 hành vi) — xem `eval/reports/evaluation_report.md` |
| `v1/` | 2026-09-16 | Lần đo sau đợt sửa lỗi đầu tiên kể từ baseline (391 case: 265 Q&A + 126 hành vi — 2 case brittleness đã bỏ, xem `CHANGELOG.md`). Q&A: **204/265 (77.0%)** so với baseline 160/267 (59.9%). Hành vi: **41/41** so với baseline 40/41. Chi tiết thay đổi và số liệu đầy đủ: `eval/golden_set/changelog/CHANGELOG.md`, `eval/reports/evaluation_report.md`. |
