# EduTutor Golden Set — Report (v1, current pgvector+Cohere architecture)

Built fresh from scratch per explicit instruction — supersedes the old
54-case `eval/golden_set.jsonl`/`eval/report.md` (deleted), which measured a
retired FAISS + sentence-transformers + rank_bm25 + local cross-encoder
architecture that no longer exists in this codebase. This Golden Set has
**not yet been run** against the live system — it is the evaluation
instrument, not the evaluation result. Running it (wiring each case's
`input`/`context` through `POST /chat/ask` etc. and scoring against
`expected_behavior`/`must_contain`/`abstention_type`) is the next step,
outside the scope of this build.

## 1. Totals

- **Total cases**: 393 (`eval/golden_set.jsonl`)
- **Regression subset**: 77 (`eval/golden_set_regression.jsonl`)
- **Documents**: 13 (`eval/corpus/`, see `eval/source_inventory.json`)
- **Atomic facts**: 342 (`eval/fact_inventory.json`)
- **Features covered**: 20 categories, mapping to 41 feature rows in `eval/feature_inventory.md`

## 2. Feature distribution (full set)

| Category | Cases | % of total |
|---|---:|---:|
| rag_qa | 45 | 11.5% |
| grounding_citation | 35 | 8.9% |
| retrieval | 35 | 8.9% |
| conversational | 25 | 6.4% |
| abstention_clarification | 25 | 6.4% |
| decomposition | 20 | 5.1% |
| multi_document | 20 | 5.1% |
| guardrail | 20 | 5.1% |
| document_management | 20 | 5.1% |
| quiz | 18 | 4.6% |
| compare | 15 | 3.8% |
| apply | 15 | 3.8% |
| personalization | 15 | 3.8% |
| flashcard | 15 | 3.8% |
| study_plan | 15 | 3.8% |
| mastery | 12 | 3.1% |
| summarize | 12 | 3.1% |
| error_handling | 13 | 3.3% |
| persistence | 10 | 2.5% |
| profile | 8 | 2.0% |

Full breakdown with difficulty split: `eval/coverage_matrix.csv`.

## 3. Difficulty distribution

easy 109 (27.7%) · medium 204 (51.9%) · hard 80 (20.4%)

## 4. Positive/negative distribution

- 234 cases (60%) expect a real grounded answer (`expected_answer` set)
- 54 cases (14%) expect abstention/rejection (`abstention_type` set)
- 217 cases (55%) require `expected_citations`
- 126 cases (32%) are purely behavioral (Quiz/Flashcard/Study Plan/Profile/Persistence/Error-handling mechanics with no document/citation involved)

## 5. Document distribution (usage across cases' `required_documents`)

| Document | Cases referencing it |
|---|---:|
| 02_mang_than_kinh_nhan_tao_vi | 42 |
| 03_mang_than_kinh_tich_chap_vi | 33 |
| 09_random_forest_en | 33 |
| 01_hoc_sau_vi | 27 |
| 04_cay_quyet_dinh_vi | 26 |
| 12_reinforcement_learning_en | 25 |
| 11_precision_and_recall_en | 23 |
| 10_gradient_descent_en | 19 |
| 06_su_qua_khop_vi | 15 |
| 08_dich_may_bang_no_ron_vi | 13 |
| 07_xac_suat_vi | 12 |
| 05_hoi_quy_tuyen_tinh_vi | 7 |
| 13_offtopic_am_thuc_vi | 4 (also referenced via `context`/`must_not_contain` in several abstention/multi-document cases without being listed in `required_documents`, since the point of those cases is that this document is NOT what should ground the answer) |

No single document dominates; the two thinnest source articles (05, 06 —
genuinely short Wikipedia stubs) proportionally have the fewest cases,
reflecting real content depth rather than arbitrary padding.

## 6. Topic distribution (from `fact_inventory.json`)

