# Golden Set Generation Notes — Methodology

## Why this exists / trigger

The prior Golden Set (54 cases, `eval/golden_set.jsonl` + `eval/report.md`)
measured a retrieval architecture (FAISS + sentence-transformers + BM25 +
local cross-encoder) that the codebase has since fully migrated away from
(now Postgres+pgvector + Cohere embed/rerank + Postgres full-text search).
The user directed a from-scratch rebuild, explicitly independent of any
data already used in this project, to avoid selection bias from already
knowing how the app handles specific documents.

## How documents were selected

1. Searched Wikipedia (Vietnamese primary, English for topics without solid
   VI coverage) for standard ML/DL/Stats curriculum topics, deliberately
   avoiding any title already present in the deleted `eval/documents/`, in
   `real_test_documents/`, or already uploaded/tested against the live app
   this session (`Học máy`, `Trí tuệ nhân tạo` were excluded for this
   reason).
2. Downloaded via Wikipedia's official PDF export API
   (`/api/rest_v1/page/pdf/{title}`), the same mechanism already established
   as trustworthy in `real_test_documents/README.md`.
3. One deliberate off-topic negative-control document (`Phở`) was added for
   abstention/distractor testing.
4. Every file was run through the app's REAL `parse_document()`/
   `extract_outline()` before inclusion — one document (`Xác suất thống kê`)
   was rejected and replaced (`Xác suất`) after this check revealed it was
   a 254-character stub, too thin to support any case.

## How facts were extracted (Phase 3)

The 13 documents were parsed via `parse_document()`, dumped to plain text
with explicit `SECTION N | Trang X` markers so every fact could cite an
exact position. 4 parallel agents each read 2-6 documents and extracted
atomic, single-claim facts (definition/concept/procedure/relationship/
comparison/cause_effect/condition/exception/numerical_fact/table_value/
example/prerequisite/hierarchy/chronological), explicitly instructed to
skip reference-list/navigation filler and to phrase qualitatively rather
than invent a number/formula when PDF extraction had visibly lost
mathematical notation. All 342 resulting `fact_id`s were verified unique
across the 4 parallel outputs before merging (0 collisions).

## How questions were generated (Phase 6)

The 20 target categories were split into 6 parallel generation batches by
subject-matter cluster (not by mechanical page count) so each agent had
deep context on the specific product mechanics it was testing (e.g. the
batch covering Compare/Summarize/Apply/Guardrail was given the exact
trigger regexes and message-constant names from the real source files;
the batch covering Quiz/Flashcard/Mastery/Study Plan/Profile was given the
exact formulas/thresholds from the Phase 0 feature inventory rather than
generic assumptions). Every batch was instructed, as a standing rule, to
test the CURRENT fixed behavior of previously-documented-and-resolved bugs
(e.g. quiz/flashcard partial-generation reporting, atomic document
deletion) rather than the old buggy behavior, and to mark anything
genuinely unclear in the source material as `"UNCLEAR — verify against
code: ..."` rather than guess.

Two agent runs (batch 3, batch 6) were interrupted mid-generation by a
provider-side session rate limit; on retry, both had actually already
finished writing their output files before the interruption, so no
regeneration was needed — verified by re-checking JSON validity and
`fact_id` traceability rather than assumed.

## How expected answers were validated

- **Programmatic (Phase 7)**: every `required_facts` entry across all 393
  cases was checked against the real `fact_inventory.json` — 0 invalid
  references. Every case `id` was checked for uniqueness — 0 duplicates
  across the 6 independently-generated batches.
- **Manual/agent self-report**: each generation batch was required to
  report, alongside its output, exactly which subcategories it could NOT
  honestly construct (e.g. no genuine "conflicting evidence" pair exists in
  the 342 facts; batch 5 confirmed this and did not fabricate one).

## How duplicates were removed (Phase 12)

A `difflib.SequenceMatcher` pairwise scan within each category flagged 13
candidate pairs at >0.85 text similarity. Each was manually inspected:
all 13 turned out to be deliberate systematic variants testing distinct
system behavior on the same or near-identical input (e.g. the same
"Gradient descent là gì?" question used once to test normal citation
presence and once to test the invalid-citation-index-stripping mechanism;
the four SRS rating branches — again/hard/good/easy — tested from the same
starting flashcard state; three mastery bands — yếu/trung bình/tốt —
tested from the same templated setup). None were removed; this matches the
master spec's own explicit guidance that "same fact + citation validation"
and similar pairs are legitimate variants, not duplicates.

## How coverage was measured

`eval/coverage_matrix.csv` computed programmatically from the final merged
set (category × difficulty cross-tab). Document/topic/failure-mode
distributions computed the same way and reported in
`eval/golden_set_report.md`.

## How adversarial review was performed (Phase 13)

Rather than manually re-reading all 393 cases against every hostile
question in the master spec, the review was done quantitatively where a
quantitative answer is more reliable than a qualitative one:

- "Can the system pass by always abstaining?" → 60% of cases (234) require
  a real grounded `expected_answer`; an always-abstain system fails these.
- "Can it pass with no citation mechanism?" → 55% of cases (217) require
  `expected_citations`.
- "Can guardrails pass by blocking legitimate questions?" → 9 of 20
  guardrail cases are explicit `false_positive_*` subcategories (must NOT
  be blocked), not just true-block cases.
- "Can it pass by answering only one subquestion?" → Category G
  (decomposition) cases explicitly set `expected_coverage: 1.0` and 8/20
  are flagged with the anticipated current-gap failure mode, rather than
  silently accepting partial answers as passing.

These checks were run as code (`eval/` Python one-liners during the build),
not as claims — the counts above are reproducible.

## Known limitations of this Golden Set (see also report.md §9)

- 13 documents / 342 facts is a real but modest corpus — some categories
  (Compare, Summarize) have fewer cases than others because the corpus
  genuinely doesn't support more without either padding or fabricating
  facts, both explicitly disallowed.
- This Golden Set has not yet been executed against the live system. It is
  the measurement instrument; running it and recording pass/fail per case
  is a separate next step.
