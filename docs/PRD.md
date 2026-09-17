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

Việc theo dõi thời gian học thực tế (đo mình ngồi học bao lâu, tập trung ra sao - cần instrument sự kiện ở giao diện, chưa thu thập) vẫn để ngoài phạm vi, vì đây là bài toán Learning Analytics riêng, không phải điều kiện để giải 3 pain point ưu tiên ở trên. Cá nhân hoá theo hồ sơ tự khai và mục tiêu học tập (Learning Profile, ngày thi từng môn) đã được đưa vào phạm vi Must (F7, F8) vì đây chính là phần giải quyết trực tiếp pain point "lập lịch ôn trước deadline" - ghi rõ ở mục 4 để không lẫn với việc "quên làm".

## 2. Persona

**Primary - người tự học:** sinh viên hoặc người đi làm tự học thêm một chủ đề mới bằng tài liệu PDF/DOCX của chính mình (slide, giáo trình, ghi chú). Không có ai chấm bài hộ, cần tự kiểm tra xem hiểu đúng chưa và biết nên ưu tiên ôn phần nào trước khi hết thời gian. Mức độ quen dùng AI không cao, cần giao diện đơn giản, không đòi hỏi biết viết prompt.

**Câu định vị:** *"Tôi vừa đọc xong một chương giáo trình dài, tôi muốn hỏi lại một chỗ chưa chắc và nhận được câu trả lời kèm đúng đoạn trong tài liệu - thay vì hỏi một chatbot chung chung không biết gì về tài liệu của tôi."*

**Phạm vi người dùng của MVP:** chỉ phục vụ một người dùng cho mỗi lần chạy (không có đăng nhập/phân quyền nhiều người trong MVP - xem F11 ở mục 4). Nếu mở rộng sau này cho nhiều người dùng chung, cần thêm vai trò kiểu "quản trị" để duyệt nội dung trước khi dùng chung - nhưng việc đó ngoài phạm vi đồ án hiện tại vì mục tiêu là một app tự học cá nhân, không phải kho tri thức dùng chung.

## 3. Input

| Chiều input | Phạm vi dự kiến |
| --- | --- |
| Loại file | PDF và DOCX |
| Kích thước | dự kiến giới hạn khoảng 30 MB/file - cần thử với vài file thật để biết ngưỡng hợp lý trước khi chốt cứng |
| Ngôn ngữ | tài liệu chủ yếu tiếng Việt và tiếng Anh (giáo trình kỹ thuật hay có thuật ngữ Anh xen tiếng Việt); câu trả lời nên theo đúng ngôn ngữ của câu hỏi |
| Cách trích xuất | PDF theo trang, DOCX theo nhóm đoạn văn (DOCX không có khái niệm trang cố định) - cần giữ lại vị trí nguồn để trích dẫn kiểm tra lại được |
| Chất lượng | chỉ nhận tài liệu có lớp text trích được; OCR cho file scan để ở nhóm Could (F10), không làm ngay vì tốn thời gian mà chưa chắc cần thiết cho phần lớn tài liệu học tập |
| Phiên bản | có thể upload lại tài liệu đã có (ví dụ giáo trình bản chỉnh sửa) - giữ cả bản cũ lẫn bản mới, hỏi đáp chỉ dùng bản mới nhất, xem F1 ở mục 5 |
| Người dùng | một người dùng/phiên làm việc trong MVP, chưa có đăng nhập thật |

## 4. Scope & priority

So với bản đầu, một số hạng mục từng ở nhóm Could (cá nhân hoá sâu, ôn tập có lịch) đã được quyết định đưa vào Must vì đây chính là phần giải quyết trực tiếp pain point "lập lịch ôn trước deadline" và "biết chủ đề nào đang yếu" ở mục 1 — không đạt được 2 pain point đó thì sản phẩm chỉ còn là một chatbot hỏi đáp tài liệu, không phải trợ lý học tập cá nhân hoá như tên gọi.

