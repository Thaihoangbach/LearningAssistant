"""Kiem tra chat luong eval/golden_set/data/golden_set.jsonl TRUOC khi chay
that (khong goi API/LLM/DB nao) — bat cac loi tung gap that trong qua trinh
xay dung bo case (xem eval/golden_set/annotations/annotation_guidelines.md):

1. Thieu field bat buoc (theo schema/golden_set.schema.json) hoac gia tri
   category/difficulty khong hop le.
2. id trung lap.
3. required_documents tham chieu document_id khong ton tai trong
   sources/run_doc_mapping.json.

Chay: python eval/scripts/validate_golden_set.py
Exit code 0 = sach, 1 = co loi (in danh sach loi ra stderr).
"""
import json
import os
import sys

HERE = os.path.dirname(__file__)
EVAL_ROOT = os.path.join(HERE, "..")
GOLDEN_SET_DIR = os.path.join(EVAL_ROOT, "golden_set")
GOLDEN_SET_PATH = os.path.join(GOLDEN_SET_DIR, "data", "golden_set.jsonl")
SCHEMA_PATH = os.path.join(GOLDEN_SET_DIR, "schema", "golden_set.schema.json")
DOC_MAPPING_PATH = os.path.join(GOLDEN_SET_DIR, "sources", "run_doc_mapping.json")


def load_jsonl(path):
    cases = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                cases.append((lineno, json.loads(line)))
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path}:{lineno}: invalid JSON — {e}")
    return cases


def main():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    required_fields = schema["required"]
    valid_categories = set(schema["properties"]["category"]["enum"])
    valid_difficulties = set(schema["properties"]["difficulty"]["enum"])

    with open(DOC_MAPPING_PATH, encoding="utf-8") as f:
        doc_mapping = json.load(f)
    valid_doc_ids = set(doc_mapping.keys())

    cases = load_jsonl(GOLDEN_SET_PATH)

    errors = []
    seen_ids = {}
    for lineno, case in cases:
        cid = case.get("id", f"<no id, line {lineno}>")

        missing = [f for f in required_fields if f not in case]
        if missing:
            errors.append(f"{cid}: thieu field bat buoc {missing}")

        if case.get("category") is not None and case["category"] not in valid_categories:
            errors.append(f"{cid}: category '{case['category']}' khong hop le")

        if case.get("difficulty") is not None and case["difficulty"] not in valid_difficulties:
            errors.append(f"{cid}: difficulty '{case['difficulty']}' khong hop le")

        if cid in seen_ids:
            errors.append(f"{cid}: id trung lap (dong {seen_ids[cid]} va {lineno})")
        else:
            seen_ids[cid] = lineno

        for doc_id in case.get("required_documents") or []:
            if doc_id not in valid_doc_ids:
                errors.append(
                    f"{cid}: required_documents tham chieu '{doc_id}' khong co trong "
                    f"run_doc_mapping.json"
                )

    print(f"Da kiem tra {len(cases)} case trong {GOLDEN_SET_PATH}")
    if errors:
        print(f"\n{len(errors)} loi:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    print("Khong co loi.")


if __name__ == "__main__":
    main()
