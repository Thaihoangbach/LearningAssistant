# PRD - EduTutor: Trợ lý học tập cá nhân hoá dùng LLM + RAG

EduTutor là app cho phép tải tài liệu học tập (PDF/DOCX) lên, sau đó hỏi đáp có trích dẫn nguồn, tự sinh quiz/flashcard để ôn tập, và theo dõi mức độ thành thạo (mastery) theo từng chủ đề để biết nên học tiếp cái gì. Sản phẩm hỗ trợ tự học có căn cứ - không thay giáo viên, không chấm điểm chính thức, và không được bịa nội dung ngoài tài liệu đã tải lên.


## 1. Problem statement

Khi tự học một chủ đề mới (ví dụ Machine Learning), mình hay tích một đống tài liệu: slide, giáo trình PDF, ghi chú... nhưng lại thiếu vài thứ để học hiệu quả.

Ba việc bị lặp lại mỗi lần tự học mà chưa có công cụ nào giải quyết gọn:

- **Tra cứu lại một khái niệm** - đã đọc qua nhưng không nhớ chính xác, muốn hỏi lại mà không phải đọc lại cả chương.
- **Tự kiểm tra xem hiểu đúng chưa** - không có ai ra đề, tự đặt câu hỏi ôn tập từ một tài liệu dài rất mất thời gian.
- **Biết nên ôn cái gì tiếp theo** - học nhiều chủ đề song song, không nhớ nổi chủ đề nào đang yếu nhất.

### Pain point ưu tiên

| Pain point | Quy trình hiện tại - vấn đề | Tác động | Root cause |
| --- | --- | --- | --- |
| Tra cứu lại một khái niệm đã học | Đọc lại cả tài liệu hoặc hỏi một chatbot chung, không biết nó có bịa hay không | Mất thời gian, hoặc tin nhầm thông tin sai mà không kiểm chứng được | Chatbot chung không gắn với đúng tài liệu của mình, không có trích dẫn để đối chiếu |
| Tự kiểm tra kiến thức | Tự soạn câu hỏi ôn tập bằng tay, hoặc bỏ qua bước này luôn | Học xong không chắc mình đã hiểu đúng, dễ sai lệch kiến thức mà không biết | Không có công cụ sinh câu hỏi từ đúng nội dung tài liệu đang học |
| Biết chủ đề nào đang yếu | Tự nhớ lại kết quả những lần tự kiểm tra trước, không có ghi chép | Ôn sai trọng tâm, dồn thời gian vào chủ đề đã vững | Không có nơi lưu và tính lại điểm mastery theo thời gian |
| Lập lịch ôn trước deadline | Chia thời gian theo cảm tính | Ôn không đều, có chủ đề bị bỏ sót sát ngày thi | Không có cách tự động ưu tiên chủ đề yếu/chưa học khi chia lịch |

### Pain point nằm ngoài phạm vi và lý do

Việc theo dõi thời gian học thực tế (đo mình ngồi học bao lâu, tập trung ra sao) và cá nhân hoá theo mục tiêu học dài hạn (ví dụ tự sinh lộ trình theo goal "ôn thi trong 2 tuần") là những bài toán cần thu thập dữ liệu hành vi lâu dài hoặc lưu hồ sơ người học (Learning Profile) - vượt quá thời gian làm đồ án, nên để ngoài phạm vi MVP, ghi rõ ở mục 5 để không lẫn với việc "quên làm".

## 2. Persona

**Primary - người tự học:** sinh viên hoặc người đi làm tự học thêm một chủ đề mới bằng tài liệu PDF/DOCX của chính mình (slide, giáo trình, ghi chú). Không có ai chấm bài hộ, cần tự kiểm tra xem hiểu đúng chưa và biết nên ưu tiên ôn phần nào trước khi hết thời gian. Mức độ quen dùng AI không cao, cần giao diện đơn giản, không đòi hỏi biết viết prompt.