| Priority | Feature | Giá trị |
| --- | --- | --- |
| **Must** | F1 - Quản lý tài liệu học tập (upload, xử lý nền, xoá, versioning, gộp theo môn học) | có nguồn tài liệu đáng tin, biết đang xử lý hay lỗi, không nạp trùng tài liệu đổi tên |
| **Must** | F2 - Hỏi đáp RAG có trích dẫn nguồn, gồm 3 dạng câu hỏi sinh nội dung riêng (tóm tắt 1 chủ đề, so sánh 2 khái niệm, áp dụng khái niệm vào ví dụ mới) | trả lời có căn cứ, mở được đúng đoạn trong tài liệu, phục vụ được cả câu hỏi lấy thông tin lẫn câu hỏi cần tổng hợp/vận dụng |
| **Must** | F3 - Guardrail an toàn cho câu hỏi | chặn injection/jailbreak và yêu cầu làm bài hộ trước khi trả lời |
| **Must** | F4 - Sinh quiz trắc nghiệm để tự kiểm tra + chấm bài | có đề ôn tập từ đúng tài liệu, biết đúng/sai ngay |
| **Must** | F5 - Theo dõi mastery theo chủ đề + phát hiện hiểu sai lặp lại | biết mình đang mạnh/yếu chủ đề nào, và đang nhầm lẫn cụ thể điều gì chứ không chỉ "hay sai" |
| **Must** | F6 - Sinh flashcard để ôn nhanh + lịch ôn tập ngắt quãng (spaced repetition) | ôn thuật ngữ/khái niệm nhanh hơn đọc lại tài liệu, và được nhắc đúng lúc trước khi quên thay vì tự nhớ lịch ôn |
| **Must** | F7 - Gợi ý học tiếp theo + kế hoạch ôn tập theo ngày thi từng môn học | biết ưu tiên ôn gì và chia thời gian thế nào khi học song song nhiều môn có deadline khác nhau |
| **Must** | F8 - Cá nhân hoá theo trình độ, gộp từ hồ sơ tự khai, mức thành thạo hiện có, và các sự kiện học tập gần đây | không phải khai báo trình độ mỗi lần hỏi, và hệ thống nhắc lại đúng chỗ mình hay nhầm thay vì hỏi chung chung |
| **Should** | F9 - Nhớ ngữ cảnh học tập đầy đủ hơn xuyên nhiều phiên làm việc (vượt quá các sự kiện rời rạc F8 đang ghi lại) | hỏi tiếp sau nhiều ngày không phải nhắc lại toàn bộ bối cảnh đang học |
| **Could** | F10 - OCR cho tài liệu scan | nhận thêm được tài liệu dạng ảnh/scan |
| **Could** | F11 - Đăng nhập/đa người dùng thật | dùng được cho nhiều người, không chỉ một người/phiên |
| **Won't** | Chấm điểm chính thức thay giáo viên, kết nối LMS, tìm Internet trực tiếp, gợi ý theo prerequisite (cần đồ thị phụ thuộc giữa chủ đề, chưa có nguồn dữ liệu này) | giữ phạm vi trong một app tự học cá nhân dựa trên tài liệu tự tải lên |

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
- Có một bước xác minh lại câu trả lời trước khi trả về người dùng, xác minh THEO TỪNG PHẦN của câu trả lời chứ không phải cả khối - nếu chỉ một phần qua được xác minh, trả đúng phần đó kèm dấu hiệu rõ ràng là câu trả lời chưa đầy đủ, thay vì từ chối toàn bộ hoặc giữ nguyên phần chưa xác minh được.
- Hiểu được câu hỏi tiếp nối trong cùng phiên hỏi đáp (ví dụ dùng đại từ nhắc lại ý trước) mà không cần người dùng lặp lại ngữ cảnh; khi đại từ không xác định được đang nhắc tới gì (không có lượt hỏi trước liên quan), hệ thống hỏi lại thay vì tự đoán một đối tượng bất kỳ rồi trả lời tự tin sai chủ đề.
- Có tham số chọn trình độ (beginner/advanced) để đổi độ sâu câu trả lời, ưu tiên theo thứ tự: người dùng chọn tường minh ở lượt hỏi này > trình độ đã lưu trong hồ sơ > suy ra từ mức thành thạo trung bình hiện có nếu chưa từng khai báo.
- Người dùng hỏi tóm tắt một chương/chủ đề thì nhận được nội dung phủ TRỌN chủ đề đó (không chỉ vài đoạn liên quan nhất) kèm trích dẫn, xác định đúng chủ đề đang hỏi kể cả khi gọi tên khác với tiêu đề gốc trong tài liệu.
- Người dùng hỏi so sánh 2 khái niệm thì cả 2 vế đều được tìm kiếm đầy đủ trong tài liệu, không để vế có ít nội dung hơn trong corpus bị lép vế so với vế còn lại.
- Người dùng hỏi kiểu "cho tôi một ví dụ áp dụng khái niệm X" thì nhận được một ví dụ/tình huống cụ thể minh hoạ khái niệm, không chỉ nhắc lại định nghĩa.

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

