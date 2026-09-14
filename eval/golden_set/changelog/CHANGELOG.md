# Changelog — Golden Set

Ghi lại các thay đổi tới `data/golden_set.jsonl` ảnh hưởng tới kết quả
đánh giá (thêm/sửa/xoá case, đổi corpus). Không ghi sửa lỗi chính tả không
ảnh hưởng kết quả chấm điểm.

## v1 — 2026-09-14 (bản gốc)

- 393 case: 267 Q&A (rag_qa, retrieval, grounding_citation,
  abstention_clarification, conversational, decomposition, multi_document,
  compare, summarize, apply, guardrail) + 126 hành vi (document_management,
  persistence, error_handling, personalization, mastery, quiz, flashcard,
  study_plan, profile).
- Corpus: 13 tài liệu Wikipedia độc lập (`eval/corpus/`).
- Kết quả đo lần đầu: `eval/results/baseline/` — xem
  `eval/reports/evaluation_report.md` cho số liệu đầy đủ.
- Vấn đề đã biết trong chính bộ case (chưa sửa, ghi nhận để theo dõi):
  khoảng 10 case có tiền đề bị lỗi trong định nghĩa case (không phải lỗi hệ
  thống) — xem `annotations/annotation_guidelines.md`.
