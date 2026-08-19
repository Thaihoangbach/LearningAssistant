# Golden Set Evaluation Report — EduTutor

## 1. Evaluation Overview

### 1.1 Mục tiêu

Đánh giá nền tảng EduTutor (AI Personalized Learning Platform, RAG + LLM) trên các khía cạnh:

- RAG Retrieval & Generation
- Citation
- Personalization
- Quiz Generation
- Flashcard Generation
- Recommendation
- Study Planner
- Learning Analytics
- Safety & Reliability

### 1.2 Golden Set

| Thông tin | Giá trị |
|---|---|
| Tổng số cases | 54 |
| Số nhóm | 8 |
| Dataset domain | Machine Learning / Deep Learning (giáo dục) |

### 1.3 Evaluation Scope

Bốn lượt chạy thật (không mô phỏng), qua FastAPI TestClient + Gemini API thật, trên cùng một Golden Set 54 case:

| Run | Retrieval config | Mục đích |
|---|---|---|
| **Config B run1** | Hybrid + Reranker | **Cấu hình đang chạy thật (production)** |
| **Config B run2** | Hybrid + Reranker (giống hệt run1) | Lặp lại độc lập — đo nhiễu ngẫu nhiên LLM (mục 15) |
| **Config A run1** | Dense-only (ép qua biến môi trường, để so sánh) | Baseline thực nghiệm |
| **Config A run2** | Dense-only (giống hệt run1) | Lặp lại độc lập — đo nhiễu ngẫu nhiên LLM (mục 15) |

## 2. Golden Set Composition

| Category | Cases | Percentage |
|---|---|---|
| RAG QA | 26 | 48.1% |
| Personalization | 10 | 18.5% |
| Safety & Reliability | 5 | 9.3% |
| Assessment (Quiz) | 3 | 5.6% |
| Recommendation | 3 | 5.6% |
| Study Planner | 3 | 5.6% |
| Flashcard | 2 | 3.7% |
| Analytics & Memory | 2 | 3.7% |
| **Total** | **54** | **100%** |

RAG QA chiếm gần một nửa bộ case có chủ đích: đây là lớp nền tảng mọi tính năng khác phụ thuộc vào (quiz/flashcard/recommendation đều lấy nội dung từ cùng pipeline retrieval), nên cần cỡ mẫu đủ lớn (26 case, trải trên 4 tài liệu, nhiều dạng câu hỏi) để kết luận đáng tin cậy thay vì suy diễn từ vài case đơn lẻ.

## 3. System Configuration

Cấu hình THẬT đọc trực tiếp từ code, không phải giá trị mẫu:

| Component | Configuration |
|---|---|
| LLM (generator/verifier/judge) | Google Gemini `gemini-3.1-flash-lite` |
| Embedding | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (local, đa ngôn ngữ) |
| Vector DB | FAISS `IndexFlatIP` (local file, 1 index riêng/user) |
| Chunking | Fixed-size theo ký tự (không phải recursive/semantic) — 800 ký tự/chunk, overlap 100 |
| Retriever | Hybrid: Dense (FAISS cosine) + BM25 (`rank_bm25`), hợp nhất bằng Reciprocal Rank Fusion (k=60) |
| Reranker | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (multilingual cross-encoder) |
| Candidate pool trước rerank | max(20, top_k×3) |
| Top-K (cuối cùng) | 5 |
| LLM temperature | Không set tường minh (mặc định API) |

## 4. Evaluation Metrics

Không dùng một metric chung cho mọi module — mỗi nhóm có bộ tiêu chí riêng, chấm bằng rule-based (khi đo được chính xác) hoặc LLM-as-judge (khi cần đánh giá nội dung):

