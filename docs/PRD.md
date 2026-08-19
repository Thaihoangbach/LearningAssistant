# PRD - EduTutor: Trợ lý học tập cá nhân hoá dùng LLM + RAG

**Trạng thái:** MVP đã code xong và chạy được · **Ghi chú:** tài liệu này viết lại sau khi đã làm xong, dựa trên code thật và kết quả chạy eval thật, không phải bản kế hoạch viết trước khi code · **Đối tượng chính:** người tự học bằng tài liệu của mình

> EduTutor là app cho phép tải tài liệu học tập (PDF/DOCX) lên, sau đó hỏi đáp có trích dẫn nguồn, tự sinh quiz/flashcard để ôn tập, và theo dõi mức độ thành thạo (mastery) theo từng chủ đề để biết nên học tiếp cái gì. Mục tiêu là hỗ trợ tự học có căn cứ - không thay giáo viên, không chấm điểm chính thức, và quan trọng nhất là không được bịa nội dung ngoài tài liệu đã tải lên.

Sơ đồ kiến trúc: [`architecture-diagrams.md`](./architecture-diagrams.md)

## 1. Vấn đề cần giải quyết

Khi tự học một chủ đề mới (ví dụ Machine Learning), thường sẽ tích một đống tài liệu: slide, giáo trình PDF, ghi chú... nhưng lại thiếu vài thứ:

- **Tra cứu nhanh có căn cứ** - hỏi lại một khái niệm mà không muốn đọc lại cả chương, nhưng cũng không tin tưởng hỏi ChatGPT thường vì nó không biết nội dung đúng trong tài liệu của mình và có thể trả lời sai mà không kiểm tra được.
- **Tự kiểm tra** - không có ai ra đề, tự đặt câu hỏi ôn tập từ một tài liệu dài thì rất mất thời gian.
- **Biết nên ôn cái gì tiếp theo** - học nhiều chủ đề cùng lúc, không nhớ nổi chủ đề nào đang yếu.
- **Lập lịch ôn trước deadline** - có hạn thi/nộp bài nhưng không biết chia thời gian ôn thế nào cho hợp lý giữa các chủ đề.

Vì đây là project đã làm xong chứ không phải PRD viết trước khi code, nên phần mục tiêu ở dưới không phải là con số kỳ vọng chưa kiểm chứng - đã có bộ 54 case eval chạy thật với Gemini API (`eval/golden_set.jsonl`, xem chi tiết ở [`eval/report.md`](../eval/report.md)), chạy 4 lượt để so sánh cấu hình. Số liệu ở mục 2 lấy trực tiếp từ đó.

### Cái đã làm được và cái chưa

| Vấn đề | Trạng thái | Bằng chứng |
| --- | --- | --- |
| Hỏi đáp có trích dẫn, không bịa khi thiếu căn cứ | Đã làm - generator + verifier 2 bước, guardrail 3 tầng chặn injection/jailbreak/làm bài hộ | Faithfulness 0.90 (N=40), Safety 1.00 (N=7) |
| Tự sinh quiz/flashcard có căn cứ | Đã làm - mỗi câu/thẻ verify riêng | Flashcard groundedness 1.00 (N=6); Quiz groundedness 0.67 (N=9) - thấp hơn kỳ vọng, xem mục 2 |
| Biết chủ đề nào cần ôn | Đã làm - rule-based, đọc lại mastery, không tốn quota LLM | Recommendation relevance 1.00 (N=4) |
| Lập lịch ôn theo số ngày còn lại | Đã làm - tính lại từ mastery mỗi lần gọi | Planner constraint satisfaction 1.00 (N=5) |
| Trả lời đúng độ sâu theo trình độ (beginner/advanced) | Chưa đạt - có tham số `level` nhưng chưa hiệu quả | Personalization chỉ 0.13 (N=15), điểm yếu nhất hệ thống |
| Không từ chối nhầm khi thật ra có căn cứ | Còn lỗi - 2/54 case từ chối sai một câu hỏi có căn cứ thật trong tài liệu | Xếp Critical trong `eval/report.md` |
| Cá nhân hoá theo mục tiêu dài hạn, gợi ý theo prerequisite, đăng nhập nhiều người dùng | Chưa làm | Xem mục 5 |

## 2. Mục tiêu & số liệu đo được

