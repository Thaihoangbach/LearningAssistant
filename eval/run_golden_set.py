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

Output: eval/run_results.jsonl (1 dòng/case, có actual response + điểm).
"""
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

BASE_URL = "http://127.0.0.1:8000"
USER_ID = "golden-eval-user"
COURSE_NAME = "GoldenSetEval"

CHAT_ASK_CATEGORIES = {
    "rag_qa", "retrieval", "grounding_citation", "abstention_clarification",
    "conversational", "decomposition", "multi_document", "compare",
    "summarize", "apply", "guardrail",
}

HERE = os.path.dirname(__file__)

with open(os.path.join(HERE, "run_doc_mapping.json"), encoding="utf-8") as f:
    DOC_MAPPING = json.load(f)
FILE_NAME_BY_DOC_ID = {v["file_name"]: k for k, v in DOC_MAPPING.items()}


def ask(question, conversation_id=None, retries=3):
    payload = {"user_id": USER_ID, "question": question, "course_name": COURSE_NAME}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    for attempt in range(retries):
        try:
            r = requests.post(f"{BASE_URL}/chat/ask", json=payload, timeout=90)
            if r.status_code == 200:
                return r.json()
            print(f"  [HTTP {r.status_code}] {r.text[:200]}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  [request error] {e}", file=sys.stderr)
        time.sleep(3 * (attempt + 1))
    return None


_NO_CONTEXT_SNIPPET = "chưa có trong tài liệu"
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
        if _NO_CONTEXT_SNIPPET in answer:
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

    if case.get("expected_answer"):
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

    for s in case.get("must_contain") or []:
        ok = s in (result["actual_answer"] or "")
        result.setdefault("must_contain_results", []).append({"substring": s, "found": ok})
        passes.append(ok)
    for s in case.get("must_not_contain") or []:
        ok = s not in (result["actual_answer"] or "")
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
    with open(os.path.join(HERE, "golden_set.jsonl"), encoding="utf-8") as f:
        all_cases = [json.loads(line) for line in f if line.strip()]

    cases = [c for c in all_cases if c["category"] in CHAT_ASK_CATEGORIES]
    print(f"Running {len(cases)} /chat/ask-based cases out of {len(all_cases)} total.")

    judge_client = None
    try:
        from app.llm.client_factory import get_llm_client
        judge_client = get_llm_client()
    except Exception as e:  # noqa: BLE001
        print(f"WARNING: could not init judge LLM client, content-correctness checks skipped: {e}", file=sys.stderr)

    results = []
    out_path = os.path.join(HERE, "run_results.jsonl")
    with open(out_path, "w", encoding="utf-8") as out_f:
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