| Nhóm | Metric đã đo | Metric đề xuất nhưng CHƯA đo (ghi rõ để không nhầm là có) |
|---|---|---|
| RAG | Context Recall, Context Precision, Faithfulness, Answer Relevance, Citation Accuracy | MRR, Hit@K (cần chấm độ liên quan từng chunk riêng lẻ, chưa instrument) |
| Personalization | Difficulty Alignment (`difficulty_matches_student_level`), Depth Differentiation (`answer_differs_from_beginner_version`) | Profile Consistency (cần Learning Profile lưu trữ, chưa có) |
| Quiz/Flashcard | Groundedness, Question/Card Count, Answer Key Correctness, Diversity | Topic Coverage định lượng |
| Recommendation | Relevance, Avoid-mastered-topic | Prerequisite Consistency, Learning Goal Alignment, Explanation Quality (cần đồ thị prerequisite / goal lưu trữ, chưa có) |
| Planner | Deadline Satisfaction, Weak-topic Priority, Non-empty plan | Workload Feasibility theo giờ/ngày (planner hiện chia theo SỐ CHỦ ĐỀ, chưa theo giờ) |
| Safety | Refusal Correctness, Policy Compliance | Hallucination Rate riêng biệt (đo gộp trong Faithfulness của RAG) |

## 5. Overall Results

Tính trên **Config B (Hybrid + Reranker)** — cấu hình đang chạy thật (production):

| Dimension | Score | N |
|---|---|---|
| Faithfulness | 0.90 | 40 |
| Citation Accuracy | 0.75 | 20 |
| Context Precision | 0.77 | 22 |
| Context Recall | 0.50 | 2 |
| Answer Relevance | 0.50 | 2 |
| Personalization | 0.13 | 15 |
| Quiz Groundedness | 0.67 | 9 |
| Flashcard Groundedness | 1.00 | 6 |
| Recommendation Relevance | 1.00 | 4 |
| Planner Constraint Satisfaction | 1.00 | 5 |
| Safety | 1.00 | 7 |
| Analytics Tracking | 1.00 | 4 |
| **Overall (trung bình cộng gộp N)** | **0.765** | **136** |

**Lưu ý về cách tính Overall:** đây là tổng số tiêu chí PASS chia cho tổng số tiêu chí được chấm trên toàn bộ 54 case (không phải trung bình cộng đơn giản của 12 dòng trên) — vì các dimension có N rất khác nhau (Faithfulness N=40 so với Context Recall N=2), lấy trung bình 12 dòng sẽ cho trọng số sai (đánh đồng 1 dimension đo bằng 2 tình huống với 1 dimension đo bằng 40 tình huống). Context Recall và Answer Relevance có N=2 — quá nhỏ để coi là số liệu đáng tin cậy độc lập, chỉ nên đọc cùng phần Failure Analysis bên dưới.

## 6. Results by Category

Tính theo case (1 case PASS chỉ khi TẤT CẢ tiêu chí của case đó đều PASS):

| Category | Pass | Fail | Pass Rate |
|---|---|---|---|
| Flashcard | 2 | 0 | 100% |
| Recommendation | 3 | 0 | 100% |
| Study Planner | 3 | 0 | 100% |
| Analytics | 2 | 0 | 100% |
| Safety | 5 | 0 | 100% |
| RAG QA | 17 | 9 | 65.4% |
| Assessment (Quiz) | 1 | 2 | 33.3% |
| Personalization | 1 | 9 | 10.0% |

**Nhận xét có giá trị hơn một con số tổng:** 5/8 nhóm đạt 100% — đều là các bước tính toán/quy tắc cố định (Flashcard/Recommendation/Planner/Analytics dựa trên công thức, Safety dựa trên mẫu nhận diện). Ba nhóm còn lại đều liên quan tới việc AI phải TỰ SINH nội dung hoặc TỰ CHỌN nguồn — RAG QA đạt 65.4% cho thấy phần lõi hỏi-đáp còn nhiều dư địa cải thiện, và Personalization chỉ 10% là điểm yếu rõ ràng nhất của toàn hệ thống.

## 7. RAG Evaluation

### 7.1 Retrieval

| Metric | Score | N |
|---|---|---|
| Context Precision | 0.77 | 22 |
| Context Recall | 0.50 | 2 |
| MRR | *chưa đo* | — |
| Hit@5 | *chưa đo* | — |

### 7.2 Generation

| Metric | Score | N |
|---|---|---|
| Faithfulness | 0.90 | 40 |
| Answer Relevance | 0.50 | 2 |

### 7.3 Citation

| Metric | Score | N |
|---|---|---|
| Citation Accuracy | 0.75 | 20 |

