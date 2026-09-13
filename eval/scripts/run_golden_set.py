"""Chạy các case trong golden_set.jsonl thuộc nhóm dùng chung POST /chat/ask
(rag_qa, retrieval, grounding_citation, abstention_clarification,
conversational, decomposition, multi_document, compare, summarize, apply,
guardrail) trên hệ thống thật đang chạy local (xem run_doc_mapping.json cho
danh sách document đã tải lên), chấm điểm theo expected_behavior/
abstention_type/expected_citations/must_contain/must_not_contain, và với
case có expected_answer thì dùng thêm 1 lượt LLM judge để chấm nội dung có
đúng ý hay không.

KHÔNG chạy các category còn lại (document_management, persistence,
error_handling, personalization, mastery, quiz, flashcard, study_plan,
profile) — các category đó cần fixture trạng thái DB phức tạp hơn (lịch sử
attempt, flashcard review nhiều ngày...) mà bản thân mỗi case chỉ mô tả bằng
ngôn ngữ tự nhiên trong `context`, chưa đủ cấu trúc để dựng fixture tự động
đáng tin cậy trong lần chạy này.

Output: eval/results/run_results.jsonl (1 dòng/case, có actual response + điểm).

Cờ `--regression-only`: chỉ chạy tập con 77 case đánh dấu
`in_regression_set: true` trong golden_set.jsonl (dùng để kiểm tra không
hồi quy sau khi sửa code, nhanh hơn chạy lại toàn bộ 267 case) — ghi ra
eval/results/regression_results.jsonl thay vì run_results.jsonl. Đổi tên
file output bằng `--out <filename>` nếu cần (vẫn ghi trong eval/results/).
"""
import json
import os
import sys
import time

import requests

# Script nay nam o eval/scripts/ — EVAL_ROOT la eval/ (thu muc cha), noi
# chua golden_set.jsonl/run_doc_mapping.json va thu muc results/.
HERE = os.path.dirname(__file__)
EVAL_ROOT = os.path.join(HERE, "..")
RESULTS_DIR = os.path.join(EVAL_ROOT, "results")

sys.path.insert(0, os.path.join(EVAL_ROOT, "..", "backend"))

BASE_URL = "http://127.0.0.1:8000"
USER_ID = "golden-eval-user"
COURSE_NAME = "GoldenSetEval"

CHAT_ASK_CATEGORIES = {
    "rag_qa", "retrieval", "grounding_citation", "abstention_clarification",
    "conversational", "decomposition", "multi_document", "compare",
    "summarize", "apply", "guardrail",
}

with open(os.path.join(EVAL_ROOT, "run_doc_mapping.json"), encoding="utf-8") as f:
    DOC_MAPPING = json.load(f)
FILE_NAME_BY_DOC_ID = {v["file_name"]: k for k, v in DOC_MAPPING.items()}


# Key Cohere trial hiện dùng giới hạn 10 lượt gọi/phút; mỗi /chat/ask tốn
# ~3 lượt Cohere (embed truy vấn, rerank, embed cho memory-recall) -> giãn
# cách tối thiểu giữa 2 request để không vượt quá 10 lượt Cohere/phút.
_MIN_SECONDS_BETWEEN_REQUESTS = 20


def ask(question, conversation_id=None, retries=3):
    payload = {"user_id": USER_ID, "question": question, "course_name": COURSE_NAME}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    for attempt in range(retries):
        try:
            r = requests.post(f"{BASE_URL}/chat/ask", json=payload, timeout=90)
            if r.status_code == 200:
                time.sleep(_MIN_SECONDS_BETWEEN_REQUESTS)
                return r.json()
            print(f"  [HTTP {r.status_code}] {r.text[:200]}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  [request error] {e}", file=sys.stderr)
        time.sleep(30 * (attempt + 1))
    return None


_NO_CONTEXT_SNIPPET = "chưa có trong tài liệu"
# answer_with_fallback (app/services/qa_pipeline.py) bọc NO_CONTEXT/NOT_GROUNDED
# bằng message giàu thông tin hơn (kèm đoạn gần đúng để đối chiếu) khi is_grounded
# =False — phát hiện qua Golden Set rerun sau khi vá bug tự-từ-chối (rag.py):
# message thật đổi từ NEEDS_CLARIFICATION_MESSAGE sang message này, nhưng
# thiếu snippet nay khien classify_outcome roi vao "other_abstention" chung,
# khong phan anh dung cai thien thuc te.
_NO_CONTEXT_FALLBACK_SNIPPET = "Không tìm thấy nội dung này trong tài liệu của bạn"
_NOT_GROUNDED_SNIPPET = "Chưa đủ căn cứ"
_NEEDS_TOPIC_SNIPPET = "chương/chủ đề cụ thể"
_NEEDS_ENTITIES_SNIPPET = "hai vế cần so sánh"
_ACADEMIC_INTEGRITY_SNIPPET_CANDIDATES = ["làm bài hộ", "không thể làm bài tập thay"]


