import argparse
import json
import os
import shutil
import sys
import time

# Console Windows mặc định dùng cp1252, không encode được tiếng Việt khi
# print() — ép stdout/stderr sang UTF-8 để tránh UnicodeEncodeError giữa chừng.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_cli = argparse.ArgumentParser()
_cli.add_argument("--mode", choices=["hybrid_rerank", "dense_only"], default="hybrid_rerank",
                   help="Retrieval config để benchmark — xem app/retrieval/pipeline.py")
_cli.add_argument("--out", default="results.jsonl", help="Tên file kết quả trong eval/")
_cli.add_argument("--run-dir", default="_run", help="Thư mục cách ly DB/vectorstore riêng cho lần chạy này")
ARGS = _cli.parse_args()

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(EVAL_DIR)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
RUN_DIR = os.path.join(EVAL_DIR, ARGS.run_dir)

# Cách ly môi trường TRƯỚC khi import bất kỳ module app.* nào — database.py
# đọc DB_PATH từ os.environ ngay lúc import, đổi thứ tự sẽ ghi đè nhầm vào
# backend/data/ thật. EDUTUTOR_RETRIEVAL_MODE cũng phải set trước import vì
# app/retrieval/pipeline.py đọc os.environ ngay khi retrieve_chunks() chạy.
if os.path.exists(RUN_DIR):
    shutil.rmtree(RUN_DIR)
os.makedirs(RUN_DIR, exist_ok=True)
os.chdir(RUN_DIR)
os.environ["DB_PATH"] = os.path.join(RUN_DIR, "eval.db")
if ARGS.mode == "dense_only":
    os.environ["EDUTUTOR_RETRIEVAL_MODE"] = "dense_only"

sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

import google.generativeai as genai  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Attempt, MasteryScore, Quiz, QuizItem, Topic  # noqa: E402

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
JUDGE_MODEL_NAME = "gemini-3.1-flash-lite"

init_db()
client = TestClient(app)

USER_ID = "eval-user"
FRESH_USER_ID = "eval-user-fresh"  # user chưa có mastery data, dùng cho EDU-REC-002
DOCS_DIR = os.path.join(EVAL_DIR, "documents")

CORPUS = [
    ("ML_Optimization.docx", "machine_learning"),
    ("ML_DecisionTree.docx", "machine_learning"),
    ("DL_CNN.docx", "deep_learning"),
    ("DL_NeuralNetwork.docx", "deep_learning"),
]


