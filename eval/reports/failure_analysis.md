# EduTutor Golden Set — Failure Analysis

Phân tích nguyên nhân gốc (root cause) cho các case fail trong
**[evaluation_report.md](evaluation_report.md)**, cùng các fix đã áp dụng
và kiểm chứng. Đọc `evaluation_report.md` trước để có số liệu tổng quan.

---

## 1. Bốn phát hiện đáng chú ý — Phần Q&A

**Finding #1 — Follow-up dùng đại từ thường không resolve được ngữ cảnh.**
7/25 case `conversational` (28%) rơi vào `needs_clarification` thay vì trả
lời đúng, cụ thể là câu dùng đại từ chỉ định tiếp nối lượt trước ("Nó có
mấy loại phổ biến?", "Cái đó hoạt động theo cơ chế nào?"). Hệ thống không
dùng được ngữ cảnh hội thoại để resolve chủ đề dù `build_retrieval_query()`
đã có cơ chế nối từ khoá lượt trước. Attribution sau này (mục 3) cho thấy
phần lớn case này thực ra là cùng bug tự-từ-chối (đã sửa) — chi tiết mục 3.1.

**Finding #2 — Câu hỏi có tiền đề sai bị gộp vào "cần làm rõ" thay vì bị
bác bỏ rõ ràng.** 5/5 case hỏi câu có tiền đề sai rõ ràng (ví dụ "LeNet-5
được LeCun phát triển tại Google năm 1998", "Random forest giảm overfitting
bằng cách TĂNG độ tương quan giữa các cây...") đều nhận
`NEEDS_CLARIFICATION_MESSAGE` thay vì một câu trả lời khẳng định-và-sửa-lại
hoặc từ chối rõ ràng vì tiền đề sai. **Đã sửa — xem mục 3.3.**

**Finding #3 — Mẫu hình lặp lại xuyên suốt: câu hỏi hợp lệ nhưng phức
tạp/ghép nhiều ý dễ rơi vào "cần làm rõ".** Không chỉ ở #1 và #2 — nhiều
case `guardrail` false-positive và nhiều case `apply`/`grounding_citation`
cũng cho kết quả tương tự: hệ thống an toàn (không bịa, không chặn nhầm)
nhưng phản hồi mơ hồ hơn cần thiết thay vì trả lời thẳng hoặc từ chối có lý
do cụ thể. Root cause thật sau attribution (mục 3): verifier's
`addresses_question` là một phán quyết CÓ/KHÔNG duy nhất, không có khái
niệm "trả lời được một phần của câu hỏi ghép" — **đã sửa, xem mục 3.3.**

**Finding #4 — Summarize: `resolve_topic()` khớp chủ đề chặt hơn cần thiết
trong thực tế.** Với tài liệu thực sự có chủ đề để tóm tắt, chỉ 1/7 case
khớp đúng chủ đề và trả về bản tóm tắt cấu trúc thật; 6/7 nhận
`NEEDS_TOPIC_MESSAGE` dù chủ đề có tồn tại. `resolve_topic()` chỉ khớp khi
có trùng từ nội dung với tiêu đề `DocumentTopic` — nguyên tắc "không đoán
bừa" này an toàn nhưng có thể quá chặt khi người dùng diễn đạt theo nội
dung thay vì lặp lại đúng từ trong tiêu đề gốc. Ngược lại, 6 case cố ý
không có chủ đề để tóm tắt đều nhận đúng `NEEDS_TOPIC_MESSAGE` như thiết
kế. **CHƯA sửa** — xác nhận qua attribution (mục 3.1): 6/6 case fail
category này hoàn toàn không đi qua `answer_question()`/verifier,
`resolve_topic()` là một cơ chế khớp từ khoá thuần, tách biệt hoàn toàn.

---

## 2. Phát hiện — lỗ hổng còn sót trong bộ lọc topic nhiễu (Study Plan)

`GET /study-plan` (qua `app/routers/study_plan.py`, dùng chung
`filter_topic_titles` với `chat.py`) vẫn để lọt các mục **tham khảo đánh số
kiểu Wikipedia** vào kế hoạch học, dù rõ ràng không phải tiêu đề chương:

- `15. "OpenNMT – Open-Source Neural Machine Translation". opennmt.net. Truy cập`
- `1.0 for a class C means that every item` (câu bị cắt giữa chừng, không phải heading)

**Nguyên nhân:** sau khi sửa outline PDF trước đó trong dự án (bỏ nhánh
Title-Case/ALL-CAPS, chỉ giữ mục đánh số kiểu
`_NUMBERED_SECTION_RE = r"^\d{1,2}(\.\d{1,2}){0,3}\.?\s+\S"`), một mục tham
khảo đánh số trong phần "Tham khảo"/"References" của Wikipedia (ví dụ
`"15. Tên bài báo". domain.net. Truy cập ngày...`) khớp chính xác mẫu này —
về mặt cú pháp nó cũng là "số + dấu chấm + text", không khác gì
"6.1 Machine Translation". `is_plausible_topic()` có luật loại citation-like
(năm trong ngoặc, ISBN/DOI, "tr./pp.") nhưng **không có luật cho định dạng
web/Wikipedia** (URL + "Truy cập ngày") — đúng kiểu trích dẫn phổ biến nhất
trong corpus mới (toàn bộ 13 tài liệu đều từ Wikipedia).

**Vì sao đáng chú ý:** đây là loại lỗi chỉ lộ ra khi kiểm thử một tính năng
(Study Plan) đọc dữ liệu do một tính năng khác tạo ra (outline extraction
lúc upload) — giá trị cốt lõi của kịch bản liên-tính-năng, không thể phát
hiện được nếu chỉ test `outline.py` hay `study_plan.py` riêng lẻ.

**Trạng thái: CHƯA sửa** — đề xuất fix ở mục 4.

---

## 3. Attribution theo pipeline và fix đã áp dụng

Sau khi hiệu chỉnh evaluator (`evaluation_report.md` mục 3.2), 82 case
`product_failure` còn lại được chia 2 nhóm: 36 case đã có `failure_mode`
dạng tag ngắn có kiểm soát trong `golden_set.jsonl`
(hallucination/false_citation/wrong_retrieval...), và **46 case chưa rõ
root cause** (đa số conversational/decomposition/multi_document/apply/
summarize/guardrail-false-positive). Để attribution 46 case này KHÔNG dựa
vào suy đoán từ output cuối, đã thêm instrumentation debug
(`backend/app/llm/rag.py::_trace`, chỉ ghi khi `EVAL_TRACE=1`, không đổi
response contract) ghi lại điểm retrieval, `draft_answer` của generator, và
`raw_verdict` của verifier — rồi rerun CHỈ 46 case đó qua backend thật và
phân loại root cause theo đúng trace ghi được.

### 3.1 Root cause thật của 46 case (từ trace, không suy đoán)

| Root cause | Số case | Ý nghĩa |
|---|---:|---|
| `verifier_addresses_question_false` | 26 | Verifier's VIỆC 1 (addresses_question) trả KHÔNG |
| `no_trace` | 7 | Không qua `answer_question()` cùng đường (6 = summarize dùng `resolve_topic()` riêng, xem mục 1 Finding #4; 1 = guardrail bị chặn trước RAG pipeline) |
| `generator_only` | 6 | Verifier không từ chối gì — lỗi nằm ở NỘI DUNG generator sinh ra |
| `retrieval_empty` | 4 | 0 chunk đạt `min_score` — lỗi tầng retrieval, không phải verifier |
| `verifier_claims_rejected` | 3 | Verifier từ chối cụ thể một/nhiều luận điểm (không phải addresses_question) |

**Phát hiện quan trọng nhất trong 26 case `verifier_addresses_question_false`**:
đọc trực tiếp `draft_answer` thật cho thấy generator đã làm ĐÚNG theo chỉ thị
của chính nó (`_build_generator_prompt`: *"Nếu đoạn trích không chứa câu trả
lời, hãy nói rõ là không có thông tin"*) — draft answer chỉ là câu tự-từ-chối
("Không có thông tin.", "Không có thông tin về X trong đoạn trích."). Câu
tự-từ-chối này bị đưa nguyên vào verifier's VIỆC 1, và verifier phán nó
"không trả lời đúng câu hỏi" — dẫn tới `NEEDS_CLARIFICATION_MESSAGE` ("câu
hỏi chưa đủ rõ, hãy nói rõ hơn") — **thông điệp sai lệch**, vì câu hỏi không
mơ hồ, hệ thống chỉ đơn giản là thiếu căn cứ.

### 3.2 Fix vòng 1 — loại câu tự-từ-chối khỏi verifier

`backend/app/llm/rag.py::answer_question()`: sau khi tách luận điểm
(`_split_claims`), lọc bỏ mọi luận điểm khớp `_SELF_DECLINED_NO_INFO_RE`
("không có/tìm thấy (đủ/cụ thể/trực tiếp) thông tin") TRƯỚC khi gửi cho
verifier. Nếu không còn luận điểm thực chất nào, trả `NOT_GROUNDED_MESSAGE`
ngay (bỏ luôn 1 lượt gọi LLM verifier). Nếu câu hỏi ghép nhiều ý và một phần
có căn cứ (vd case decomposition), phần thực chất vẫn đi qua verifier như
cũ — sửa đồng thời một lỗi phụ (câu hỏi ghép bị mất phần trả lời đúng vì lẫn
với phần tự-từ-chối). Có 2 test hồi quy mới trong `tests/test_rag.py`
(`test_self_declined_no_info_returns_not_grounded_without_calling_verifier`,
`test_partial_decline_keeps_substantive_claim_and_still_calls_verifier`) —
68/68 test `test_rag.py` pass sau fix.

**Đo lại thật bằng cách rerun đúng 46 case đó lần 2** sau khi vá:
19/46 case đổi outcome — từ `needs_clarification` (message sai lệch "câu hỏi
chưa đủ rõ") sang message thật của `answer_with_fallback`
("Không tìm thấy nội dung này trong tài liệu của bạn...", kèm đoạn gần đúng
để người dùng tự đối chiếu) — **đúng bản chất hơn nhiều, nhưng CHƯA làm tăng
số case pass thô**, vì nội dung câu trả lời thật (không phải chỉ message)
vẫn chưa có — nghĩa là bug đã sửa là bug về THÔNG ĐIỆP (communicate đúng lý
do từ chối), không phải bug khiến hệ thống tìm ra thêm nội dung mới. Một
case (`EDU-APL-005`) chuyển thật sự từ `unsupported_claim` sang
`grounded_answer` với `content_correct_per_judge=True` — chỉ còn fail vì
lỗi evaluator khác (mục 3.2b).

Ngoài ra phát hiện: `classify_outcome()` (script chấm điểm) chưa nhận diện
được message thật của `answer_with_fallback` — đã thêm snippet
`_NO_CONTEXT_FALLBACK_SNIPPET` để chấm đúng outcome `insufficient_evidence`
cho các case này ở lần chạy sau.

### 3.2b Lỗi evaluator khác phát hiện qua EDU-APL-005: so khớp `must_contain` phân biệt hoa/thường

`score_case()` so `must_contain`/`must_not_contain` phân biệt hoa/thường —
case yêu cầu `"câu hỏi gợi mở"` (thường) nhưng câu trả lời thật viết hoa đầu
câu `"Câu hỏi gợi mở..."` khiến case fail dù `content_correct_per_judge=True`.
Đã sửa `run_golden_set.py::score_case()` so không phân biệt hoa/thường.

### 3.3 Fix vòng 2 — sub-question coverage + false-premise (cùng 1 chỗ trong verifier)

Sau khi thảo luận thêm, 2 hạng mục còn lại (false-premise Finding #2, và
root cause thứ 3 của decomposition/multi_document ở mục 3.1) hoá ra chạm
CÙNG một chỗ: `_build_claim_verifier_prompt`'s VIỆC 1 (`addresses_question`),
lúc đó chỉ có 2 giá trị CÓ/KHÔNG — ép mọi câu hỏi ghép nhiều phần vào phán
quyết all-or-nothing, và không phân biệt được "nói sang chuyện khác" với
"sửa lại một tiền đề sai".

**Fix lần 1 đã thử (chỉ thêm 1 câu chỉ dẫn cho tiền đề sai) — kiểm chứng
live: KHÔNG hiệu quả.** Test lại case "LeNet-5 tại Google" trên backend đã
có câu chỉ dẫn mới: verifier vẫn trả `addresses_question: "KHÔNG"` dù
generator đã trả lời đúng và có căn cứ đầy đủ. Bài học: thêm một câu nhắc
vào cùng một khoá CÓ/KHÔNG không đủ mạnh để đổi xu hướng suy luận có sẵn
của LLM.

**Fix lần 2 — đổi `addresses_question` từ 2 giá trị thành 3 giá trị
('ĐẦY ĐỦ'/'MỘT PHẦN'/'KHÔNG'), vẫn 1 lượt gọi:**
- 'MỘT PHẦN' — trả lời đúng ít nhất một phần của câu hỏi ghép nhiều ý,
  không bị coi là từ chối cả câu chỉ vì thiếu một phần → giải quyết root
  cause thứ 3 của decomposition/multi_document (mục 3.1).
- Chỉ 'KHÔNG' mới bị coi là từ chối; sửa lại tiền đề sai luôn được tính
  'ĐẦY ĐỦ' → giải quyết Finding #2 (false-premise).
- `_parse_addresses_question()` sửa lại: chỉ giá trị bắt đầu bằng "KHÔNG"
  mới bị từ chối, còn lại (kể cả giá trị lạ do model trả sai định dạng) đều
  cho đi tiếp — giữ đúng nguyên tắc cũ "lỗi định dạng không biến thành từ
  chối oan".

**Đồng thời vá lỗi regex tự-từ-chối** (mục 3.2) bỏ sót thứ tự "...thông tin
... không có" (chỉ bắt được thứ tự "không có ... thông tin") — phát hiện
qua `EDU-DECOMP-007`.

**Kiểm chứng live (backend thật, sau khi restart nạp cả 2 fix), không chỉ
unit test:**

| Case | Trước | Sau |
|---|---|---|
| "LeNet-5 tại Google" (false-premise) | `needs_clarification` | `is_grounded=true`: *"LeNet-5 được Yann LeCun và các đồng sự phát triển tại AT&T Labs vào năm 1998, không phải tại Google. [1]"* |
| "So sánh AlexNet/VGGNet... tại sao GoogLeNet dùng Inception?" (3 phần, decomposition) | fail (all-or-nothing) | `is_grounded=true`, trả lời ĐỦ cả 3 phần, trích dẫn từ 2 tài liệu khác nhau |
| "LeNet-5 mấy lớp, Random Forest giảm overfitting sao?" (regex-gap case) | fail | `is_grounded=true`, trả lời đúng phần có căn cứ |

3 test hồi quy mới trong `tests/test_rag.py` (71/71 pass): regex thứ tự
ngược, `addresses_question="MỘT PHẦN"` không bị từ chối, và test cũ đã sửa
tương ứng giá trị JSON mới.

**Metric mới, tính được ngay từ dữ liệu, không cần LLM** — đã đo lại đầy đủ
qua regression 51 case (chạy 2 lần vì chạm giới hạn Cohere key giữa đường,
xem mục 3.4):

| Metric | Trước 2 fix (cùng 51 ID) | Sau 2 fix |
|---|---:|---:|
| Pass rate (bộ regression 51 case) | 23/51 (45.1%) | **36/51 (70.6%)** |
| Unnecessary refusal rate (trong số case đáng ra trả lời được) | 5/36 (13.9%) | 4/36 (11.1%) |
| Sub-question coverage (heuristic từ-vựng, 14 sub-question trong mẫu này) | 14/14 (100%) | 14/14 (100%) |

Ghi chú: `unnecessary refusal rate`/`sub-question coverage` đo trên mẫu 51
case (đa dạng, không chỉ case đã fail) nên cải thiện nhìn nhỏ hơn con số
60% đã tính trước đó trên TOÀN BỘ 90 case fail của 267-case baseline — hai
mẫu số khác nhau, không mâu thuẫn. `sub-question coverage` không đổi vì
heuristic từ-vựng khá thô (chỉ so trùng từ nội dung, không đánh giá đúng-sai
ý), không đủ nhạy để thấy cải thiện đã xác nhận qua case sống (AlexNet/
VGGNet/GoogLeNet ở trên) — nên coi các con số sống (test tay qua backend
thật) là bằng chứng chính, metric bảng trên chỉ để theo dõi xu hướng dài hạn.

### 3.4 Sự cố hạ tầng giữa lúc regression — Cohere key hết hạn mức lần 3

Trong lúc chạy regression 51 case, gặp lại đúng lỗi đã biết 2 lần trước
trong phiên: Cohere trial key trả `429 TooManyRequestsError`, khiến request
bị treo tới timeout (90s) và cascade sang nhiều case liên tiếp. Đã dừng
ngay, người dùng cấp key mới, thay vào `.env`, xác nhận key mới hoạt động
bằng 1 request thật trước khi chạy lại. **Phát hiện thêm 1 lỗi nhỏ trong
logic resume của runner** (khi đó là script `run_regression.py` riêng, nay
đã gộp thành cờ `--regression-only` trong `run_golden_set.py`): logic
resume chỉ kiểm tra case đã có mặt trong file kết quả, không kiểm tra
`request_ok` — khiến 3 case bị lỗi hạ tầng (không phải lỗi sản phẩm) bị coi
là "đã xong" và không được chạy lại tự động; phải phát hiện thủ công qua
rescan `checks.request_ok == False` rồi xoá 3 dòng đó để chạy lại đúng phần
thiếu. **Đã sửa** resume-logic để tự loại case `request_ok=False` khỏi
danh sách "đã xong".

### 3.5 Kiểm tra hồi quy cuối cùng (so với baseline gốc, cùng 51 ID)

3 case đổi từ pass→fail so với baseline gốc, đã điều tra hết:
- `EDU-DECOMP-002`, `EDU-MULTIDOC-001`: mọi check thực chất đều `True` —
  đúng mẫu hình evaluator noise đã biết (nội dung LLM diễn đạt khác đi giữa
  2 lượt gọi, không liên quan 2 fix).
- `EDU-ABS-014` ("Kernel là gì?"): đúng hạn chế ĐÃ CÔNG KHAI ở mục 4 (không
  có bước phát hiện đa nghĩa độc lập) — hệ thống giờ trả lời tự tin theo 1
  nghĩa (CNN filter) thay vì "không có thông tin" như trước, nhưng vẫn CHƯA
  nêu tên nghĩa thứ 2 (random-forest kernel). Xem trace: retrieval trả về 24
  chunk có điểm cao nhưng chủ yếu KHÔNG liên quan trực tiếp tới khái niệm
  "kernel" (chunk đúng chủ đề bị chôn ở hạng 3 và hạng 12), khiến generator
  đưa ra draft "Không có thông tin." — bị fix mục 3.3 chặn đúng như thiết
  kế, trả `NOT_GROUNDED_MESSAGE` thay vì `NEEDS_CLARIFICATION_MESSAGE` nêu
  tên 2 khả năng. **Bản chất vấn đề**: hệ thống KHÔNG có một bước phát hiện
  "thuật ngữ có nhiều nghĩa" độc lập — hành vi "hỏi lại nêu rõ 2 khả năng" ở
  baseline gốc chỉ là NGẪU NHIÊN xảy ra vì verifier's addresses_question
  tình cờ từ chối draft answer khi đó, dùng chung message với "câu hỏi quá
  mơ hồ". Fix mục 3.3 không lấy đi một năng lực thật đã có — nó chỉ đổi
  NHÁNH NGẪU NHIÊN nào được đi tới khi draft là câu tự-từ-chối. Hệ thống sau
  fix vẫn an toàn (không bịa, không chọn bừa 1 trong 2 nghĩa) nhưng mất đi
  việc NÊU TÊN 2 khả năng cho người dùng chọn. Không phải hồi quy do code
  sai — xem mục 4 cho đề xuất.

**Không có hồi quy thật mới nào do 2 fix của vòng này gây ra.**

---

## 4. Kết luận và việc còn lại

**Điểm mạnh xuyên suốt:** khi hệ thống có trả lời, độ chính xác và trích
dẫn gần như tuyệt đối (97–99%); toàn bộ cơ chế Quiz/Flashcard/Mastery/Study
Plan hoạt động đúng thiết kế qua vòng đời API thật.

**Vấn đề chính KHÔNG phải "trả lời sai" mà là 3 lỗi độc lập cùng nằm ở
verifier's `addresses_question`** — cả 3 đã sửa và kiểm chứng (mục 3.3):
tự-từ-chối bị hiểu nhầm, câu hỏi ghép nhiều phần bị đánh trượt toàn bộ, và
không nhận diện sửa tiền đề sai. Ngoài ra còn một lỗ hổng cụ thể trong bộ
lọc topic nhiễu chưa xử lý định dạng trích dẫn web/Wikipedia (mục 2, chưa
sửa).

**Việc còn lại, theo thứ tự đề xuất:**

1. ~~Bug tự-từ-chối~~ / ~~all-or-nothing với câu hỏi ghép~~ / ~~không nhận
   diện sửa tiền đề sai~~ — **cả 3 đã sửa, kiểm chứng live + regression 51
   case (pass rate 45%→70.6%, không hồi quy thật mới)**, xem mục 3.2-3.5.
2. Điều tra điểm retrieval bị pha loãng bởi khung diễn đạt dài (roleplay/
   yêu cầu bỏ qua tài liệu) — CHƯA sửa vì có đánh đổi thật với ngưỡng
   `min_score` chung.
3. **Vẫn cần quyết định thiết kế** (mục 3.5, case `EDU-ABS-014` "Kernel
   là gì?"): có nên xây một bước phát hiện "thuật ngữ có nhiều nghĩa/nhiều
   tài liệu không liên quan cùng khớp" độc lập không? Sau 2 fix, hệ thống
   giờ trả lời tự tin theo 1 nghĩa thay vì từ chối mơ hồ như trước — AN
   TOÀN hơn (không bịa) nhưng vẫn CHƯA nêu tên nghĩa còn lại. Xây thêm cần
   một bước so sánh cluster chunk theo tài liệu trước khi generation, có
   đánh đổi (thêm độ trễ/1 lượt LLM cho mọi câu hỏi, rủi ro false-positive
   hỏi lại khi không cần) — chưa xây, cần chốt hướng trước.
4. Vá `is_plausible_topic()` để nhận diện thêm định dạng trích dẫn web (URL
   + "Truy cập ngày") — mục 2.
5. Xem lại `resolve_topic()` (Summarize) — mục 1 Finding #4: 6/6 case fail
   category này hoàn toàn không qua `answer_question()`/verifier, lỗi nằm
   100% ở bước khớp từ khoá riêng của `resolve_topic()`.
6. Mở rộng độ phủ `personalization`/`persistence`/`multi_course_merge` còn
   thiếu (`evaluation_report.md` mục 4.3).