def classify_outcome(resp):
    if resp is None:
        return "request_failed"
    answer = resp.get("answer", "") or ""
    if resp.get("needs_clarification"):
        if _NEEDS_TOPIC_SNIPPET in answer:
            return "needs_topic"
        if _NEEDS_ENTITIES_SNIPPET in answer:
            return "needs_entities"
        return "needs_clarification"
    if not resp.get("is_grounded"):
        if _NO_CONTEXT_SNIPPET in answer or _NO_CONTEXT_FALLBACK_SNIPPET in answer:
            return "insufficient_evidence"
        if _NOT_GROUNDED_SNIPPET in answer:
            return "unsupported_claim"
        for snip in _ACADEMIC_INTEGRITY_SNIPPET_CANDIDATES:
            if snip in answer:
                return "blocked_academic_integrity"
        return "other_abstention"
    return "grounded_answer"


_ABSTENTION_TYPE_EQUIV = {
    "insufficient_evidence": {"insufficient_evidence"},
    "unsupported_claim": {"unsupported_claim"},
    "needs_clarification": {"needs_clarification"},
    "out_of_scope": {"insufficient_evidence", "unsupported_claim", "other_abstention"},
    "needs_topic": {"needs_topic", "needs_clarification"},
    "needs_entities": {"needs_entities", "needs_clarification"},
    "blocked_academic_integrity": {"blocked_academic_integrity", "other_abstention"},
    "blocked_injection": {"other_abstention", "blocked_academic_integrity"},
    "blocked_injection_soft_trigger": {"other_abstention", "grounded_answer"},
}


def score_case(case, resp, judge_client=None):
    result = {
        "id": case["id"], "category": case["category"],
        "actual_answer": (resp or {}).get("answer"),
        "actual_is_grounded": (resp or {}).get("is_grounded"),
        "actual_needs_clarification": (resp or {}).get("needs_clarification"),
        "actual_sources": [s.get("document_name") for s in (resp or {}).get("sources", [])],
        "checks": {},
    }
    if resp is None:
        result["checks"]["request_ok"] = False
        result["overall_pass"] = False
        return result
    result["checks"]["request_ok"] = True
    outcome = classify_outcome(resp)
    result["actual_outcome"] = outcome

    passes = []

    expected_abstention = case.get("abstention_type")
    if expected_abstention:
        allowed = _ABSTENTION_TYPE_EQUIV.get(expected_abstention, {expected_abstention})
        ok = outcome in allowed
        result["checks"]["abstention_type_match"] = ok
        passes.append(ok)

    # Bỏ qua khi case CÓ abstention_type: với các case đó, expected_answer
    # đang được dùng để MÔ TẢ đúng câu từ chối/hỏi lại mong đợi (không phải
    # một câu trả lời nội dung) — nếu không loại trừ, check này luôn mâu
    # thuẫn với abstention_type_match ở trên bất kể hệ thống trả lời gì
    # (phát hiện qua eval/rescore.py, gây sai lệch ~15 case guardrail/
    # summarize trong lần chạy 267 case đầu).
    if case.get("expected_answer") and not expected_abstention:
        ok = outcome == "grounded_answer"
        result["checks"]["grounded_as_expected"] = ok
        passes.append(ok)

        if ok and case.get("required_documents"):
            expected_files = {DOC_MAPPING[d]["file_name"] for d in case["required_documents"] if d in DOC_MAPPING}
            actual_files = set(result["actual_sources"])
            citation_ok = bool(expected_files & actual_files) if expected_files else True
            result["checks"]["citation_matches_expected_document"] = citation_ok
            passes.append(citation_ok)

        if ok and judge_client is not None:
            judge_prompt = (
                "Bạn là bộ chấm điểm. Câu hỏi: " + str(case.get("input")) + "\n"
                "Câu trả lời tham chiếu (đúng): " + str(case["expected_answer"]) + "\n"
                "Câu trả lời thực tế cần chấm: " + str(result["actual_answer"]) + "\n"
                "Câu trả lời thực tế có TRUYỀN TẢI ĐÚNG nội dung thực chất của câu trả lời tham "
                "chiếu không (không cần giống hệt câu chữ, chỉ cần đúng ý, không thiếu ý chính, "
                "không có ý sai)? Trả lời DUY NHẤT 'CÓ' hoặc 'KHÔNG'."
            )
            try:
                verdict = judge_client.complete(judge_prompt).strip().upper()
                content_ok = verdict.startswith("CÓ") or verdict.startswith("CO") or verdict.startswith("YES")
            except Exception as e:  # noqa: BLE001
                content_ok = None
                result["checks"]["judge_error"] = str(e)
            result["checks"]["content_correct_per_judge"] = content_ok
            if content_ok is not None:
                passes.append(content_ok)

    # So khong phan biet hoa/thuong — cau tra loi that co the viet hoa dau
    # cau ("Câu hỏi gợi mở...") con substring case dinh nghia lai thuong
    # ("câu hỏi gợi mở"), phat hien qua EDU-APL-005 sau khi va bug tu-tu-choi:
    # content_correct_per_judge=True nhung van fail vi khac hoa/thuong don thuan.
    actual_lower = (result["actual_answer"] or "").lower()
    for s in case.get("must_contain") or []:
        ok = s.lower() in actual_lower
        result.setdefault("must_contain_results", []).append({"substring": s, "found": ok})
        passes.append(ok)
    for s in case.get("must_not_contain") or []:
        ok = s.lower() not in actual_lower
        result.setdefault("must_not_contain_results", []).append({"substring": s, "absent": ok})
        passes.append(ok)

    result["overall_pass"] = all(passes) if passes else None
    return result


