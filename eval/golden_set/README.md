# Golden Set — bộ case đánh giá

Bộ 393 case (267 Q&A + 126 hành vi) dùng để đánh giá EduTutor. Đây là dữ
liệu ĐẦU VÀO của eval (câu hỏi/kịch bản + kết quả mong đợi) — kết quả
CHẠY THẬT nằm ở `eval/results/`, báo cáo/phân tích nằm ở `eval/reports/`.

## Cấu trúc

```
golden_set/
├── README.md                  ← file này
├── data/
│   └── golden_set.jsonl       ← 393 case hiện hành (bản mới nhất)
├── schema/
│   └── golden_set.schema.json ← schema JSON cho mỗi case, dùng bởi validate_golden_set.py
├── sources/
│   └── run_doc_mapping.json   ← map document_id trong case -> UUID/tên file thật đã upload lên backend eval
├── annotations/
│   └── annotation_guidelines.md ← nguyên tắc viết/soát case, đúc kết từ các lỗi thật đã tìm thấy
└── changelog/
    └── CHANGELOG.md           ← lịch sử thay đổi bộ case theo thời gian
```

## Versioning

`data/golden_set.jsonl` luôn là **bản hiện hành**. Khi sửa/thêm/xoá case
theo cách ảnh hưởng tới kết quả đánh giá (không phải sửa lỗi chính tả nhỏ),
snapshot bản CŨ thành `data/golden_set_vN.jsonl` trước khi sửa, rồi ghi lại
thay đổi vào `changelog/CHANGELOG.md`. Không sửa lặng lẽ một case đã dùng
để đo baseline — nếu cần sửa, ghi rõ lý do vào changelog để biết vì sao một
số liệu cũ không còn so sánh trực tiếp được với số liệu mới.

## Trước khi sửa case

Đọc `annotations/annotation_guidelines.md` — vài lỗi thật đã gặp (tiền đề
case sai, `must_contain` không khớp cách hệ thống thật diễn đạt...) đều có
thể tránh được nếu tuân theo các nguyên tắc đó.
