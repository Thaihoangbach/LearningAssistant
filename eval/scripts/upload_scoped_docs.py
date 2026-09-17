"""Upload 5 tai lieu vao 5 course RIENG, moi course chi chua DUNG 1 tai lieu
— dung ha tang cho 8 case out_of_scope trong Golden Set (EDU-ABS-016..023).

Vi sao can: POST /chat/ask chi gioi han pham vi theo course_name (xem
app/services/context_assembly.py), khong co tham so gioi han theo tung
document_id le. Corpus goc upload het 13 tai lieu vao CHUNG 1 course
("GoldenSetEval") nen 8 case out_of_scope (moi case chi dinh required_documents
la DUNG 1 tai lieu, ky vong retrieval CHI thay tai lieu do) chua tung duoc
test dung y do — hoi CNN van tim thay tai lieu CNN that trong course chung,
du case gia dinh chi co tai lieu Pho trong pham vi.

Script nay upload LAI (khong dung/xoa ban trong course chung) dung 5 tai lieu
can thiet, moi tai lieu vao 1 course rieng ten
"GoldenSetEval_scope_<key>" — doc_id/course_name moi ghi ra
eval/golden_set/sources/scoped_course_mapping.json de run_golden_set.py doc
lai va dinh tuyen dung 8 case ve course hep tuong ung.

Chay: python eval/scripts/upload_scoped_docs.py
"""
import json
import os
import time

import requests

HERE = os.path.dirname(__file__)
EVAL_ROOT = os.path.join(HERE, "..")
CORPUS_DIR = os.path.join(EVAL_ROOT, "corpus")
SOURCES_DIR = os.path.join(EVAL_ROOT, "golden_set", "sources")
OUT_PATH = os.path.join(SOURCES_DIR, "scoped_course_mapping.json")

BASE_URL = "http://127.0.0.1:8000"
USER_ID = "golden-eval-user"

# key -> file_name trong eval/corpus/ (key trung voi required_documents
# trong golden_set.jsonl).
NEEDED_DOCS = {
    "13_offtopic_am_thuc_vi": "13_offtopic_am_thuc_vi.pdf",
    "01_hoc_sau_vi": "01_hoc_sau_vi.pdf",
    "04_cay_quyet_dinh_vi": "04_cay_quyet_dinh_vi.pdf",
    "09_random_forest_en": "09_random_forest_en.pdf",
    "11_precision_and_recall_en": "11_precision_and_recall_en.pdf",
}


def upload_one(key: str, file_name: str) -> dict:
    course_name = f"GoldenSetEval_scope_{key}"
    file_path = os.path.join(CORPUS_DIR, file_name)
    with open(file_path, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/documents",
            params={"user_id": USER_ID, "course_name": course_name},
            files={"file": (file_name, f, "application/pdf")},
            timeout=60,
        )
    r.raise_for_status()
    document_id = r.json()["document_id"]
    print(f"  uploaded {file_name} -> document_id={document_id}, course={course_name}, waiting xu ly...")

    # Polling status cho tới "sẵn sàng" hoặc "lỗi" — cùng cơ chế corpus gốc
    # đã dùng (xem run_doc_mapping.json).
    for _ in range(60):
        time.sleep(2)
        docs = requests.get(f"{BASE_URL}/documents", params={"user_id": USER_ID}, timeout=30).json()
        row = next((d for d in docs if d["id"] == document_id), None)
        if row and row["status"] in ("sẵn sàng", "lỗi"):
            print(f"  -> status={row['status']}")
            return {
                "document_id": document_id,
                "course_name": course_name,
                "file_name": file_name,
                "status": row["status"],
            }
    raise TimeoutError(f"{file_name} chưa xử lý xong sau 120s")


def main():
    os.makedirs(SOURCES_DIR, exist_ok=True)
    mapping = {}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            mapping = json.load(f)

    for key, file_name in NEEDED_DOCS.items():
        if key in mapping and mapping[key].get("status") == "sẵn sàng":
            print(f"[{key}] đã có sẵn ({mapping[key]['document_id']}), bỏ qua.")
            continue
        print(f"[{key}] uploading {file_name}...")
        mapping[key] = upload_one(key, file_name)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)

    print(f"\nDONE. Mapping ghi tại {OUT_PATH}")


if __name__ == "__main__":
    main()