def upload_corpus():
    doc_ids = {}
    for filename, course in CORPUS:
        path = os.path.join(DOCS_DIR, filename)
        with open(path, "rb") as f:
            resp = client.post(
                "/documents",
                params={"user_id": USER_ID, "course_name": course},
                files={
                    "file": (
                        filename,
                        f,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        resp.raise_for_status()
        doc_ids[filename] = resp.json()["document_id"]
        print(f"[upload] {filename} -> {resp.json()}")
    return doc_ids


def wait_ready(document_id, timeout=180):
    start = time.time()
    while time.time() - start < timeout:
        resp = client.get("/documents", params={"user_id": USER_ID})
        for d in resp.json():
            if d["id"] == document_id:
                if d["status"] == "sẵn sàng":
                    return
                if d["status"] == "lỗi":
                    raise RuntimeError(f"Document {document_id} lỗi: {d['error_reason']}")
        time.sleep(1)
    raise TimeoutError(f"Document {document_id} chưa sẵn sàng sau {timeout}s")


def seed_mastery(user_id, topic_scores, course_name="machine_learning"):
    """Tạo trực tiếp Topic + MasteryScore trong DB để chuẩn bị tình huống
    cho case Recommendation/Planning — KHÔNG tốn lượt gọi Gemini cho việc
    dựng bối cảnh (chỉ eval đúng hành vi recommendation/planner thật)."""
    db = SessionLocal()
    try:
        for topic_name, score in topic_scores.items():
            topic = db.query(Topic).filter(Topic.user_id == user_id, Topic.name == topic_name).first()
            if not topic:
                topic = Topic(user_id=user_id, name=topic_name, course_name=course_name)
                db.add(topic)
                db.commit()
            existing = db.query(MasteryScore).filter(MasteryScore.user_id == user_id, MasteryScore.topic_id == topic.id).first()
            if existing:
                existing.score = score
            else:
                db.add(MasteryScore(user_id=user_id, topic_id=topic.id, score=score))
            db.commit()
    finally:
        db.close()


def llm_judge(case, actual_output):
    prompt = (
        "Bạn là giám khảo đánh giá chất lượng một hệ thống trợ lý học tập AI. "
        "Đánh giá NGHIÊM KHẮC và khách quan — không vì hệ thống 'có cố gắng trả lời' "
        "mà cho PASS nếu nội dung không thực sự đáp ứng tiêu chí.\n\n"
        f"Tình huống (input): {json.dumps(case['input'], ensure_ascii=False)}\n"
        f"Ngữ cảnh: {json.dumps(case.get('context', {}), ensure_ascii=False)}\n"
        f"Hành vi mong đợi: {json.dumps(case['expected_behavior'], ensure_ascii=False)}\n\n"
        f"Đầu ra THẬT của hệ thống:\n{actual_output}\n\n"
        "Với MỖI tiêu chí dưới đây, chấm 'PASS' nếu đầu ra thoả mãn, 'FAIL' nếu không, "
        "kèm 1 câu lý do ngắn gọn bằng tiếng Việt.\n"
        f"Tiêu chí: {json.dumps(case['assertion'], ensure_ascii=False)}\n\n"
        "Trả lời DUY NHẤT bằng JSON hợp lệ, dạng: "
        '{"tên_tiêu_chí": {"verdict": "PASS hoặc FAIL", "reason": "..."}}'
    )
    model = genai.GenerativeModel(JUDGE_MODEL_NAME)
    last_error = None
    for attempt in range(4):
        try:
            resp = model.generate_content(prompt)
            break
        except Exception as e:  # noqa: BLE001 - free tier hay bị 429, cần retry có backoff
            last_error = e
            if "429" in str(e) and attempt < 3:
                time.sleep(2**attempt * 8)  # 8s, 16s, 32s
                continue
            raise
    else:
        raise last_error
    text = resp.text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def run_case(case, doc_ids):
    cid = case["id"]
    feature = case["feature"]
    actual = {}
    rule_checks = {}

    try:
        if case["category"] == "RAG_QA" or (case["category"] == "PERSONALIZATION"):
            payload = {"user_id": USER_ID, "question": case["input"]["query"]}
            if case["input"].get("level"):
                payload["level"] = case["input"]["level"]
            resp = client.post("/chat/ask", json=payload)
            resp.raise_for_status()
            data = resp.json()
            actual = data
            actual_text = f"answer: {data['answer']}\nis_grounded: {data['is_grounded']}\nsources: {data['sources']}"

        elif case["category"] == "ASSESSMENT":
            doc_name = case["input"]["document"]
            payload = {
                "user_id": USER_ID,
                "document_id": doc_ids[doc_name],
                "num_questions": case["input"].get("num_questions", 5),
            }
            if feature == "quiz_difficulty":
                payload_b = dict(payload, difficulty="beginner")
                payload_a = dict(payload, difficulty="advanced")
                resp_b = client.post("/quiz/generate", json=payload_b)
                resp_b.raise_for_status()
                resp_a = client.post("/quiz/generate", json=payload_a)
                resp_a.raise_for_status()
                data_b, data_a = resp_b.json(), resp_a.json()
                actual = {"beginner": data_b, "advanced": data_a}
                actual_text = (
                    f"BEGINNER quiz ({len(data_b['items'])} câu): "
                    f"{[i['question'] for i in data_b['items']]}\n\n"
                    f"ADVANCED quiz ({len(data_a['items'])} câu): "
                    f"{[i['question'] for i in data_a['items']]}"
                )
                rule_checks["questions_are_grounded"] = "N/A - qua verifier per-item ở backend, không verify lại ở đây"
            else:
                resp = client.post("/quiz/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
                actual = data
                rule_checks["question_count_equals_5"] = len(data["items"]) == 5
                actual_text = f"quiz_id: {data['quiz_id']}\nsố câu: {len(data['items'])}\ncâu hỏi: {[i['question'] for i in data['items']]}"

        elif case["category"] == "FLASHCARD":
            doc_name = case["input"]["document"]
            payload = {"user_id": USER_ID, "document_id": doc_ids[doc_name], "num_cards": case["input"].get("num_cards", 10)}
            resp = client.post("/flashcard/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            actual = data
            rule_checks["front_and_back_not_empty"] = all(i["front"].strip() and i["back"].strip() for i in data["items"])
            actual_text = f"số thẻ: {len(data['items'])}\n" + "\n".join(f"- {i['front']} => {i['back']}" for i in data["items"])

        elif case["category"] == "RECOMMENDATION":
            if cid == "EDU-REC-002":  # user hoàn toàn mới, chưa có tài liệu -> vẫn phải qua được nhánh recommendation
                resp = client.post("/chat/ask", json={"user_id": FRESH_USER_ID, "question": case["input"]["query"]})
            else:
                rec_seed = {
                    "EDU-REC-001": {"Backpropagation": 0.3, "Decision Tree": 0.9},
                    "EDU-REC-003": {"Vanishing Gradient": 0.15, "CNN": 0.7, "Decision Tree": 0.8},
                }
                rec_user = f"{USER_ID}-{cid}"
                seed_mastery(rec_user, rec_seed[cid])
                resp = client.post("/chat/ask", json={"user_id": rec_user, "question": case["input"]["query"]})
            resp.raise_for_status()
            data = resp.json()
            actual = data
            actual_text = f"answer: {data['answer']}"

        elif case["category"] == "PLANNING":
            # Mỗi case Planning dùng user_id RIÊNG để không bị nhiễu bởi topic
            # tự sinh từ các case ASSESSMENT/FLASHCARD/RECOMMENDATION khác
            # (bug đã gặp ở vòng chạy trước).
            plan_seed = {
                "EDU-PLAN-001": {"Backpropagation": 0.3, "CNN": 0.6, "Decision Tree": 0.9, "Gradient Descent": 0.5},
                "EDU-PLAN-002": {"Vanishing Gradient": 0.1, "Convolution": 0.95},
                "EDU-PLAN-003": {"Backpropagation": 0.2, "Pooling": 0.9},
            }
            plan_user = f"{USER_ID}-{cid}"
            seed_mastery(plan_user, plan_seed[cid])
            resp = client.get("/study-plan", params={"user_id": plan_user, "days": case["input"]["days"]})
            resp.raise_for_status()
            data = resp.json()
            actual = data
            max_day = max((d["day"] for d in data["days"]), default=0)
            rule_checks["deadline_constraint_is_satisfied"] = max_day <= case["input"]["days"]
            rule_checks["plan_is_non_empty"] = len(data["days"]) > 0
            weak_topic_by_case = {"EDU-PLAN-002": "Vanishing Gradient", "EDU-PLAN-003": "Backpropagation"}
            if cid in weak_topic_by_case:
                first_day_topics = data["days"][0]["topics"] if data["days"] else []
                rule_checks["weak_topics_receive_higher_priority"] = weak_topic_by_case[cid] in first_day_topics
            actual_text = json.dumps(data, ensure_ascii=False)

        elif case["category"] == "ANALYTICS":
            analytics_doc = doc_ids["ML_DecisionTree.docx"] if cid == "EDU-ANLY-001" else doc_ids["DL_CNN.docx"]
            gen_resp = client.post(
                "/quiz/generate",
                json={"user_id": USER_ID, "document_id": analytics_doc, "num_questions": 3},
            )
            gen_resp.raise_for_status()
            item_id = gen_resp.json()["items"][0]["id"]

            db = SessionLocal()
            try:
                quiz_item = db.query(QuizItem).filter(QuizItem.id == item_id).first()
                correct_answer = quiz_item.correct_answer
                topic_id = quiz_item.topic_id
            finally:
                db.close()

            before_resp = client.get("/mastery", params={"user_id": USER_ID})
            before_score = next((t["score"] for t in before_resp.json()["topics"] if t["topic_id"] == topic_id), None)

            if cid == "EDU-ANLY-002":
                selected_answer = "___đáp_án_cố_tình_sai___"  # không khớp bất kỳ option nào -> chắc chắn is_correct=False
            else:
                selected_answer = correct_answer
            submit_resp = client.post(
                "/quiz/submit", json={"user_id": USER_ID, "quiz_item_id": item_id, "selected_answer": selected_answer}
            )
            submit_resp.raise_for_status()
            submit_data = submit_resp.json()

            after_resp = client.get("/mastery", params={"user_id": USER_ID})
            after_score = next((t["score"] for t in after_resp.json()["topics"] if t["topic_id"] == topic_id), None)

            actual = {"submit": submit_data, "before_score": before_score, "after_score": after_score}
            rule_checks["mastery_score_updates_immediately"] = after_score is not None and after_score != before_score
            if cid == "EDU-ANLY-002":
                rule_checks["mastery_score_reflects_correct_answer"] = submit_data["is_correct"] is False and (after_score if after_score is not None else 1) <= (before_score if before_score is not None else 1)
            else:
                rule_checks["mastery_score_reflects_correct_answer"] = submit_data["is_correct"] is True and (after_score or 0) >= (before_score or 0)
            actual_text = f"is_correct: {submit_data['is_correct']}\nbefore_score: {before_score}\nafter_score: {after_score}"

        elif case["category"] == "SAFETY":
            resp = client.post("/chat/ask", json={"user_id": USER_ID, "question": case["input"]["query"]})
            resp.raise_for_status()
            data = resp.json()
            actual = data
            actual_text = f"answer: {data['answer']}\nis_grounded: {data['is_grounded']}"

        else:
            raise ValueError(f"Không biết cách chạy category {case['category']}")

    except Exception as e:  # noqa: BLE001 - ghi lại lỗi thật, không để crash cả batch
        return {
            "id": cid,
            "status": "ERROR",
            "error": f"{type(e).__name__}: {e}",
            "actual": None,
            "rule_checks": {},
            "judge": {},
        }

    try:
        judge_result = llm_judge(case, actual_text)
    except Exception as e:  # noqa: BLE001
        judge_result = {"_judge_error": f"{type(e).__name__}: {e}"}

    return {
        "id": cid,
        "status": "RAN",
        "actual": actual,
        "actual_text": actual_text,
        "rule_checks": rule_checks,
        "judge": judge_result,
    }


def main():
    print("=== Upload corpus ===")
    doc_ids = upload_corpus()
    for filename, doc_id in doc_ids.items():
        wait_ready(doc_id)
        print(f"[ready] {filename}")

    cases = []
    with open(os.path.join(EVAL_DIR, "golden_set.jsonl"), encoding="utf-8") as f:
        for line in f:
            cases.append(json.loads(line))

    results = []
    for i, case in enumerate(cases, start=1):
        print(f"\n=== [{i}/{len(cases)}] {case['id']} ({case['category']}/{case['feature']}) ===")
        result = run_case(case, doc_ids)
        print(json.dumps(result, ensure_ascii=False, indent=2)[:1500])
        results.append(result)
        time.sleep(8)  # tránh dồn quá nhiều request/phút vào Gemini free tier (15 RPM)

    out_path = os.path.join(EVAL_DIR, ARGS.out)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n=== Done ({ARGS.mode}). Wrote {len(results)} results to {out_path} ===")


if __name__ == "__main__":
    main()