### F5 - Theo dõi mastery theo chủ đề + phát hiện hiểu sai lặp lại (Must)

**Pain point giải quyết:** không nhớ nổi chủ đề nào mình đang yếu nếu không ghi chép lại kết quả tự kiểm tra; biết mình "hay sai" một chủ đề nhưng không biết cụ thể đang nhầm điều gì.

**User stories**

1. Là người học, tôi muốn thấy điểm mastery theo từng chủ đề để biết nên ôn gì.
2. Là người học, tôi muốn điểm này phản ánh đúng tình trạng gần đây, không bị kéo lệch bởi những lần làm bài rất lâu trước.
3. Là người học, khi được gợi ý học tiếp theo, tôi muốn biết cụ thể mình đang nhầm lẫn điều gì ở chủ đề yếu, không chỉ một con số.

**AC**

- Mỗi lần làm xong một câu quiz, điểm mastery của chủ đề liên quan được cập nhật ngay; công thức có tính đến thời gian (lượt làm bài gần đây ảnh hưởng nhiều hơn lượt cũ) và độ khó câu hỏi (đúng câu khó/sai câu dễ là bằng chứng mạnh hơn đúng câu dễ/sai câu khó).
- Điểm mastery tiếp tục giảm nhẹ theo thời gian không luyện tập một chủ đề, để phản ánh đúng "có thể đã quên" chứ không giữ nguyên vô thời hạn.
- Khi người học lặp lại cùng một lựa chọn sai ở cùng một chủ đề từ 2 lần trở lên, hệ thống nêu rõ cụ thể đang nhầm lẫn gì (không chỉ nói "hay sai chủ đề X") ở màn hình gợi ý học tiếp theo.
- Có màn hình tổng quan xem điểm mastery theo từng chủ đề, cùng vài số liệu cơ bản (số tài liệu, số quiz đã làm, tỉ lệ đúng, câu đã trả lời sai gần đây).

### F6 - Sinh flashcard + ôn tập ngắt quãng (Must)

**Pain point giải quyết:** ôn xong một lần rồi quên vì không có lịch nhắc ôn lại đúng lúc trước khi quên.

**User stories**

1. Là người học, tôi muốn tạo flashcard từ tài liệu để ôn nhanh khái niệm/thuật ngữ.
2. Là người học, tôi muốn hệ thống tự tính khi nào nên ôn lại một thẻ, dựa trên việc tôi thấy thẻ đó dễ hay khó ở lần ôn trước, thay vì tự nhớ lịch.

**AC**

- Sinh được flashcard (mặt trước/mặt sau) từ nội dung tài liệu đã chọn, dùng lại kỹ thuật xác minh nội dung giống F4; cũng lưu được trực tiếp một câu trả lời hỏi đáp thành flashcard.
- Mỗi thẻ gắn nguồn (tài liệu + vị trí) để kiểm chứng lại được.
- Sau mỗi lần đánh giá một thẻ (theo 4 mức, kiểu Anki), hệ thống tính lại ngày nên ôn thẻ đó tiếp theo - đánh giá "khó/quên" thì được nhắc ôn sớm hơn, "dễ" thì giãn ra xa hơn.
- Có màn hình xem thẻ nào đang đến hạn, đang học, hay đã thuộc.