**Câu định vị:** *"Tôi vừa đọc xong một chương giáo trình dài, tôi muốn hỏi lại một chỗ chưa chắc và nhận được câu trả lời kèm đúng đoạn trong tài liệu - thay vì hỏi một chatbot chung chung không biết gì về tài liệu của tôi."*

**Phạm vi người dùng của MVP:** chỉ phục vụ một người dùng cho mỗi lần chạy (không có đăng nhập/phân quyền nhiều người trong MVP - xem mục 5, Won't). Nếu mở rộng sau này cho nhiều người dùng chung, cần thêm vai trò kiểu "quản trị" để duyệt nội dung trước khi dùng chung - nhưng việc đó ngoài phạm vi đồ án hiện tại vì mục tiêu là một app tự học cá nhân, không phải kho tri thức dùng chung.

## 3. Input

| Chiều input | Phạm vi dự kiến |
| --- | --- |
| Loại file | PDF và DOCX |
| Kích thước | dự kiến giới hạn khoảng 30 MB/file - cần thử với vài file thật để biết ngưỡng hợp lý trước khi chốt cứng |
| Ngôn ngữ | tài liệu chủ yếu tiếng Việt và tiếng Anh (giáo trình kỹ thuật hay có thuật ngữ Anh xen tiếng Việt); câu trả lời nên theo đúng ngôn ngữ của câu hỏi |
| Cách trích xuất | PDF theo trang, DOCX theo nhóm đoạn văn (DOCX không có khái niệm trang cố định) - cần giữ lại vị trí nguồn để trích dẫn kiểm tra lại được |
| Chất lượng | chỉ nhận tài liệu có lớp text trích được; OCR cho file scan để ở nhóm Could (F9), không làm ngay vì tốn thời gian mà chưa chắc cần thiết cho phần lớn tài liệu học tập |
| Phiên bản | có thể upload lại tài liệu đã có (ví dụ giáo trình bản chỉnh sửa) - cần quyết định giữ bản cũ hay ghi đè, xem mục 9 |
| Người dùng | một người dùng/phiên làm việc trong MVP, chưa có đăng nhập thật |

## 4. Scope & priority

| Priority | Feature | Giá trị |
| --- | --- | --- |
| **Must** | F1 - Quản lý tài liệu học tập (upload, xử lý nền, xoá) | có nguồn tài liệu đáng tin, biết đang xử lý hay lỗi |
| **Must** | F2 - Hỏi đáp RAG có trích dẫn nguồn | trả lời có căn cứ, mở được đúng đoạn trong tài liệu |
| **Must** | F3 - Guardrail an toàn cho câu hỏi | chặn injection/jailbreak và yêu cầu làm bài hộ trước khi trả lời |
| **Must** | F4 - Sinh quiz trắc nghiệm để tự kiểm tra + chấm bài | có đề ôn tập từ đúng tài liệu, biết đúng/sai ngay |
| **Must** | F5 - Theo dõi mastery theo chủ đề | biết mình đang mạnh/yếu chủ đề nào |
| **Should** | F6 - Sinh flashcard để ôn nhanh | ôn thuật ngữ/khái niệm nhanh hơn đọc lại tài liệu |
| **Should** | F7 - Gợi ý học tiếp theo + lập kế hoạch ôn tập theo deadline | biết ưu tiên ôn gì và chia thời gian thế nào |
| **Could** | F8 - Cá nhân hoá sâu hơn theo trình độ (Learning Profile lưu lâu dài) | không phải khai báo trình độ mỗi lần hỏi |
| **Could** | F9 - OCR cho tài liệu scan | nhận thêm được tài liệu dạng ảnh/scan |
| **Could** | F10 - Nhớ ngữ cảnh xuyên phiên làm việc | hỏi tiếp không phải nhắc lại bối cảnh |
| **Could** | F11 - Đăng nhập/đa người dùng thật | dùng được cho nhiều người, không chỉ một người/phiên |
| **Won't** | Chấm điểm chính thức thay giáo viên, kết nối LMS, tìm Internet trực tiếp, gợi ý theo prerequisite (cần đồ thị phụ thuộc giữa chủ đề, chưa có nguồn dữ liệu này) | giữ phạm vi trong một app tự học cá nhân dựa trên tài liệu tự tải lên, làm được trong thời gian đồ án |

## 5. Features & acceptance criteria

### F1 - Quản lý tài liệu học tập (Must)

**Pain point giải quyết:** cần một nơi tập trung tài liệu đang học, biết tài liệu nào dùng được để hỏi đáp.

**User stories**

1. Là người học, tôi muốn tải tài liệu lên và thấy trạng thái xử lý để biết hệ thống đang chạy hay đã lỗi.
2. Là người học, tôi muốn xoá một tài liệu không cần nữa mà không ảnh hưởng các tài liệu khác.

**AC**

- Given file đúng định dạng và trong giới hạn kích thước, when tải lên, then hệ thống trả về ngay và xử lý (tách nội dung, chia đoạn, tạo vector) chạy nền, không chặn người dùng làm việc khác.
- Khi xử lý lỗi (file hỏng, không trích được nội dung), hệ thống hiển thị rõ lý do, không để trạng thái "đang xử lý" treo mãi không rõ nguyên nhân.
- Tài liệu chỉ được dùng để trả lời sau khi xử lý xong ("sẵn sàng").
- File sai định dạng hoặc vượt giới hạn bị từ chối ngay kèm lý do cụ thể.
- Xoá tài liệu thì xoá luôn phần nội dung đã lập chỉ mục liên quan, không để sót dữ liệu mồ côi.

### F2 - Hỏi đáp RAG có trích dẫn nguồn (Must)

**Pain point giải quyết:** tra cứu lại một khái niệm trong tài liệu dài tốn thời gian, hỏi chatbot chung không tin tưởng được vì không kiểm chứng lại được.

**User stories**

1. Là người học, tôi muốn hỏi bằng ngôn ngữ tự nhiên để không phải mở từng tài liệu tự tìm.
2. Là người học, tôi muốn mở đúng đoạn nguồn để kiểm tra lại trước khi tin.
3. Là người học, tôi muốn hệ thống từ chối khi thiếu căn cứ để không dùng nhầm câu trả lời sai.

**AC**

- Câu trả lời chỉ dựa trên tài liệu đã xử lý xong ("sẵn sàng"), không dùng kiến thức ngoài tài liệu để kết luận.
- Mọi kết luận kèm tên tài liệu và vị trí nguồn (trang hoặc mục); người dùng mở được đúng đoạn.
- Khi không tìm được đoạn nào đủ liên quan, hệ thống báo rõ "chưa có trong tài liệu đã tải lên" thay vì cố trả lời.
- Có một bước xác minh lại câu trả lời trước khi trả về người dùng (không trả thẳng câu trả lời nháp của bước sinh nội dung) - nếu xác minh không qua thì báo "chưa đủ căn cứ để trả lời chắc chắn" thay vì bịa.
- Hiểu được câu hỏi tiếp nối trong cùng phiên hỏi đáp (ví dụ dùng đại từ nhắc lại ý trước) mà không cần người dùng lặp lại ngữ cảnh.
- Có tham số chọn trình độ (beginner/advanced) để đổi độ sâu câu trả lời - biết trước đây là rủi ro chưa chắc đạt mục tiêu ở mục 2, cần thử sớm.

### F3 - Guardrail an toàn cho câu hỏi (Must)

**Pain point giải quyết:** một app hỏi đáp mở cho LLM luôn có rủi ro bị dùng sai mục đích (dò system prompt, nhờ làm bài hộ để nộp, hỏi ngoài phạm vi học tập).

**User stories**

1. Là người học, tôi muốn hệ thống từ chối yêu cầu làm bài hộ để không bị lạm dụng, tự tôi vẫn phải tự học.
2. Là người phát triển, tôi muốn chặn được các kiểu dò hỏi injection/jailbreak phổ biến trước khi tốn lượt gọi LLM.

**AC**

- Câu hỏi rõ ràng là yêu cầu làm/giải bài hộ để nộp bị chặn, kèm thông báo gợi ý hỏi khái niệm cụ thể thay vì xin lời giải trọn vẹn.
- Câu hỏi khớp các mẫu injection/jailbreak rõ ràng (ví dụ yêu cầu bỏ qua chỉ dẫn hệ thống, tiết lộ system prompt) bị chặn ngay.
- Câu hỏi mơ hồ (có thể là câu hỏi học tập hợp lệ nhưng chạm từ khoá nhạy) được phân loại kỹ hơn trước khi quyết định chặn hay không, tránh chặn nhầm câu hỏi học tập bình thường.
- Ưu tiên xử lý rẻ trước, đắt sau: chỉ dùng đến bước gọi LLM để phân loại khi thật sự cần, để tiết kiệm quota.

### F4 - Sinh quiz trắc nghiệm để tự kiểm tra (Must)

**Pain point giải quyết:** tự soạn câu hỏi ôn tập từ tài liệu dài rất mất thời gian, dễ bỏ qua bước tự kiểm tra luôn.

**User stories**

1. Là người học, tôi muốn tạo một bộ câu hỏi trắc nghiệm từ tài liệu đã tải lên để tự kiểm tra.
2. Là người học, tôi muốn biết ngay đúng/sai và có giải thích sau khi trả lời một câu.

**AC**

- Sinh được câu hỏi trắc nghiệm (nhiều lựa chọn, 1 đáp án đúng) từ nội dung tài liệu đã chọn.
- Mỗi câu hỏi có căn cứ kiểm tra được lại từ đúng đoạn tài liệu dùng để sinh ra nó; câu nào không xác minh được thì loại, không đưa vào bộ quiz.
- Không sinh được câu nào xác minh được thì báo lỗi rõ ràng, không trả về quiz rỗng hoặc quiz có câu sai.
- Không lộ đáp án đúng ở bước tạo quiz - chỉ trả sau khi người dùng đã nộp câu trả lời.
- Sau khi nộp, hệ thống trả đúng/sai kèm giải thích ngắn.

### F5 - Theo dõi mastery theo chủ đề (Must)

**Pain point giải quyết:** không nhớ nổi chủ đề nào mình đang yếu nếu không ghi chép lại kết quả tự kiểm tra.

**User stories**

1. Là người học, tôi muốn thấy điểm mastery theo từng chủ đề để biết nên ôn gì.
2. Là người học, tôi muốn điểm này phản ánh đúng tình trạng gần đây, không bị kéo lệch bởi những lần làm bài rất lâu trước.

**AC**

- Mỗi lần làm xong một câu quiz, điểm mastery của chủ đề liên quan được cập nhật ngay.
- Công thức tính có tính đến thời gian - lượt làm bài gần đây ảnh hưởng nhiều hơn lượt cũ, để điểm phản ánh đúng trạng thái hiện tại.
- Có màn hình tổng quan xem điểm mastery theo từng chủ đề, cùng vài số liệu cơ bản (số tài liệu, số quiz đã làm, tỉ lệ đúng).

### F6 - Sinh flashcard (Should)

**AC**

- Sinh được flashcard (mặt trước/mặt sau) từ nội dung tài liệu đã chọn, dùng lại kỹ thuật xác minh nội dung giống F4.
- Mỗi thẻ gắn nguồn (tài liệu + vị trí) để kiểm chứng lại được.

### F7 - Gợi ý học tiếp theo và lập kế hoạch ôn tập (Should)

**AC**

- Hỏi kiểu "tôi nên học gì tiếp theo" được nhận diện và trả lời dựa trên dữ liệu mastery đã có, ưu tiên chủ đề điểm thấp nhất - không cần tốn một lượt gọi LLM cho việc này vì chỉ là đọc lại dữ liệu đã tính.
- Nhập số ngày còn lại tới hạn, hệ thống chia lịch ôn tập ưu tiên chủ đề yếu/chưa học lên trước.
- Kế hoạch tự cập nhật theo tiến độ mới nhất mỗi lần hỏi lại, không cần đồng bộ trạng thái kế hoạch cũ.

### F8-F11 - Các hạng mục Could còn lại

- **F8 Cá nhân hoá sâu hơn:** lưu trình độ/sở thích lâu dài (Learning Profile) thay vì phải khai báo `level` mỗi lần hỏi.
- **F9 OCR:** nhận thêm tài liệu dạng scan, mỗi đoạn trích từ OCR cần đánh dấu độ tin cậy vì kém chính xác hơn text gốc.
- **F10 Nhớ ngữ cảnh phiên làm việc:** hỏi tiếp trong cùng phiên không phải nhắc lại tài liệu/chủ đề đang bàn.
- **F11 Đăng nhập/đa người dùng:** mở app dùng được cho nhiều người, mỗi người có dữ liệu và tài liệu riêng.

## 6. Non-functional requirements

- **An toàn nội dung:** guardrail (F3) là lớp chặn trước khi vào bước sinh câu trả lời; bước xác minh (F2) là lớp chặn thứ hai chống bịa. Không có bước nào để lộ câu trả lời chưa qua xác minh.
- **Ranh giới dữ liệu:** nếu về sau có nhiều người dùng (F11), dữ liệu và tài liệu của người này không được lẫn sang người khác ở bất kỳ bước truy hồi nào - cần thiết kế ngay từ đầu để không phải sửa lại kiến trúc truy hồi sau này.
- **Hiệu năng:** chưa cam kết p95 cụ thể (xem mục 2) - sẽ đo baseline thật sớm rồi mới chốt ngưỡng.
- **Chi phí:** ưu tiên chạy các bước không cần khả năng ngôn ngữ (tách văn bản, tạo vector tìm kiếm) bằng mô hình chạy local miễn phí, chỉ gọi LLM ở đúng bước cần sinh/xác minh nội dung ngôn ngữ - tránh phí quota free tier cho việc không cần thiết.
- **Truy hồi:** cân nhắc kết hợp tìm theo ngữ nghĩa và tìm theo từ khoá thay vì chỉ dùng một loại, vì tài liệu học thuật có nhiều thuật ngữ/ký hiệu chính xác mà tìm ngữ nghĩa một mình dễ bỏ sót - cần thử nghiệm so sánh trước khi chốt.
- **Đánh giá:** dùng bộ câu hỏi chuẩn tự soạn (mục 2) để đo trước khi coi một tính năng là "xong", không chỉ test bằng cảm tính vài câu hỏi ngẫu nhiên.
- **Khả dụng:** lỗi upload/xử lý tài liệu luôn có trạng thái và lý do rõ ràng hiển thị được, không để người dùng đoán mò tại sao không chạy.

## 7. Definition of Done

MVP coi là xong khi hoàn thành được hành trình: tải tài liệu lên -> đợi trạng thái sẵn sàng -> hỏi đáp và mở được nguồn trích dẫn -> làm một quiz và thấy điểm mastery cập nhật -> xem được gợi ý/kế hoạch ôn tập (nếu kịp làm F7). Toàn bộ Must (F1-F5) đạt AC ở mục 6, và đạt các chỉ số ở mục 2 trên bộ câu hỏi chuẩn.

Ba điều kiện chặn riêng, không đánh đổi kể cả khi áp dụng kịch bản hạ cấp:

- **0 trường hợp** câu trả lời khẳng định nghiệp vụ mà không có trích dẫn nguồn.
- **0 trường hợp** lọt qua được các mẫu injection/jailbreak rõ ràng đã liệt kê khi thiết kế guardrail.
- **100%** câu hỏi yêu cầu làm bài hộ rõ ràng bị chặn, không trả lời một phần nào của yêu cầu đó.