Reinforcement Learning 50 · Random Forest 36 · Gradient Descent 36 ·
Artificial Neural Network 32 · Deep Learning 31 · Decision Tree 30 ·
Probability 30 · Precision and Recall 30 · CNN 23 ·
Neural Machine Translation 18 · off-topic-negative 12 ·
Linear Regression 8 · Overfitting 6

## 7. Failure-mode coverage

254 distinct `failure_mode` descriptions across 393 cases (no repeated
generic label dominating) — each case states the SPECIFIC regression it
catches (e.g. "Regression could set interval_days=1 instead of 0 for
'again', breaking the same-session-reappearance guarantee") rather than a
generic "wrong answer" bucket.

## 8. Source coverage

- 100% of factual cases (`required_facts` non-empty) reference real,
  verified `fact_id`s from `eval/fact_inventory.json` — 0 invalid references
  found in the Phase 7 automated cross-check.
- 100% of behavioral cases (`document_management`, `persistence`,
  `error_handling`, `personalization`, `mastery`, `quiz`, `flashcard`,
  `study_plan`, `profile`) cite an actual row in `eval/feature_inventory.md`
  via `source_trace`.

## 9. Uncovered areas / known limitations

- **Quiz/Flashcard multi-document composite** generation exists in the
  backend (`document_ids` list param) but is NOT exposed by the current
  frontend (`QuizPage.jsx` only sends a single `documentId`) — cases in
  `eval/golden_set_batch1.json`/batch6 flag this explicitly as
  backend-only, not a frontend-testable path today.
- **`misconception.py::find_repeated_misconceptions`** appears fully built
  but no router call site was found during the Phase 0 audit — flagged as
  "UNCLEAR, may be dead code" rather than assumed live; no case in this set
  exercises it end-to-end through an API for that reason.
- **Timeout behavior** (Category T) has no documented mechanism, value, or
  message anywhere in the codebase — the one timeout case
  (`EDU-ERR-013`) is marked fully UNCLEAR rather than inventing a plausible
  contract.
- **Genuine conflicting-evidence cases** (Category D/E) — none were found
  across the 342 facts; per the no-fabrication constraint, this subcase is
  under-represented by honest necessity, not oversight.
- **Query Decomposition** (Category G): 8 of 20 cases are explicitly marked
  `failure_mode: "partial_answer_only_first_subquestion"` — these are
  EXPECTED to currently fail, since the app does not yet implement true
  query decomposition (confirmed in this session's own design discussion).
  This is intentional: the Golden Set documents the target contract ahead
  of the implementation, per the master spec's instruction not to encode
  current bugs/gaps as "correct."
- **Corpus size**: 13 documents / 342 facts is real but modest. Some
  categories (Compare, Summarize) are correspondingly smaller (15, 12
  cases) because only a subset of documents have topically comparable
  pairs or outline entries — not artificially padded to hit a target count.

## 10. Validation methodology (summary — full detail in `eval/golden_set_generation_notes.md`)

Phase 0-1 (repository + corpus audit) → Phase 3 (fact extraction, 4 parallel
agents, cross-checked for real `fact_id` uniqueness) → Phase 4 (coverage
plan) → Phase 6 (case generation, 6 parallel agents grounded in
`fact_inventory.json`/`feature_inventory.md`) → Phase 7 (automated
cross-validation: 0 duplicate IDs across 393 cases, 0 invalid
`required_facts` references) → Phase 12 (near-duplicate scan, 13 candidate
pairs manually reviewed, 0 removed — all confirmed legitimate variants
testing distinct system behavior per the master spec's own criterion) →
Phase 13 (adversarial self-check, quantified: a system that always
abstains would fail 60% of cases; a system with no citation mechanism
would fail 55%; guardrail false-positive coverage is 9/20 cases, not just
true-block cases) → Phase 14 (77-case regression subset, balanced across
all 20 categories and 3 difficulty levels).