Đo trên bộ **Golden Set 54 case** (`eval/golden_set.jsonl`), chia 8 nhóm: RAG QA (26) · Personalization (10) · Safety (5) · Quiz (3) · Recommendation (3) · Study Planner (3) · Flashcard (2) · Analytics (2). Cấu hình đang chạy thật là hybrid retrieval (dense FAISS + BM25 qua RRF) + cross-encoder rerank.

| Chỉ số | Đo được | Mục tiêu đặt ra | Đạt? |
| --- | --- | --- | --- |
| Faithfulness (không bịa ngoài tài liệu) | **0.90** (N=40) | ≥ 0.85 | Đạt |
| Citation Accuracy | **0.75** (N=20) | ≥ 0.80 | Chưa đạt |
| Context Precision | **0.77** (N=22) | ≥ 0.70 | Đạt |
| Safety (chặn injection/jailbreak/làm bài hộ) | **1.00** (N=7) | 1.00 | Đạt |
| Quiz Groundedness | **0.67** (N=9) | ≥ 0.85 | Chưa đạt |
| Flashcard Groundedness | **1.00** (N=6) | ≥ 0.85 | Đạt |
| Recommendation Relevance | **1.00** (N=4) | ≥ 0.85 | Đạt |
| Planner Constraint Satisfaction | **1.00** (N=5) | 1.00 | Đạt |
| Personalization (đúng độ sâu theo `level`) | **0.13** (N=15) | ≥ 0.70 | Không đạt - điểm yếu nhất |
| Overall (tổng tiêu chí pass / tổng tiêu chí chấm) | **0.765** (104/136) | - | Tham khảo |

Không lấy trung bình cộng 8 dòng trên làm 1 con số duy nhất vì N chênh lệch quá nhiều giữa các dimension (Faithfulness N=40 so với Context Recall N=2), trung bình cộng đơn giản sẽ lệch. Cách tính chi tiết và giới hạn từng chỉ số xem `eval/report.md` mục 5, 15, 17.

Mỗi cấu hình đã chạy lặp lại 2 lần độc lập để xem con số nào là nhiễu ngẫu nhiên của LLM, con số nào là tín hiệu thật (chi tiết `eval/report.md` mục 15). Kết quả: Citation Accuracy và Context Precision không đổi giữa 2 lần chạy cùng cấu hình, nên chênh lệch so với baseline dense-only là thật. Personalization và Quiz Groundedness thì dao động 11-13pp giữa 2 lần chạy cùng code, nên đọc 2 số này nên trừ hao sai số, đừng coi là chính xác tuyệt đối.

Về p95 thời gian phản hồi: chưa đo bằng công cụ, chỉ có cảm nhận thủ công là chấp nhận được với 1 câu hỏi. Chưa có số liệu chính thức nên không ghi vào bảng trên, để ở mục open question.

## 3. Đối tượng dùng

**Chính - người tự học:** sinh viên hoặc người đi làm tự học thêm một chủ đề (ví dụ ML) bằng tài liệu PDF/DOCX của chính mình. Không có ai chấm bài hộ, cần tự kiểm tra xem hiểu đúng chưa và biết nên ưu tiên ôn phần nào trước khi hết thời gian.

**Ý tưởng gốc:** vừa đọc xong một chương dài, muốn hỏi lại một chỗ chưa chắc và nhận câu trả lời kèm đúng đoạn trong tài liệu - thay vì hỏi một chatbot chung chung không biết gì về tài liệu của mình.

Sản phẩm hiện chưa có khái niệm giáo viên/admin xem tiến độ nhiều người hoặc duyệt nội dung - tài liệu tải lên được dùng ngay sau khi xử lý xong, không qua ai duyệt lại. Việc này phù hợp với bối cảnh tự tải tài liệu của chính mình để tự học, nhưng là một giới hạn cần biết nếu sau này mở rộng cho nhiều người dùng chung (xem mục 5).

## 4. Đầu vào