def run_conversational(case, judge_client):
    turns = case["input"]
    conversation_id = None
    last_resp = None
    for turn in turns:
        q = turn["question"] if isinstance(turn, dict) else turn
        last_resp = ask(q, conversation_id=conversation_id)
        if last_resp:
            conversation_id = last_resp.get("conversation_id")
    return score_case(case, last_resp, judge_client)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--regression-only", action="store_true",
        help="Chi chay tap con danh dau in_regression_set=true trong golden_set.jsonl "
             "(dung de kiem khong hoi quy sau khi sua code, thay cho eval/run_regression.py cu).",
    )
    parser.add_argument(
        "--out", default=None,
        help="Duong dan file ket qua (mac dinh: run_results.jsonl, hoac "
             "regression_results.jsonl khi dung --regression-only).",
    )
    args = parser.parse_args()

    with open(os.path.join(EVAL_ROOT, "golden_set.jsonl"), encoding="utf-8") as f:
        all_cases = [json.loads(line) for line in f if line.strip()]

    cases = [c for c in all_cases if c["category"] in CHAT_ASK_CATEGORIES]
    if args.regression_only:
        cases = [c for c in cases if c.get("in_regression_set")]

    default_out = "regression_results.jsonl" if args.regression_only else "run_results.jsonl"
    out_path = os.path.join(RESULTS_DIR, args.out or default_out)
    # Chi coi la "da xong" khi request_ok=True — bug thuc te: case fail vi
    # loi ha tang (Cohere het han muc, timeout...) khong duoc tinh la "da
    # xong", tranh bo qua nham khi resume (xem eval/report.md muc 6.7).
    already_done = set()
    kept_lines = []
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("checks", {}).get("request_ok") is True:
                    already_done.add(row["id"])
                    kept_lines.append(line)
        with open(out_path, "w", encoding="utf-8") as f:
            f.writelines(kept_lines)
    cases = [c for c in cases if c["id"] not in already_done]
    print(f"Resuming: {len(already_done)} cases already done, running {len(cases)} remaining.")

    judge_client = None
    try:
        from app.llm.client_factory import get_llm_client
        judge_client = get_llm_client()
    except Exception as e:  # noqa: BLE001
        print(f"WARNING: could not init judge LLM client, content-correctness checks skipped: {e}", file=sys.stderr)

    results = []
    with open(out_path, "a", encoding="utf-8") as out_f:
        for i, case in enumerate(cases, 1):
            print(f"[{i}/{len(cases)}] {case['id']} ({case['category']})...", flush=True)
            if case["category"] == "conversational":
                result = run_conversational(case, judge_client)
            else:
                resp = ask(case["input"] if isinstance(case["input"], str) else json.dumps(case["input"]))
                result = score_case(case, resp, judge_client)
            results.append(result)
            out_f.write(json.dumps(result, ensure_ascii=False) + "\n")
            out_f.flush()

    total = len(results)
    passed = sum(1 for r in results if r.get("overall_pass") is True)
    failed = sum(1 for r in results if r.get("overall_pass") is False)
    unscored = sum(1 for r in results if r.get("overall_pass") is None)
    print(f"\nDONE. total={total} passed={passed} failed={failed} unscored={unscored}")


if __name__ == "__main__":
    main()