### F7 - Gợi ý học tiếp theo và lập kế hoạch ôn tập theo ngày thi từng môn (Must)

**AC**

- Hỏi kiểu "tôi nên học gì tiếp theo" được nhận diện và trả lời dựa trên dữ liệu mastery đã có, ưu tiên chủ đề điểm thấp nhất - không cần tốn một lượt gọi LLM cho việc này vì chỉ là đọc lại dữ liệu đã tính.
- Người học khai báo ngày thi cho từng môn học; hệ thống chia lịch ôn tập ưu tiên chủ đề yếu/chưa học lên trước, tính theo TỪNG môn khi học song song nhiều môn có deadline khác nhau.
- Mỗi chủ đề trong kế hoạch kèm một hành động đề xuất cụ thể (nên làm quiz để kiểm tra lại hiểu bài, nên ôn flashcard vì có nguy cơ quên, hay nên học lại từ đầu) và lý do ngắn gọn, không chỉ liệt kê tên chủ đề.
- Kế hoạch tự cập nhật theo tiến độ mới nhất mỗi lần hỏi lại, không cần đồng bộ trạng thái kế hoạch cũ; người học có thể đánh dấu thủ công một chủ đề "đã ôn hôm nay".

### F8 - Cá nhân hoá theo trình độ (Must)

**Pain point giải quyết:** phải khai báo lại trình độ/bối cảnh mỗi lần hỏi; hệ thống không nhớ những gì vừa xảy ra trong phiên học gần đây để đưa vào câu trả lời tiếp theo.

**AC**

- Trình độ hiệu lực dùng chung giữa hỏi đáp và sinh quiz/flashcard, ưu tiên: người học chọn tường minh ở lượt này > đã lưu trong hồ sơ > suy ra từ mức thành thạo trung bình hiện có (yếu → sơ cấp, tốt → nâng cao) nếu chưa từng khai báo.
- Người học khai báo được một mục tiêu học tập dạng tự do (ví dụ "chuẩn bị phỏng vấn ML"); nội dung này được lọc chống chèn lệnh (prompt injection) ngay khi lưu, vì sẽ được đưa lại vào ngữ cảnh trả lời ở các lượt sau.
- Các sự kiện học tập đáng chú ý gần đây (bị từ chối trả lời vì thiếu căn cứ, trả lời sai quiz, quên một flashcard...) được ghi lại và có thể được nhắc lại đúng lúc liên quan đến câu hỏi hiện tại, xuyên suốt mọi cuộc hội thoại chứ không chỉ trong đúng 1 phiên hỏi đáp.
- Việc cá nhân hoá không được làm giảm độ chính xác của câu trả lời - nội dung cá nhân hoá chỉ đóng vai trò bối cảnh tham khảo, không được dùng thay cho căn cứ trích dẫn từ tài liệu.

### F9 - Nhớ ngữ cảnh học tập xuyên phiên đầy đủ hơn (Should)

**AC**

- Ngoài các sự kiện rời rạc ở F8, hệ thống cần nhớ được bối cảnh liên tục hơn của một chủ đề đang học qua nhiều ngày (ví dụ: đang ở giai đoạn nào của một chương, đã hỏi những khía cạnh nào rồi) để không phải mở lại toàn bộ lịch sử hội thoại cũ mỗi lần quay lại.
- Chưa cần đạt mức "trợ lý nhớ mọi chi tiết" - ưu tiên đúng những gì ảnh hưởng trực tiếp tới câu trả lời/gợi ý tiếp theo.

### F10-F11 - Các hạng mục Could

- **F10 OCR:** nhận thêm tài liệu dạng scan, mỗi đoạn trích từ OCR cần đánh dấu độ tin cậy vì kém chính xác hơn text gốc.
- **F11 Đăng nhập/đa người dùng:** mở app dùng được cho nhiều người, mỗi người có dữ liệu và tài liệu riêng; cần thêm xác thực session/token thay vì tin thẳng định danh do client tự gửi.