| Loại | Phạm vi hiện tại |
| --- | --- |
| File | PDF và DOCX |
| Kích thước | tối đa 30 MB/file (`MAX_FILE_MB` ở `app/routers/documents.py`) |
| Ngôn ngữ | đa ngôn ngữ - embedding và rerank dùng model đa ngữ (`paraphrase-multilingual-mpnet-base-v2`, `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`); câu trả lời sinh ra đúng ngôn ngữ của câu hỏi, kể cả khi tài liệu nguồn khác ngôn ngữ |
| Cách trích xuất | PDF: mỗi trang 1 section (`Trang n`). DOCX: nhóm 10 đoạn văn liên tiếp thành 1 section (`Mục n`) vì DOCX không có khái niệm trang cố định |
| Chất lượng | cần có lớp text trích được, không hỗ trợ OCR - file scan/ảnh sẽ báo lỗi "không có nội dung text trích xuất được" |
| Phiên bản | upload lại cùng tên file + tên môn học sẽ tạo bản mới, bản cũ đánh dấu `is_latest = False` thay vì xoá/ghi đè - hỏi đáp và sinh quiz chỉ dùng bản mới nhất, bản cũ vẫn xem lại được trong danh sách |
| Người dùng | 1 `user_id` cố định (`demo-user`) ở frontend, chưa có đăng nhập/đa người dùng thật. Backend đã thiết kế theo `user_id` (mỗi user 1 FAISS index riêng) nên sau này bật đăng nhập thật không cần đổi lại phần retrieval |

## 5. Phạm vi & độ ưu tiên

| Trạng thái | Tính năng | Giá trị |
| --- | --- | --- |
| Đã làm | F1 - Quản lý tài liệu (upload, versioning, xử lý nền, xoá) | có nguồn tài liệu đáng tin, biết đang xử lý hay lỗi |
| Đã làm | F2 - Hỏi đáp RAG có trích dẫn, guardrail, lịch sử hội thoại, điều chỉnh theo trình độ | trả lời có căn cứ, từ chối khi thiếu căn cứ, chặn injection/làm bài hộ |
| Đã làm | F3 - Gợi ý học tiếp theo (rule-based, không gọi LLM) | biết ngay chủ đề yếu nhất |
| Đã làm | F4 - Sinh quiz trắc nghiệm (1 hoặc nhiều tài liệu, theo độ khó) + chấm + cập nhật mastery | tự kiểm tra có đáp án đúng, giải thích khớp tài liệu |
| Đã làm | F5 - Sinh flashcard | ôn nhanh thuật ngữ/khái niệm |
| Đã làm | F6 - Kế hoạch học tập theo số ngày còn lại | phân bổ thời gian ôn ưu tiên chủ đề yếu/chưa học |
| Đã làm | F7 - Mastery theo chủ đề (rule-based, recency-weighted) + dashboard | điểm mastery phản ánh đúng hiện trạng, không coi mọi lượt làm bài như nhau |
| Chưa làm | Cá nhân hoá theo mục tiêu học dài hạn (lưu Learning Profile, deadline/goal tự sinh kế hoạch) | `level`/`difficulty` hiện phải truyền tay mỗi request, chưa tự áp dụng theo hồ sơ |
| Chưa làm | Gợi ý theo prerequisite (đồ thị phụ thuộc giữa chủ đề) | cần dữ liệu quan hệ giữa các chủ đề, chưa có |
| Chưa làm | Theo dõi thời gian học thực tế | cần instrument sự kiện ở frontend, chưa làm |
| Chưa làm | Đăng nhập / đa người dùng thật, phân quyền | hiện `user_id` cố định `demo-user` |
| Chưa làm | Xoá/đổi tên cuộc hội thoại | chỉ tạo mới và xem lại được |
| Chưa làm | OCR cho tài liệu scan | chỉ nhận file có lớp text |
| Chưa làm | Xử lý "một phần căn cứ" | verifier hiện chỉ CÓ/KHÔNG, câu trả lời đúng một phần bị từ chối luôn cả câu |
| Không làm | Chấm điểm chính thức thay giáo viên, kết nối LMS, tìm Internet trực tiếp | giữ phạm vi trong một app tự học cá nhân dựa trên tài liệu tự tải lên |

### Ưu tiên sửa tiếp theo (dựa trên số liệu eval thật)

Xếp theo mức nghiêm trọng trong `eval/report.md` mục 13, 16, 18:

1. **False refusal ở RAG QA** (2 case từ chối sai một câu hỏi có căn cứ thật) - mức Critical, ưu tiên số 1 vì ảnh hưởng ngay cả câu hỏi cơ bản.
2. **Personalization** (9/10 case fail, lặp đúng 2 kiểu: bản beginner vẫn còn thuật ngữ chưa giải thích, hoặc bản advanced không đủ sâu hơn beginner) - lặp lại trên 5 chủ đề khác nhau nên đây là lỗi hệ thống, không phải ngẫu nhiên.
3. **Trích dẫn lẫn tài liệu ngoài phạm vi** (4 case, khi nội dung trùng lặp giữa các tài liệu) - mức Medium.
4. **Quiz groundedness đo 0.67** nhưng phần lớn là do giám khảo chấm sai (hiểu nhầm việc hệ thống cố tình giấu đáp án ở bước sinh quiz là thiếu sót) - cần xem lại cách chấm trước khi kết luận đây là lỗi thật.