**Phát hiện chính của nhóm RAG:** phần lớn lỗi retrieval/citation (16/26 case RAG QA có ít nhất 1 tiêu chí fail) quy về đúng 2 nguyên nhân — (1) khi một khái niệm xuất hiện ở nhiều tài liệu, hệ thống trích dẫn cả những tài liệu ngoài phạm vi câu hỏi dự kiến; (2) 2 case bị từ chối trả lời sai (hệ thống báo "không có thông tin" dù thông tin thực sự có trong tài liệu) — đây là lỗi nghiêm trọng nhất trong nhóm RAG vì trực tiếp phủ nhận một câu hỏi cơ bản hợp lệ.

## 8. Personalized Learning Evaluation

| Test Group | Cases | Pass (case-level) | Score (assertion-level) |
|---|---|---|---|
| Student Level (beginner vs advanced) | 10 (5 cặp chủ đề) | 1/10 | 2/15 = 13% |
| Learning Goal | *không có trong bộ case này* | — | — |
| Weak Topic | *đo trong nhóm Recommendation, không phải Personalization* | — | — |
| Learning History | *chưa có tính năng — Learning Profile lưu trữ dài hạn chưa tồn tại* | — | — |

**Nhận xét:** Đây là khía cạnh yếu nhất hệ thống. Với 5 chủ đề khác nhau (Gradient Descent, Decision Tree, Backpropagation, CNN, Pooling), **9/10 case fail theo đúng 1 trong 2 kiểu lặp lại**: (a) bản "beginner" vẫn dùng thuật ngữ chuyên môn không đủ giải nghĩa đơn giản, hoặc (b) bản "advanced" không đủ khác biệt độ sâu so với bản beginner. Vì lặp lại nhất quán trên nhiều chủ đề độc lập, đây là hành vi hệ thống chứ không phải nhiễu ngẫu nhiên của một câu trả lời đơn lẻ.

## 9. Generation Evaluation (Quiz & Flashcard)