## 6. Non-functional requirements

- **An toàn nội dung:** guardrail (F3) là lớp chặn trước khi vào bước sinh câu trả lời; bước xác minh theo từng câu (F2) là lớp chặn thứ hai chống bịa, và trả về đúng phần đã xác minh được thay vì cả câu trả lời một khối. Không có bước nào để lộ câu trả lời chưa qua xác minh.
- **Ranh giới dữ liệu:** mọi bước truy hồi và mọi bước đọc/ghi dữ liệu cá nhân hoá (mastery, hồ sơ, sự kiện học tập) đều lọc theo đúng người dùng ngay trong câu truy vấn, không phải lọc kết quả sau khi đã lấy hết - đây là điều kiện tiên quyết trước khi có thể mở rộng sang nhiều người dùng thật (F11).
- **Hiệu năng:** chưa cam kết p95 cụ thể - đo baseline thật trước khi chốt ngưỡng cho từng loại thao tác (hỏi đáp gọi LLM khác hẳn về độ trễ so với đọc dashboard mastery).
- **Chi phí:** ưu tiên xử lý rule-based/đọc dữ liệu đã tính sẵn (guardrail 2 tầng đầu, capability detection, đọc mastery) trước khi chạm tới bước gọi mô hình trả phí (LLM, embedding, rerank) - chỉ gọi mô hình đúng lúc thật sự cần sinh/xác minh/biểu diễn nội dung ngôn ngữ.
- **Khả năng triển khai (stateless):** container backend không được giữ trạng thái nào trên đĩa cục bộ (không SQLite/FAISS/file tạm) - toàn bộ dữ liệu bền vững phải nằm ở dịch vụ ngoài container, để deploy được lên host free tier không có persistent disk và container có thể khởi động lại bất cứ lúc nào mà không mất dữ liệu người dùng.
- **Truy hồi:** kết hợp tìm theo ngữ nghĩa và tìm theo từ khoá thay vì chỉ dùng một loại, vì tài liệu học thuật có nhiều thuật ngữ/ký hiệu chính xác mà tìm ngữ nghĩa một mình dễ bỏ sót.
- **Đánh giá:** dùng bộ câu hỏi chuẩn tự soạn (Golden Set, `eval/`) để đo trước khi coi một tính năng là "xong", không chỉ test bằng cảm tính vài câu hỏi ngẫu nhiên; số liệu đo được cập nhật trong `eval/`, không lưu cố định trong PRD vì thay đổi theo mỗi lần chạy lại.
- **Khả dụng:** lỗi upload/xử lý tài liệu luôn có trạng thái và lý do rõ ràng hiển thị được, không để người dùng đoán mò tại sao không chạy.

## 7. Definition of Done

MVP coi là xong khi hoàn thành được hành trình: tải tài liệu lên -> đợi trạng thái sẵn sàng -> hỏi đáp (kể cả tóm tắt/so sánh/áp dụng) và mở được nguồn trích dẫn -> làm một quiz và thấy điểm mastery cập nhật -> ôn một flashcard và thấy lịch ôn tiếp theo được tính lại -> khai báo ngày thi một môn và xem được kế hoạch ôn tập kèm hành động đề xuất theo từng chủ đề. Toàn bộ Must (F1-F8) đạt AC ở mục 5, và được đo bằng bộ câu hỏi chuẩn (Golden Set) trước khi coi là hoàn thành - không chỉ dựa vào cảm tính.

Ba điều kiện chặn riêng, không đánh đổi kể cả khi áp dụng kịch bản hạ cấp:

- **0 trường hợp** câu trả lời khẳng định nghiệp vụ mà không có trích dẫn nguồn.
- **0 trường hợp** lọt qua được các mẫu injection/jailbreak rõ ràng đã liệt kê khi thiết kế guardrail.
- **100%** câu hỏi yêu cầu làm bài hộ rõ ràng bị chặn, không trả lời một phần nào của yêu cầu đó.