## 6. Tính năng & tiêu chí chấp nhận

### F1 - Quản lý tài liệu

- Upload PDF/DOCX qua `POST /documents`, trả về ngay `document_id` và trạng thái "đang xử lý"; xử lý (parse -> chunk -> embed -> index) chạy nền qua FastAPI `BackgroundTasks`, không chặn request.
- File sai định dạng hoặc quá 30 MB bị từ chối ngay kèm lý do, trước khi tạo bản ghi xử lý nền.
- Lỗi trong lúc xử lý (parse hỏng, không trích được text, lỗi embedding) được bắt lại và ghi vào `Document.status = "lỗi"` kèm `error_reason`, không để tiến trình treo im.
- Frontend poll `GET /documents` mỗi 2 giây để cập nhật trạng thái mà không cần người dùng tự làm mới trang.
- Upload lại cùng tên file + môn học tạo bản mới (`version` tăng, bản cũ `is_latest = False`); hỏi đáp và sinh quiz chỉ dùng bản mới nhất.
- Xoá tài liệu thì xoá luôn file gốc, bản ghi DB, và toàn bộ vector liên quan trong FAISS.

### F2 - Hỏi đáp RAG có trích dẫn

- Câu trả lời chỉ dựa trên chunk truy hồi từ tài liệu `status = "sẵn sàng"` và `is_latest = True` thuộc đúng `user_id` (lọc thêm theo `course_name` nếu có) - không có tài liệu nào ngoài tập này lọt vào prompt.
- Guardrail chạy 3 tầng trước khi vào generator/verifier để đỡ tốn quota Gemini: tầng 1 rule-based chặn ngay yêu cầu "làm bài hộ", tầng 2 rule-based chặn ngay pattern injection/jailbreak rõ ràng, tầng 3 chỉ câu hỏi mơ hồ (khớp từ khoá nhạy như "vai trò", "system", "prompt") mới gọi 1 lượt Gemini làm gatekeeper phân loại. Đa số câu hỏi bình thường không khớp gì cả nên không tốn thêm lượt gọi nào.
- Generator sinh câu trả lời nháp từ đoạn trích; Verifier (một lượt gọi LLM riêng, không nhận lịch sử hội thoại) xác nhận nội dung có nêu trực tiếp hoặc suy ra được từ đoạn trích trước khi trả về - nếu không thì trả "Chưa đủ căn cứ trong kho tài liệu để trả lời chắc chắn câu hỏi này." thay vì bịa.
- Không có chunk nào đạt `min_score` (mặc định 0.3) thì trả ngay "Nội dung này chưa có trong tài liệu bạn đã tải lên.", không gọi LLM.
- Mọi câu trả lời có kết luận đều kèm `sources`: tên tài liệu + vị trí (Trang n hoặc Mục n), loại trùng trước khi trả về.
- Hiểu câu hỏi tiếp nối dựa trên tối đa 3 lượt hội thoại gần nhất, chỉ đưa vào prompt của generator, không đưa vào prompt của verifier - để verifier vẫn chỉ chấp nhận câu trả lời có căn cứ trong đoạn trích hiện tại, lịch sử hội thoại không bị tính là "tài liệu".
- Tham số `level` (beginner/advanced) chỉnh hướng dẫn prompt generator để đổi độ sâu câu trả lời - đã cài đặt nhưng chưa đạt hiệu quả đo được (xem mục 2, Personalization chỉ 0.13).
- Câu hỏi kiểu "tôi nên học gì tiếp theo?" được nhận diện và trả lời trực tiếp từ dữ liệu mastery đã có, không qua RAG, không gọi LLM.

### F3 - Gợi ý học tiếp theo

