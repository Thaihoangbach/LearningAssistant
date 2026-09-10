"""Integration test cho POST /study-plan/review và GET /study-plan (đa môn,
mỗi môn một ngày thi riêng — xem docs/superpowers/specs/2026-09-09-study-plan-
multi-course-design.md). Router này trước đây (single course_name + days
chung) chưa có test nào."""
import os
import sys
import unittest
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import (
    CourseDeadline,
    Document,
    DocumentTopic,
    FlashcardItem,
    FlashcardReview,
    FlashcardSet,
    MasteryScore,
    MemoryEvent,
    Topic,
    User,
)
from pg_test_helpers import fresh_test_session_factory


def _fake_embed_query(text):
    return np.zeros(1024, dtype="float32")


class MarkTopicReviewedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

        embed_patcher = patch("app.ingestion.embedder.embed_query", side_effect=_fake_embed_query)
        embed_patcher.start()
        self.addCleanup(embed_patcher.stop)

        self.user_id = str(uuid.uuid4())
        self.topic_id = str(uuid.uuid4())
        self.other_course_topic_id = str(uuid.uuid4())

        db = self.SessionLocal()
        try:
            db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", display_name="Dana"))
            db.flush()
            db.add(Topic(id=self.topic_id, user_id=self.user_id, name="Chuẩn hoá dữ liệu", course_name="CSDL"))
            # Cùng TÊN, khác MÔN — Topic khoá theo (user_id, course_name, name)
            # nên đây là một Topic hợp lệ khác, không phải bản trùng.
            db.add(
                Topic(
                    id=self.other_course_topic_id,
                    user_id=self.user_id,
                    name="Chuẩn hoá dữ liệu",
                    course_name="Mạng máy tính",
                )
            )
            db.commit()
        finally:
            db.close()

    def test_marking_known_topic_reviewed_returns_200(self):
        res = self.client.post(
            "/study-plan/review",
            json={"user_id": self.user_id, "topic_name": "Chuẩn hoá dữ liệu", "course_name": "CSDL"},
        )
        self.assertEqual(res.status_code, 200)

        db = self.SessionLocal()
        try:
            events = (
                db.query(MemoryEvent)
                .filter(MemoryEvent.user_id == self.user_id, MemoryEvent.event_type == "topic_reviewed_manual")
                .all()
            )
        finally:
            db.close()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].topic_id, self.topic_id)

    def test_marking_unknown_topic_is_rejected(self):
        res = self.client.post(
            "/study-plan/review",
            json={"user_id": self.user_id, "topic_name": "Chủ đề không tồn tại", "course_name": "CSDL"},
        )
        self.assertEqual(res.status_code, 404)

    def test_course_name_disambiguates_same_named_topic_in_another_course(self):
        """Đánh dấu "Chuẩn hoá dữ liệu" của môn Mạng máy tính phải gắn
        MemoryEvent vào ĐÚNG Topic của môn đó, không phải Topic trùng tên bên
        CSDL — trước đây lookup chỉ theo tên nên không phân biệt được."""
        res = self.client.post(
            "/study-plan/review",
            json={
                "user_id": self.user_id,
                "topic_name": "Chuẩn hoá dữ liệu",
                "course_name": "Mạng máy tính",
            },
        )
        self.assertEqual(res.status_code, 200)

        db = self.SessionLocal()
        try:
            events = (
                db.query(MemoryEvent)
                .filter(MemoryEvent.user_id == self.user_id, MemoryEvent.event_type == "topic_reviewed_manual")
                .all()
            )
        finally:
            db.close()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].topic_id, self.other_course_topic_id)

    def test_unknown_course_for_a_known_topic_name_is_rejected(self):
        res = self.client.post(
            "/study-plan/review",
            json={
                "user_id": self.user_id,
                "topic_name": "Chuẩn hoá dữ liệu",
                "course_name": "Môn không tồn tại",
            },
        )
        self.assertEqual(res.status_code, 404)


class MultiCourseStudyPlanRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

        embed_patcher = patch("app.ingestion.embedder.embed_query", side_effect=_fake_embed_query)
        embed_patcher.start()
        self.addCleanup(embed_patcher.stop)

        self.user_id = str(uuid.uuid4())
        db = self.SessionLocal()
        try:
            db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", display_name="Erin"))
            db.flush()
            db.add(Topic(user_id=self.user_id, name="CSDL yếu", course_name="CSDL"))
            db.add(Topic(user_id=self.user_id, name="MMT yếu", course_name="Mạng máy tính"))
            db.commit()
        finally:
            db.close()

    def _set_exam_date(self, course_name: str, days_from_now: int):
        db = self.SessionLocal()
        try:
            db.add(
                CourseDeadline(
                    user_id=self.user_id,
                    course_name=course_name,
                    exam_date=date.today() + timedelta(days=days_from_now),
                )
            )
            db.commit()
        finally:
            db.close()

    def test_missing_exam_date_for_a_selected_course_is_rejected(self):
        res = self.client.get(
            "/study-plan", params={"user_id": self.user_id, "course_names": ["CSDL"]}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("CSDL", res.json()["detail"])

    def test_plan_only_includes_selected_courses(self):
        self._set_exam_date("CSDL", 3)
        res = self.client.get(
            "/study-plan", params={"user_id": self.user_id, "course_names": ["CSDL"]}
        )
        self.assertEqual(res.status_code, 200)
        all_courses = {t["course_name"] for d in res.json()["days"] for t in d["topics"]}
        self.assertEqual(all_courses, {"CSDL"})

    def test_two_courses_with_same_deadline_can_share_a_day(self):
        self._set_exam_date("CSDL", 3)
        self._set_exam_date("Mạng máy tính", 3)
        res = self.client.get(
            "/study-plan",
            params={"user_id": self.user_id, "course_names": ["CSDL", "Mạng máy tính"]},
        )
        self.assertEqual(res.status_code, 200)
        day1_courses = {t["course_name"] for t in res.json()["days"][0]["topics"]}
        self.assertEqual(day1_courses, {"CSDL", "Mạng máy tính"})

    def test_course_past_exam_date_is_dropped_silently(self):
        self._set_exam_date("CSDL", -1)  # thi hôm qua
        res = self.client.get(
            "/study-plan", params={"user_id": self.user_id, "course_names": ["CSDL"]}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["days"], [])

    def test_topic_marked_reviewed_today_stays_visible_but_flagged(self):
        """Chủ đề đã đánh dấu "đã ôn xong" hôm nay KHÔNG biến mất khỏi ngày 1
        nữa — nó vẫn ở trong danh sách, chỉ mang cờ reviewed_today=True để
        frontend tự quyết định cách hiển thị (đẩy xuống cuối, khoá nút)."""
        self._set_exam_date("CSDL", 3)
        mark_res = self.client.post(
            "/study-plan/review",
            json={"user_id": self.user_id, "topic_name": "CSDL yếu", "course_name": "CSDL"},
        )
        self.assertEqual(mark_res.status_code, 200)

        res = self.client.get(
            "/study-plan", params={"user_id": self.user_id, "course_names": ["CSDL"]}
        )
        days = res.json()["days"]
        self.assertGreaterEqual(len(days), 1)
        self.assertEqual(days[0]["day"], 1)
        day1_by_name = {t["name"]: t for t in days[0]["topics"]}
        self.assertIn("CSDL yếu", day1_by_name)
        self.assertTrue(day1_by_name["CSDL yếu"]["reviewed_today"])

    def test_reviewed_today_flag_is_false_when_not_marked(self):
        self._set_exam_date("CSDL", 3)
        res = self.client.get(
            "/study-plan", params={"user_id": self.user_id, "course_names": ["CSDL"]}
        )
        day1_by_name = {t["name"]: t for t in res.json()["days"][0]["topics"]}
        self.assertFalse(day1_by_name["CSDL yếu"]["reviewed_today"])

    def test_reviewed_today_topic_keeps_its_own_day_assignment(self):
        """"Đã ôn hôm nay" chỉ gắn cờ hiển thị, không đổi chỗ chủ đề nào — xác
        nhận việc gắn cờ diễn ra SAU generate_multi_course_plan, không phải
        lọc khỏi input truyền vào hàm đó.

        "CSDL yếu" (điểm 0.1, đã đánh dấu ôn hôm nay) và "CSDL cần ôn" (điểm
        0.2) đều yếu, không ai có order_index nên xếp hạng theo điểm — "CSDL
        yếu" đứng trước (i=0) -> ngày 1 (round-robin days=2), "CSDL cần ôn"
        đứng sau (i=1) -> ngày 2. Nếu code (SAI) lọc "CSDL yếu" khỏi input
        TRƯỚC khi gọi generate_multi_course_plan, "CSDL cần ôn" sẽ là chủ đề
        DUY NHẤT còn lại và rơi vào ngày 1 (i=0) thay vì ngày 2."""
        self._set_exam_date("CSDL", 2)  # days_left = 2

        db = self.SessionLocal()
        try:
            topic_a = (
                db.query(Topic)
                .filter(Topic.user_id == self.user_id, Topic.name == "CSDL yếu", Topic.course_name == "CSDL")
                .first()
            )
            db.add(MasteryScore(user_id=self.user_id, topic_id=topic_a.id, score=0.1))
            topic_b = Topic(user_id=self.user_id, name="CSDL cần ôn", course_name="CSDL")
            db.add(topic_b)
            db.flush()
            db.add(MasteryScore(user_id=self.user_id, topic_id=topic_b.id, score=0.2))
            db.commit()
        finally:
            db.close()

        mark_res = self.client.post(
            "/study-plan/review",
            json={"user_id": self.user_id, "topic_name": "CSDL yếu", "course_name": "CSDL"},
        )
        self.assertEqual(mark_res.status_code, 200)

        res = self.client.get(
            "/study-plan", params={"user_id": self.user_id, "course_names": ["CSDL"]}
        )
        days = res.json()["days"]
        self.assertEqual(len(days), 2)
        day1_by_name = {t["name"]: t for t in days[0]["topics"]}
        day2_names = {t["name"] for t in days[1]["topics"]}

        # "CSDL yếu" ở đúng ngày round-robin gán (ngày 1), chỉ khác là mang
        # cờ reviewed_today=True — không biến mất, không "chuyển" sang ngày 2.
        self.assertIn("CSDL yếu", day1_by_name)
        self.assertTrue(day1_by_name["CSDL yếu"]["reviewed_today"])
        self.assertNotIn("CSDL yếu", day2_names)
        # "CSDL cần ôn" KHÔNG bị đẩy lên thế chỗ ngày 1, vẫn đúng ngày 2.
        self.assertNotIn("CSDL cần ôn", day1_by_name)
        self.assertIn("CSDL cần ôn", day2_names)

    def test_far_future_exam_date_is_clamped_to_max_days_left(self):
        self._set_exam_date("CSDL", 365 * 10)  # thi 10 năm nữa
        res = self.client.get(
            "/study-plan", params={"user_id": self.user_id, "course_names": ["CSDL"]}
        )
        self.assertEqual(res.status_code, 200)
        days = res.json()["days"]
        self.assertLessEqual(len(days), 61)
        self.assertGreater(len(days), 0)

    def test_document_id_resolves_from_matching_document_topic(self):
        """Chủ đề khớp tên với một DocumentTopic của CHÍNH môn đó phải trả về
        đúng document_id — dùng để tự điền sẵn tài liệu lúc bấm "Làm quiz"/
        "Ôn flashcard" từ lịch."""
        self._set_exam_date("CSDL", 3)
        db = self.SessionLocal()
        try:
            doc = Document(user_id=self.user_id, file_name="slide1.pdf", course_name="CSDL")
            db.add(doc)
            db.flush()
            db.add(DocumentTopic(document_id=doc.id, user_id=self.user_id, title="CSDL yếu", order_index=0))
            db.commit()
            doc_id = doc.id
        finally:
            db.close()

        res = self.client.get(
            "/study-plan", params={"user_id": self.user_id, "course_names": ["CSDL"]}
        )
        day1_by_name = {t["name"]: t for t in res.json()["days"][0]["topics"]}
        self.assertEqual(day1_by_name["CSDL yếu"]["document_id"], doc_id)

    def test_document_id_is_none_without_a_matching_document_topic(self):
        self._set_exam_date("CSDL", 3)
        res = self.client.get(
            "/study-plan", params={"user_id": self.user_id, "course_names": ["CSDL"]}
        )
        day1_by_name = {t["name"]: t for t in res.json()["days"][0]["topics"]}
        self.assertIsNone(day1_by_name["CSDL yếu"]["document_id"])

    def test_document_id_does_not_leak_across_courses_with_same_topic_title(self):
        """Một DocumentTopic cùng tên ở tài liệu của MÔN KHÁC không được gán
        nhầm document_id cho chủ đề của môn đang lập kế hoạch."""
        self._set_exam_date("CSDL", 3)
        db = self.SessionLocal()
        try:
            other_doc = Document(user_id=self.user_id, file_name="slide-mmt.pdf", course_name="Mạng máy tính")
            db.add(other_doc)
            db.flush()
            # Cùng tiêu đề "CSDL yếu" nhưng thuộc tài liệu của môn khác.
            db.add(
                DocumentTopic(document_id=other_doc.id, user_id=self.user_id, title="CSDL yếu", order_index=0)
            )
            db.commit()
        finally:
            db.close()

        res = self.client.get(
            "/study-plan", params={"user_id": self.user_id, "course_names": ["CSDL"]}
        )
        day1_by_name = {t["name"]: t for t in res.json()["days"][0]["topics"]}
        self.assertIsNone(day1_by_name["CSDL yếu"]["document_id"])

    def test_duplicated_course_name_in_query_params_does_not_double_count(self):
        self._set_exam_date("CSDL", 3)
        res_dup = self.client.get(
            "/study-plan",
            params={"user_id": self.user_id, "course_names": ["CSDL", "CSDL"]},
        )
        res_single = self.client.get(
            "/study-plan", params={"user_id": self.user_id, "course_names": ["CSDL"]}
        )
        self.assertEqual(res_dup.status_code, 200)
        self.assertEqual(res_dup.json(), res_single.json())

        dup_topic_count = sum(len(d["topics"]) for d in res_dup.json()["days"])
        single_topic_count = sum(len(d["topics"]) for d in res_single.json()["days"])
        self.assertEqual(dup_topic_count, single_topic_count)


class StudyPlanReasonFieldTest(unittest.TestCase):
    """GET /study-plan (Phase 1, Learning Loop): mỗi chủ đề trả thêm
    `recommended_action`/`reason` từ app/services/learning_policy.py, tính
    từ Learning State (app/services/learning_state.py) — Comprehension đọc
    MasteryScore, Retention đọc FlashcardReview."""

    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

        embed_patcher = patch("app.ingestion.embedder.embed_query", side_effect=_fake_embed_query)
        embed_patcher.start()
        self.addCleanup(embed_patcher.stop)

        self.user_id = str(uuid.uuid4())
        db = self.SessionLocal()
        try:
            db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", display_name="Fiona"))
            db.flush()
            db.add(
                CourseDeadline(
                    user_id=self.user_id, course_name="CSDL", exam_date=date.today() + timedelta(days=3)
                )
            )
            self.topic_weak = Topic(user_id=self.user_id, name="CSDL yếu", course_name="CSDL")
            self.topic_fresh = Topic(user_id=self.user_id, name="CSDL mới", course_name="CSDL")
            db.add_all([self.topic_weak, self.topic_fresh])
            db.commit()
            self.topic_weak_id = self.topic_weak.id
        finally:
            db.close()

    def _get_plan(self):
        res = self.client.get(
            "/study-plan", params={"user_id": self.user_id, "course_names": ["CSDL"]}
        )
        self.assertEqual(res.status_code, 200)
        by_name = {t["name"]: t for d in res.json()["days"] for t in d["topics"]}
        return by_name

    def test_weak_comprehension_recommends_quiz_with_a_vietnamese_reason(self):
        db = self.SessionLocal()
        try:
            db.add(MasteryScore(user_id=self.user_id, topic_id=self.topic_weak_id, score=0.1))
            db.commit()
        finally:
            db.close()

        by_name = self._get_plan()
        self.assertEqual(by_name["CSDL yếu"]["recommended_action"], "quiz")
        self.assertIn("hiểu", by_name["CSDL yếu"]["reason"])

    def test_no_data_recommends_learn(self):
        by_name = self._get_plan()
        self.assertEqual(by_name["CSDL mới"]["recommended_action"], "learn")
        self.assertTrue(by_name["CSDL mới"]["reason"])

    def test_strong_topic_has_no_recommended_action(self):
        db = self.SessionLocal()
        try:
            db.add(MasteryScore(user_id=self.user_id, topic_id=self.topic_weak_id, score=0.9))
            doc = Document(user_id=self.user_id, file_name="a.pdf", course_name="CSDL")
            db.add(doc)
            db.flush()
            fset = FlashcardSet(user_id=self.user_id, document_id=doc.id)
            db.add(fset)
            db.flush()
            item = FlashcardItem(flashcard_set_id=fset.id, topic_id=self.topic_weak_id, front="f", back="b")
            db.add(item)
            db.flush()
            db.add(
                FlashcardReview(
                    user_id=self.user_id,
                    flashcard_item_id=item.id,
                    rating="easy",
                    reviewed_at=datetime.utcnow(),
                    interval_days=4,
                    ease=2.6,
                    next_due_at=datetime.utcnow() + timedelta(days=4),
                )
            )
            db.commit()
        finally:
            db.close()

        by_name = self._get_plan()
        self.assertIsNone(by_name["CSDL yếu"]["recommended_action"])


if __name__ == "__main__":
    unittest.main()
