"""Tom tat pass rate theo category tu 1 file ket qua (run_golden_set.py),
va tuy chon so sanh 2 file de xem case nao doi pass<->fail giua 2 lan chay
(khong goi API/LLM nao — chi doc file JSONL da co san).

Chay:
  python eval/scripts/analyze_failures.py --file eval/results/baseline/run_results.jsonl
  python eval/scripts/analyze_failures.py --file <moi> --compare <cu>
"""
import argparse
import json
import os
from collections import defaultdict


def load(path):
    d = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            d[row["id"]] = row
    return d


def category_table(data):
    cat = defaultdict(lambda: [0, 0])
    for row in data.values():
        c = row.get("category")
        cat[c][1] += 1
        if row.get("overall_pass"):
            cat[c][0] += 1
    return cat


def print_summary(data, label):
    cat = category_table(data)
    total_pass = sum(p for p, _ in cat.values())
    total = sum(t for _, t in cat.values())
    print(f"\n=== {label} ===")
    print(f"Tong: {total_pass}/{total} ({100 * total_pass / total:.1f}%)\n")
    rows = sorted(cat.items(), key=lambda kv: kv[1][0] / kv[1][1] if kv[1][1] else 0)
    for c, (p, t) in rows:
        pct = 100 * p / t if t else 0
        print(f"  {c:25s} {p:3d}/{t:<3d}  {pct:5.1f}%")


def print_diff(old, new):
    print("\n=== Case doi ket qua giua 2 lan chay ===")
    flipped_to_fail, flipped_to_pass = [], []
    for cid, new_row in new.items():
        old_row = old.get(cid)
        if old_row is None:
            continue
        op, npass = old_row.get("overall_pass"), new_row.get("overall_pass")
        if op == npass:
            continue
        (flipped_to_fail if npass is False else flipped_to_pass).append(cid)

    print(f"\npass -> fail ({len(flipped_to_fail)}):")
    for cid in flipped_to_fail:
        print(f"  - {cid} ({new[cid].get('category')})")
    print(f"\nfail -> pass ({len(flipped_to_pass)}):")
    for cid in flipped_to_pass:
        print(f"  - {cid} ({new[cid].get('category')})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="File ket qua can phan tich (.jsonl)")
    parser.add_argument("--compare", default=None, help="File ket qua cu de so sanh (tuy chon)")
    args = parser.parse_args()

    data = load(args.file)
    print_summary(data, os.path.basename(args.file))

    if args.compare:
        old = load(args.compare)
        print_summary(old, os.path.basename(args.compare))
        print_diff(old, data)


if __name__ == "__main__":
    main()