- Nhận diện ý định bằng regex trên các mẫu câu như "nên học gì tiếp theo", "what should I study next".
- Đọc lại `MasteryScore` đã có theo `user_id` (lọc thêm `course_name` nếu có); nếu có chủ đề dưới ngưỡng 0.4 thì ưu tiên gợi ý tối đa 3 chủ đề yếu nhất, nếu không thì gợi ý chủ đề thấp điểm nhất trong số các chủ đề đã ổn.
- Chưa có dữ liệu mastery nào (chưa làm quiz) thì trả thông báo rõ ràng thay vì gợi ý rỗng hoặc đoán mò.
- Tự động phản ánh kết quả quiz mới nhất mà không cần code thêm gì: `MasteryScore` được cập nhật ngay khi nộp bài, nên lần gọi gợi ý tiếp theo tự lấy đúng dữ liệu mới.

### F4 - Sinh quiz trắc nghiệm

- Sinh quiz từ 1 hoặc nhiều tài liệu `"sẵn sàng"`; với nhiều tài liệu thì truy hồi riêng từng tài liệu (dùng tên file làm query) để câu hỏi không dồn hết vào 1 tài liệu.
- Generator sinh JSON gồm câu hỏi, 4 lựa chọn, đáp án đúng, giải thích, và `chunk_index` tham chiếu đoạn trích làm căn cứ.
- Mỗi câu hỏi được verify riêng (một lượt gọi LLM khác): câu nào JSON hỏng, thiếu field, tham chiếu chunk sai đều bị loại luôn - không cố sửa hay đoán.
- Không sinh được câu nào xác minh được thì trả lỗi rõ ràng, không trả quiz rỗng.
- Response sinh quiz không trả `correct_answer`/`explanation` - chỉ trả sau khi nộp bài, tránh lộ đáp án trước khi làm.
- Mỗi quiz gắn với một Topic (ưu tiên tên người dùng nhập, sau đó tên file nếu 1 tài liệu, hoặc tên môn học nếu nhiều tài liệu) để mọi quiz đều tính được vào mastery.
- Nộp đáp án ghi lại Attempt, tính lại mastery ngay bằng toàn bộ lịch sử Attempt của topic đó.

### F5 - Sinh flashcard

- Dùng chung kỹ thuật generator + verifier với F4, chỉ đổi output sang cặp front/back.
- Mỗi flashcard verify riêng trước khi trả về; card không xác minh được bị loại.
- Có gắn nguồn (document + vị trí) cho từng thẻ để kiểm chứng lại được.

### F6 - Kế hoạch học tập

- `GET /study-plan?days=N` tính lại toàn bộ kế hoạch mỗi lần gọi từ Topic/MasteryScore hiện có - không lưu bảng kế hoạch riêng, nên tiến độ mới (làm thêm quiz, chủ đề mới) luôn được cập nhật đúng ở lần gọi sau.
- Chủ đề chưa có điểm mastery (chưa làm quiz) được ưu tiên như điểm 0 - xếp sớm cùng chủ đề điểm thấp.
- Chia đều các chủ đề còn lại theo số ngày còn lại (round-robin theo thứ tự ưu tiên).
- `days <= 0` hoặc không có chủ đề nào thì trả kế hoạch rỗng, không lỗi.

### F7 - Mastery theo chủ đề

- Công thức rule-based recency-weighted: mỗi lượt đúng góp +1 x trọng số, sai góp 0, trọng số giảm dần theo nửa chu kỳ 14 ngày (lượt gần đây quan trọng hơn lượt cũ).
- Điểm trong khoảng 0-1, phân loại "tốt" (≥ 0.75), "trung bình" (≥ 0.4), còn lại là "yếu".
- `MasteryScore` là cache - tính lại và ghi đè mỗi khi có Attempt mới, để dashboard/gợi ý/kế hoạch đọc nhanh không phải quét lại lịch sử mỗi lần.
- Dashboard (`GET /mastery`) trả điểm theo chủ đề kèm phân loại, cộng số liệu: số tài liệu sẵn sàng/đang xử lý, số quiz đã làm, tổng lượt làm bài và tỉ lệ đúng.

## 7. Yêu cầu phi chức năng

