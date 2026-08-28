"""Đo CHẤT LƯỢNG TRUY HỒI tách rời khỏi chất lượng sinh nội dung.

Chạy: python eval/retrieval_metrics.py [--top-k 5] [--mode strict]

Không gọi LLM lần nào — chỉ nạp corpus, chạy truy hồi cho từng case có
`expected_evidence`, rồi đối chiếu tài liệu trả về với tài liệu kỳ vọng. Nhờ
vậy chạy được thường xuyên mà không tốn quota, và khi một case hỏng thì biết
ngay lỗi nằm ở truy hồi hay ở sinh nội dung — hai nguyên nhân đòi hai cách sửa
hoàn toàn khác nhau, mà LLM judge trên câu trả lời cuối không bao giờ phân
biệt được.

Hai mức đo, vì chúng nói hai chuyện khác nhau:

- **Mức tài liệu** — có lấy đúng tài liệu không. Dễ đạt khi corpus có ít tài
  liệu và chủ đề tách biệt, nên chỉ dùng để bắt hồi quy nặng.
- **Mức văn bản** — đoạn lấy về có THỰC SỰ chứa nội dung cần không, kiểm bằng
  trường `expected_text` của case. Đây mới là chỉ số có sức phân biệt, và là
  chỉ số phản ứng với thay đổi ở khâu chia chunk.

Không đòi khớp `section` vì `position_ref` của hệ thống là "Trang n"/"Mục n"
chứ không phải tên tiêu đề trong tài liệu.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

cli = argparse.ArgumentParser()
cli.add_argument("--top-k", type=int, default=5)
cli.add_argument("--mode", choices=["strict", "wide"], default="strict")
cli.add_argument("--golden", default="golden_set.jsonl")
ARGS = cli.parse_args()

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(EVAL_DIR)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
DOCS_DIR = os.path.join(EVAL_DIR, "documents")
GOLDEN_PATH = os.path.join(EVAL_DIR, ARGS.golden)

RUN_DIR = tempfile.mkdtemp(prefix="retrieval_metrics_")
os.environ["DB_PATH"] = os.path.join(RUN_DIR, "eval.db")
os.chdir(RUN_DIR)
sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient  # noqa: E402

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.retrieval.pipeline import retrieve_chunks  # noqa: E402

USER_ID = "retrieval-metrics-user"

init_db()
client = TestClient(app)


def upload_corpus():
    uploaded = []
    for filename in sorted(os.listdir(DOCS_DIR)):
        if not filename.lower().endswith((".pdf", ".docx")):
            continue
        with open(os.path.join(DOCS_DIR, filename), "rb") as f:
            resp = client.post(
                "/documents", params={"user_id": USER_ID}, files={"file": (filename, f)}
            )
        resp.raise_for_status()
        uploaded.append(filename)
    return uploaded


def wait_all_ready(timeout=900):
    start = time.time()
    while time.time() - start < timeout:
        docs = client.get("/documents", params={"user_id": USER_ID}).json()
        statuses = {d["status"] for d in docs}
        if statuses == {"sẵn sàng"}:
            return
        if "lỗi" in statuses:
            broken = [(d["file_name"], d["error_reason"]) for d in docs if d["status"] == "lỗi"]
            raise RuntimeError(f"Tài liệu lỗi: {broken}")
        time.sleep(2)
    raise TimeoutError("Corpus chưa sẵn sàng sau khi chờ")


def main():
    print("== Nạp corpus ==")
    uploaded = upload_corpus()
    print(f"   {len(uploaded)} tài liệu, đang chờ xử lý...")
    wait_all_ready()
    print("   sẵn sàng")

    cases = []
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            case = json.loads(line)
            if case.get("expected_evidence") and case.get("input", {}).get("query"):
                cases.append(case)

    print(f"\n== Đo trên {len(cases)} case có expected_evidence "
          f"(top_k={ARGS.top_k}, mode={ARGS.mode}) ==")

    hits = 0
    reciprocal_ranks = []
    misses = []

    text_checked = 0
    text_hits = 0
    text_misses = []

    for case in cases:
        expected_docs = {e["document"] for e in case["expected_evidence"]}
        chunks = retrieve_chunks(
            user_id=USER_ID,
            query=case["input"]["query"],
            top_k=ARGS.top_k,
            mode=ARGS.mode,
        )
        retrieved_docs = [c.document_name for c in chunks]

        rank = next((i + 1 for i, d in enumerate(retrieved_docs) if d in expected_docs), None)
        if rank:
            hits += 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)
            misses.append((case["id"], case["input"]["query"], sorted(expected_docs), retrieved_docs))

        # Mức văn bản — đoạn lấy về có thật sự chứa nội dung cần hay không.
        expected_text = case.get("expected_text")
        if expected_text:
            text_checked += 1
            needle = expected_text.lower()
            if any(needle in c.text.lower() for c in chunks):
                text_hits += 1
            else:
                text_misses.append(
                    (case["id"], expected_text, [f"{c.document_name}/{c.position_ref}" for c in chunks])
                )

    total = len(cases) or 1
    print(f"\n-- Mức tài liệu --")
    print(f"recall@{ARGS.top_k} = {hits / total:.3f}  ({hits}/{len(cases)})")
    print(f"MRR         = {sum(reciprocal_ranks) / total:.3f}")

    if text_checked:
        print(f"\n-- Mức văn bản (chỉ số có sức phân biệt) --")
        print(f"text_hit@{ARGS.top_k} = {text_hits / text_checked:.3f}  ({text_hits}/{text_checked})")

    if misses:
        print(f"\n== {len(misses)} case TRƯỢT ở mức tài liệu ==")
        for cid, query, expected, got in misses[:20]:
            print(f"  {cid}: {query[:70]}")
            print(f"     kỳ vọng: {expected}")
            print(f"     lấy về : {got}")

    if text_misses:
        print(f"\n== {len(text_misses)} case TRƯỢT ở mức văn bản ==")
        for cid, needle, got in text_misses[:20]:
            print(f"  {cid}: không đoạn nào chứa {needle!r}")
            print(f"     lấy về : {got}")

    shutil.rmtree(RUN_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()
