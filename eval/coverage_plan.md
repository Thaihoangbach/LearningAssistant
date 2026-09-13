# Phase 4 — Feature Coverage Matrix (planning target, before generation)

Target counts below are planning allocations for Phase 6 generation, not a
rigid contract — per Phase 8 guidance, every major feature must have
sufficient representation more than hitting an exact percentage. Grounded in
`eval/feature_inventory.md` (41 rows, business rules) for behavioral
categories and `eval/fact_inventory.json` (342 facts, 13 docs) for factual
categories.

| Cat | Category | Target cases | Primary grounding source |
|---|---|---:|---|
| A | Document management | 20 | feature_inventory.md rows: Upload, Status lifecycle, List, Delete, View/outline |
| B | Basic RAG QA | 45 | fact_inventory.json — all 12 in-scope docs (excl. 13 offtopic) |
| C | Retrieval stress | 35 | fact_inventory.json + corpus text (typo/paraphrase/near-miss variants) |
| D | Grounding/citation | 35 | fact_inventory.json + rag.py citation mechanics (already known) |
| E | Abstention/Clarification | 25 | fact_inventory.json (esp. doc 13 offtopic) + rag.py NEEDS_CLARIFICATION/NO_CONTEXT messages |
| F | Conversational QA | 25 | fact_inventory.json, multi-turn built on top of B cases |
| G | Query Decomposition | 20 | fact_inventory.json, 2-3 part combos across docs |
| H | Multi-document | 20 | fact_inventory.json across ≥2 docs, incl. offtopic distractor |
| I | Compare | 15 | fact_inventory.json comparison-type facts + cross-doc pairs |
| J | Summarize | 12 | docs WITH outline entries only: 03,06,07,08,09,11,12 (see eval/corpus/README.md) |
| K | Apply/Tutoring | 15 | fact_inventory.json procedure/example facts |
| L | Guardrails | 20 | app/llm/guardrail.py rules (already known in depth) |
| M | Personalization | 15 | feature_inventory.md Profile/level rows + fact_inventory.json |
| N | Mastery/Learning State | 12 | feature_inventory.md Mastery rows (decay formulas, thresholds) |
| O | Quiz | 18 | feature_inventory.md Quiz rows (partial-generation, dedup, mastery update) |
| P | Flashcard | 15 | feature_inventory.md Flashcard rows (SRS semantics, partial-gen) |
| Q | Study Plan | 15 | feature_inventory.md Study Plan rows (scope filter, priority bands, clamps) |
| R | Profile | 8 | feature_inventory.md Profile rows |
| S | Persistence/State | 10 | feature_inventory.md Persistence rows |
| T | Error handling | 12 | feature_inventory.md failure-behavior columns across all rows |
| **Total** | | **~392** | |

Regression subset (Phase 14): ~70 cases, drawn from across all categories
above, weighted toward core RAG/grounding/citation/abstention + one
representative case per feature area.

## Generation batching (Phase 6)

Split across parallel agents by category cluster to keep each agent's
context bounded and validation focused:

1. **Batch 1** — A, S, T (Document mgmt, Persistence, Error handling) — behavioral, `feature_inventory.md`-grounded
2. **Batch 2** — B, C (RAG QA, Retrieval stress) — factual, `fact_inventory.json`-grounded
3. **Batch 3** — D, E (Grounding/citation, Abstention/Clarification) — factual + rag.py mechanics
4. **Batch 4** — F, G, H (Conversational, Decomposition, Multi-document)
5. **Batch 5** — I, J, K, L (Compare, Summarize, Apply, Guardrails)
6. **Batch 6** — M, N, O, P, Q, R (Personalization, Mastery, Quiz, Flashcard, Study Plan, Profile)

Each batch writes `eval/golden_set_batchN.json`; merged, deduped (Phase 12),
and validated (Phase 7) into the final `eval/golden_set.jsonl` afterward.