- An toàn nội dung: guardrail 3 tầng ở F2 là lớp chặn duy nhất trước generator, chưa có ai duyệt tay từng câu trả lời - verifier tự động là cơ chế chặn bịa chính.
- Quyền truy cập: mỗi `user_id` có 1 FAISS index riêng trên đĩa, không tồn tại index chung để lọc metadata sau - nên không có đường nào truy hồi lẫn sang dữ liệu user khác.
- Độ tin cậy: không trả lời khi điểm liên quan dưới ngưỡng hoặc verifier từ chối; lỗi xử lý tài liệu luôn được bắt và ghi rõ nguyên nhân thay vì để tiến trình nền chết im.
- Hiệu năng: chưa có số liệu p95 chính thức, đây là chỗ cần đo thêm trước khi cam kết một con số cụ thể.
- Chi phí: embedding và rerank chạy local, miễn phí, không giới hạn - chỉ generator/verifier/gatekeeper mới gọi Gemini API (free tier), để dành quota cho đúng chỗ cần khả năng ngôn ngữ thật.
- Truy hồi: bắt buộc dùng hybrid - dense một mình hay bỏ sót thuật ngữ/tên riêng chính xác, nên có thêm nhánh BM25 hợp nhất bằng Reciprocal Rank Fusion rồi rerank bằng cross-encoder để chấm điểm liên quan trực tiếp.
- Đánh giá AI: Golden Set 54 case, 8 nhóm, chấm bằng rule-based hoặc LLM-as-judge tuỳ nhóm; mỗi cấu hình chạy lặp lại 2 lần để tách nhiễu ngẫu nhiên của LLM khỏi tín hiệu thật trước khi kết luận, nên giữ cách này cho những lần đánh giá sau chứ không chỉ đo 1 lần rồi kết luận luôn.
- Khả dụng: lỗi upload/xử lý tài liệu luôn có status + error_reason hiển thị được ở frontend, không có trạng thái treo không rõ nguyên nhân.

## 8. Definition of Done - trạng thái hiện tại

Hành trình chính đã chạy được end-to-end thật: tải tài liệu -> đợi trạng thái sẵn sàng -> hỏi đáp và mở nguồn trích dẫn -> làm quiz/flashcard và nhận mastery cập nhật -> xem gợi ý học tiếp theo và kế hoạch ôn tập -> xem dashboard tổng quan. Cả 7 tính năng chính (F1-F7) đạt tiêu chí ở mục 6.

Ba điểm chưa hoàn hảo cần nói thẳng, không nên báo là "xong hết":

- Không phải 0 trường hợp từ chối sai - Golden Set ghi nhận 2/54 case từ chối sai một câu hỏi có căn cứ thật (mức Critical, lỗi nghiêm trọng nhất còn tồn tại).
- Không phải mọi câu trả lời đều đúng độ sâu theo trình độ - Personalization chỉ 0.13/1.00, thấp hơn hẳn các nhóm còn lại.
- Chưa có công cụ migration - `models.py` đổi schema (thêm cột, bảng mới) thì phải xoá `edututor.db` cũ và tạo lại, chứ chưa migrate được - cần biết trước khi nâng cấp phiên bản trên dữ liệu thật đang có.

## 9. Việc còn đang mở

| Câu hỏi | Vì sao còn mở |
| --- | --- |
| Cách xử lý false refusal (từ chối sai câu hỏi có căn cứ thật) | Đã biết nguyên nhân là "retrieval + verifier quá thận trọng" nhưng chưa có cách fix cụ thể - ưu tiên cao nhất |
| Thiết kế Learning Profile lưu trữ dài hạn | Cần để Personalization tự động áp dụng thay vì phụ thuộc tham số mỗi request |
| p95 thời gian phản hồi thật | Chưa đo bằng công cụ, hiện chỉ có cảm nhận thủ công khi test |
| Ngưỡng `min_score` mặc định 0.3 có tối ưu chưa | Chọn theo kinh nghiệm ban đầu, chưa quét nhiều giá trị để so sánh đánh đổi Faithfulness/Recall |
| Có nên giới hạn phạm vi trích dẫn theo môn học mặc định | Sẽ giải quyết phần lớn lỗi trích dẫn lẫn tài liệu, nhưng chưa quyết định có nên bắt buộc `course_name` hay để tuỳ chọn như hiện tại |
| Chạy lặp lại N≥5/cấu hình cho eval | N=2 hiện tại chỉ đủ để xác nhận có nhiễu, chưa đủ để ước lượng chính xác độ lớn nhiễu - đang bị giới hạn bởi quota Gemini free tier (500 request/ngày) |

## 10. Ghi chú

Tài liệu này viết lại sau khi code đã chạy được và đã có kết quả eval thật, không phải bản chờ ký duyệt trước khi làm. Khi có thay đổi lớn về phạm vi hoặc chạy eval lại, nên cập nhật trực tiếp mục 2, 5, 8, 9 thay vì tạo file mới song song.