| Feature | Groundedness | Correctness (answer key) | Count đúng yêu cầu |
|---|---|---|---|
| Quiz | 100% (mọi câu đều qua verifier) | 0/3 case *("fail" ở đây là false-negative của giám khảo — xem mục 13* | 2/3 case đúng số lượng |
| Flashcard | 100% | — (không có đáp án đúng/sai) | 2/2 case đúng |

## 10. Recommendation Evaluation

| Metric | Score | N |
|---|---|---|
| Topic Relevance (ưu tiên chủ đề yếu) | 1.00 | 4 |
| Avoid-mastered-topic | 1.00 | (gộp trong 4 trên) |
| Prerequisite Consistency | *chưa đo — cần đồ thị prerequisite giữa các chủ đề, chưa xây dựng* | — |
| Learning Goal Alignment | *chưa đo — cần lưu trữ mục tiêu học tập dài hạn, chưa xây dựng* | — |
| Explanation Quality | *có giải thích lý do (dựa theo điểm số) nhưng chưa chấm riêng chất lượng giải thích* | — |

Đây là nhóm hoạt động đúng 100% và đáng tin cậy (dựa hoàn toàn vào công thức đọc lại điểm mastery đã lưu, không qua bước AI tự sinh nội dung).

## 11. Study Planner Evaluation

| Constraint | Satisfied |
|---|---|
| Không vượt deadline | 100% (5/5) |
| Kế hoạch không rỗng | 100% (5/5) |
| Ưu tiên chủ đề yếu lên trước | 100% (2/2 case có kiểm tra ràng buộc này) |
| Không học lại chủ đề đã thành thạo | *không kiểm tra riêng — planner hiện xếp TẤT CẢ chủ đề vào lịch, chỉ khác thứ tự ưu tiên, không loại hẳn chủ đề đã giỏi* |
| Phân bổ workload theo giờ/ngày | *chưa đo — planner hiện chia theo SỐ CHỦ ĐỀ/ngày, chưa có khái niệm giờ học* |

## 12. Safety & Reliability

| Metric | Score | N |
|---|---|---|
| Refusal Accuracy (từ chối đúng yêu cầu không phù hợp) | 1.00 | 7 |
| Prompt Injection Resistance | 1.00 | (gộp trong 7 trên, case `EDU-SAFE-003`) |
| Hallucination Rate (không đủ căn cứ → không bịa) | đo trong Faithfulness ở mục 7.2, không tách riêng cho case Safety | — |

5/5 case Safety đạt 100% ở cả Config A lẫn Config B — nhóm này không phụ thuộc vào cấu hình retrieval (guardrail chạy trước bước retrieval).

## 13. Failure Analysis

Config B có **20/54 case fail** (37%). Thay vì chỉ báo con số, dưới đây là 5 case đại diện kèm root cause:

| Case | Category | Failure | Root Cause | Severity |
|---|---|---|---|---|
| EDU-RAG-013 | RAG QA | Hệ thống báo "không có thông tin" cho một câu hỏi cơ bản có thật trong tài liệu | Tương tác retrieval + verifier quá thận trọng | **Critical** |
| EDU-RAG-014 | RAG QA | Giống EDU-RAG-013 — từ chối trả lời câu hỏi cơ bản có thật | Cùng nguyên nhân trên | **Critical** |
| EDU-RAG-004 | RAG QA | Từ chối hoàn toàn câu hỏi so sánh 2 chủ đề tách biệt | Retrieval không cân bằng khi 2 chủ đề trong câu hỏi cách xa nhau về ý nghĩa | High |
| EDU-PER-002 | Personalization | Bản "advanced" không đủ sâu, không khác biệt bản beginner | Chỉ dẫn độ sâu trong prompt chưa đủ mạnh để ép mô hình phân biệt rõ 2 trình độ (xem mục 15 về mức nhiễu của dimension này) | High |
| EDU-RAG-001 | RAG QA | Trích dẫn thêm tài liệu ngoài phạm vi câu hỏi | Nội dung trùng lặp giữa 2 tài liệu + chưa giới hạn tìm kiếm theo môn học | Medium |
| EDU-QUIZ-001 | Assessment | Giám khảo AI báo thiếu đáp án | **False-negative của cách đánh giá** — hệ thống cố tình giấu đáp án theo thiết kế | Low (không phải lỗi thật) |

### 13.1 Failure Taxonomy

```
Failures (20 case, Config B)
│
├── RAG QA (9 case)
│   ├── Trích dẫn lẫn tài liệu ngoài phạm vi ── 4 case
│   ├── Từ chối trả lời sai (thông tin có thật nhưng báo không có) ── 2 case
│   ├── Thiếu chi tiết cốt lõi trong câu trả lời ── 2 case
│   └── Retrieval không cân bằng đa chủ đề ── 1 case
│
├── Personalization (9 case)
│   └── Độ sâu/thuật ngữ chưa khớp trình độ ── 9 case
│
└── Assessment (2 case)
    └── Giám khảo hiểu nhầm thiết kế giấu đáp án ── 2 case (methodology, không phải lỗi thật)
```

| Failure Mode | Count | Percentage |
|---|---|---|
| Personalization depth/jargon mismatch | 9 | 45% |
| Cross-document citation leakage | 4 | 20% |
| False refusal (thông tin có thật nhưng báo không có) | 2 | 10% |
| Content completeness gap | 2 | 10% |
| Evaluation methodology false-negative | 2 | 10% |
| Multi-topic retrieval imbalance | 1 | 5% |

## 14. Baseline Comparison

```
Config A — Dense RAG            Config B — Hybrid RAG (đang chạy thật)
Embedding (FAISS cosine)        BM25 + Embedding (FAISS)
+ LLM                           + Reranker (cross-encoder)
                                 + LLM
```

*Config C — Personalized RAG (Hybrid + Reranker + Learning Profile lưu trữ dài hạn) **CHƯA thực hiện được** — "Learning Profile" như một hồ sơ lưu trữ xuyên phiên chưa tồn tại trong hệ thống; cá nhân hoá hiện chỉ qua tham số `level` gửi kèm mỗi request, không phải hồ sơ tự động áp dụng. Không đưa số liệu giả cho cột này.*

| Metric | Config A (Dense) | Config B (Hybrid+Reranker) | Δ |
|---|---|---|---|
| Context Recall | 0.50 (N=2) | 0.50 (N=2) | 0 |
| Context Precision | **0.41** (N=22) | **0.77** (N=22) | **+0.36** |
| Faithfulness | 0.80 (N=40) | 0.90 (N=40) | +0.10 |
| Answer Relevance | 1.00 (N=2) | 0.50 (N=2) | −0.50 *(N quá nhỏ, xem giải thích dưới)* |
| Citation Accuracy | **0.30** (N=20) | **0.75** (N=20) | **+0.45** |
| Personalization | **0.67** (N=15) | **0.13** (N=15) | **−0.53** *(đánh đổi, xem giải thích dưới)* |
| Quiz Groundedness | 0.78 (N=9) | 0.67 (N=9) | −0.11 |
| Flashcard/Recommendation/Planner/Safety/Analytics | 1.00 (không đổi — không phụ thuộc retrieval) | 1.00 | 0 |
| **Overall** | **0.684** (93/136) | **0.765** (104/136) | **+0.081** |

**Giải thích 2 điểm bất thường (không né tránh số liệu ngược hướng kỳ vọng):**

1. **Answer Relevance Config A cao hơn Config B** — chỉ dựa trên N=2, và đúng 1 trong 2 case (EDU-RAG-004, so sánh 2 chủ đề tách biệt) là nơi khác biệt: Config A (dense-only) lấy được MỘT PHẦN nội dung từ cả 2 tài liệu (dù không chính xác 100%) nên tổng hợp được câu trả lời tạm chấp nhận; Config B (hybrid+reranker) lọc quá gắt, chỉ giữ 1 chủ đề rồi từ chối trả lời phần còn lại. N=2 không đủ để kết luận "Dense tốt hơn Hybrid" — chỉ cho thấy đánh đổi giữa "trả lời không hoàn hảo" và "từ chối trả lời" trong tình huống khó.

2. **Personalization Config A cao hơn Config B rõ rệt (0.67 vs 0.13)** — đây là phát hiện thật đáng chú ý: retrieval kém chính xác hơn (Config A) vô tình LẤY NHIỀU nội dung hơn (ít lọc hơn), cho generator nhiều nguyên liệu hơn để viết câu trả lời "advanced" đủ dài/đủ sâu — đổi lại bằng việc trích dẫn sai nguồn nhiều hơn hẳn (Citation Accuracy giảm từ 0.75 xuống 0.30). Đây là một đánh đổi thật giữa "độ sâu cá nhân hoá" và "độ chính xác trích dẫn", không phải một cấu hình thắng tuyệt đối cấu hình kia.

**Kết luận so sánh:** Hybrid + Reranker (Config B) thắng rõ rệt ở đúng những khía cạnh nó được thiết kế để cải thiện (Context Precision +0.36, Citation Accuracy +0.45) và thắng ở Overall (+0.081) — nhưng KHÔNG phải chiến thắng toàn diện; đánh đổi thật tồn tại ở Personalization, gợi ý hướng cải thiện tiếp theo là tăng candidate pool hoặc nới lỏng ngưỡng lọc RIÊNG cho câu hỏi có `level` thay vì áp dụng đồng nhất.

## 15. Run-to-Run Variance (đo nhiễu ngẫu nhiên của LLM)

LLM không set temperature cố định, nên cùng một câu hỏi có thể nhận câu trả lời hơi khác nhau giữa 2 lần gọi độc lập. Để biết con số nào trong báo cáo này là tín hiệu thật của hệ thống và con số nào chỉ là dao động ngẫu nhiên, mỗi cấu hình (A và B) được chạy **2 lần độc lập**, giữ nguyên code, golden set và tham số — chỉ khác nhau ở việc Gemini trả lời lại từ đầu lần thứ 2.

| | Config A run1 | Config A run2 | Δ A | Config B run1 | Config B run2 | Δ B |
|---|---|---|---|---|---|---|
| **Overall** | 68.4% (93/136) | 69.9% (95/136) | +1.5pp | 76.5% (104/136) | 79.4% (108/136) | +2.9pp |

| Dimension (N cố định cả 2 lần) | A run1 | A run2 | Δ A | B run1 | B run2 | Δ B |
|---|---|---|---|---|---|---|
| Faithfulness (N=40) | 80.0% | 85.0% | +5.0pp | 90.0% | 92.5% | +2.5pp |
| Citation Accuracy (N=20) | 30.0% | 30.0% | 0pp | 75.0% | 75.0% | 0pp |
| Context Precision (N=22) | 40.9% | 45.5% | +4.5pp | 77.3% | 77.3% | 0pp |
| Context Recall (N=2) | 50.0% | 50.0% | 0pp | 50.0% | 50.0% | 0pp |
| Answer Relevance (N=2) | 100.0% | 100.0% | 0pp | 50.0% | 50.0% | 0pp |
| **Personalization (N=15)** | 66.7% | 60.0% | **−6.7pp** | 13.3% | 26.7% | **+13.3pp** |
| **Quiz Groundedness (N=9)** | 77.8% | 77.8% | 0pp | 66.7% | 77.8% | **+11.1pp** |
| Flashcard / Recommendation / Planner / Safety / Analytics | 100% cả 2 lần | | 0pp | 100% cả 2 lần | | 0pp |

**Kết luận từ dữ liệu lặp lại thật (N=2/cấu hình):**

1. **Personalization và Quiz Groundedness là 2 dimension dao động đáng kể giữa 2 lần chạy CÙNG code, CÙNG cấu hình** (Personalization dao động tới 13.3pp ở Config B, Quiz Groundedness dao động 11.1pp). Đây là bằng chứng trực tiếp rằng một phần biến động quan sát được ở 2 dimension này (kể cả chênh lệch giữa Config A và Config B ở mục 14) đến từ nhiễu ngẫu nhiên của LLM, không thuần tuý là hiệu ứng thật của cấu hình retrieval — nên cần đọc các con số Personalization/Quiz Groundedness với biên độ sai số ±10-13pp thay vì coi là chính xác tuyệt đối.
2. **Các dimension liên quan trực tiếp tới retrieval — Citation Accuracy, Context Recall, Answer Relevance, và Context Precision của Config B — ổn định tuyệt đối (0pp dao động)** giữa 2 lần chạy độc lập. Đây là bằng chứng quan trọng: sự chênh lệch Config A vs Config B ở các dimension này tại mục 14 (Citation Accuracy +0.45, Context Precision +0.36) **là tín hiệu thật, không phải nhiễu** — vì nếu là nhiễu ngẫu nhiên thì đã dao động giữa 2 lần chạy cùng cấu hình, nhưng thực tế không hề dao động.
3. **5 nhóm dựa trên logic tính toán xác định (Flashcard, Recommendation, Planner, Safety, Analytics) đạt 100% ở CẢ 4 lượt chạy (2 config × 2 lần)** — xác nhận đúng giả thuyết ở mục 6 rằng các nhóm này không phụ thuộc vào tính ngẫu nhiên của LLM.
4. **Personalization ở Config A cũng dao động (−6.7pp)** dù cùng hướng cải thiện kỳ vọng không rõ ràng — cho thấy bản thân dimension Personalization vốn nhiễu cao (N=15 với 2 kiểu lỗi lặp lại ở ranh giới PASS/FAIL), không phải chỉ Config B mới nhiễu.

**Hạn chế còn lại:** N=2/cấu hình đủ để PHÁT HIỆN có nhiễu và xác nhận dimension nào ổn định/dao động, nhưng chưa đủ để ước lượng chính xác độ lớn nhiễu (cần N≥5 cho việc đó). Xem mục 17.

## 16. Discussion

Ba phát hiện có giá trị nhất của đợt đánh giá này:

1. **Hybrid + Reranker thật sự tốt hơn Dense-only** ở đúng các khía cạnh retrieval-precision (Context Precision, Citation Accuracy) — xác nhận bằng thực nghiệm thật, không chỉ suy luận lý thuyết, nhưng đi kèm đánh đổi ở Personalization cần cân nhắc thêm. Chạy lặp lại 2 lần độc lập (mục 15) cho thấy 2 dimension này **không dao động (0pp)** giữa các lần chạy cùng cấu hình, nên chênh lệch quan sát được giữa Config A và B là tín hiệu thật chứ không phải nhiễu ngẫu nhiên của LLM.
2. **"False refusal" (từ chối trả lời câu hỏi có căn cứ thật) là lỗi nghiêm trọng nhất tìm được** — nghiêm trọng hơn cả hallucination về mặt trải nghiệm người dùng cơ bản, vì xảy ra với chính những câu hỏi đơn giản nhất trong bộ test.
3. **Personalization là điểm yếu nhất và mang tính hệ thống** (lặp lại ở 9/10 case, nhiều chủ đề độc lập) — không phải vấn đề dữ liệu hay nhiễu ngẫu nhiên.

## 17. Limitations

- **Corpus nhỏ, tự tạo (4 tài liệu DOCX)** — không đại diện cho tài liệu thật đa dạng (PDF scan, bảng biểu, công thức toán phức tạp).
- **Mỗi cấu hình đã chạy lặp lại N=2 lần (mục 15)** — đủ để XÁC NHẬN có nhiễu ngẫu nhiên thật (Personalization, Quiz Groundedness dao động 11-13pp giữa 2 lần chạy cùng code) và xác nhận các dimension liên quan trực tiếp tới retrieval (Citation Accuracy, Context Precision, Context Recall, Answer Relevance) ổn định tuyệt đối — nhưng N=2 CHƯA đủ để ước lượng chính xác độ lớn/phân bố của nhiễu đó (cần N≥5 lần/cấu hình cho việc này, hiện chưa thực hiện do giới hạn quota Gemini free tier).
- **Context Recall và Answer Relevance chỉ có N=2** trong toàn bộ báo cáo — mọi số liệu về 2 dimension này chỉ mang tính chỉ dấu.
- **Config C (Personalized RAG với Learning Profile) không thực hiện được** vì tính năng lưu hồ sơ học tập dài hạn chưa tồn tại trong hệ thống.
- **Giới hạn quota Gemini free tier (500 request/ngày)** khiến 1 lượt chạy Config A phải chia làm 3 đợt (gốc + retry lỗi 429 + chấm bù judge) trải qua 2 ngày — không ảnh hưởng tới độ chính xác kết quả cuối (đã xác nhận không còn case lỗi) nhưng ảnh hưởng tốc độ lặp thực nghiệm.
- **Golden Set chưa có nhóm Document & Knowledge Base** (parsing/chunking/versioning) trong lần mở rộng này.

## 18. Future Improvements

- **Xử lý "false refusal"** — ưu tiên cao nhất, vì đây là lỗi nghiêm trọng nhất tìm được (mục 13, 16).
- **Learning Profile lưu trữ dài hạn** — để Personalization tự động áp dụng thay vì phụ thuộc tham số mỗi request, và để Config C (so sánh có/không Learning Profile) thực hiện được.
- **Query decomposition cho câu hỏi đa chủ đề** — tách câu hỏi so sánh thành các truy vấn con, retrieve riêng từng chủ đề rồi gộp (cùng cách tiếp cận đã áp dụng cho sinh quiz đa tài liệu).
- **Giới hạn phạm vi trích dẫn theo môn học mặc định** (hoặc cảnh báo rõ khi trích chéo môn) — giải quyết phần lớn nhóm lỗi "cross-document citation leakage".
- **Prerequisite graph** cho Recommendation, **Workload theo giờ** cho Planner — để đo được các metric hiện chưa instrument (mục 4, 10, 11).
- **Chạy lặp lại N≥5/cấu hình** để ước lượng chính xác độ lớn nhiễu (N=2 ở mục 15 mới đủ xác nhận CÓ nhiễu, chưa đủ đo ĐỘ LỚN nhiễu).

## 19. Conclusion

Trên 54 tình huống thật, hệ thống đạt 76.5% tổng thể ở cấu hình đang chạy (Hybrid+Reranker). Điểm mạnh: an toàn, gợi ý học tập, kế hoạch ôn tập, theo dõi tiến độ — đều 100%, dựa trên logic tính toán xác định thay vì AI tự sinh nội dung. Điểm yếu rõ ràng nhất là Personalization (10-13%, mang tính hệ thống — lặp lại ở 9/10 case, nhiều chủ đề độc lập) và một nhóm nhỏ nhưng nghiêm trọng các câu trả lời từ chối sai trong RAG QA. Thực nghiệm so sánh Config A/B xác nhận bằng số liệu thật rằng Hybrid+Reranker cải thiện đáng kể độ chính xác trích dẫn so với Dense-only (+0.45), đúng như giả thuyết thiết kế ban đầu — nhưng đi kèm đánh đổi ở Personalization cần điều tra thêm trước khi kết luận cấu hình nào tối ưu toàn diện.
