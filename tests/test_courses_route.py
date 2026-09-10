"""Integration test cho GET/PUT/DELETE /courses/... — danh sách môn học (từ
Document.course_name) và ngày thi riêng từng môn (CourseDeadline), dùng cho
autocomplete lúc upload và lập kế hoạch ôn đa môn (app/routers/study_plan.py).
"""
import os
import sys
import unittest
import uuid
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import CourseDeadline, Document, User
from pg_test_helpers import fresh_test_session_factory


class CoursesRouteTest(unittest.TestCase):
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

        self.user_id = str(uuid.uuid4())
        db = self.SessionLocal()
        try:
            db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", display_name="Hoa"))
            db.flush()
            db.add(Document(user_id=self.user_id, file_name="a.pdf", course_name="CSDL", status="sẵn sàng"))
            db.add(Document(user_id=self.user_id, file_name="b.pdf", course_name="CSDL", status="sẵn sàng"))
            db.add(Document(user_id=self.user_id, file_name="c.pdf", course_name="Mạng máy tính", status="sẵn sàng"))
            db.add(Document(user_id=self.user_id, file_name="loose.pdf", course_name=None, status="sẵn sàng"))
            db.commit()
        finally:
            db.close()

    def test_lists_distinct_course_names_excluding_null(self):
        res = self.client.get("/courses", params={"user_id": self.user_id})
        self.assertEqual(res.status_code, 200)
        names = [c["course_name"] for c in res.json()["courses"]]
        self.assertEqual(sorted(names), ["CSDL", "Mạng máy tính"])

    def test_course_without_exam_date_has_null_exam_date(self):
        res = self.client.get("/courses", params={"user_id": self.user_id})
        by_name = {c["course_name"]: c["exam_date"] for c in res.json()["courses"]}
        self.assertIsNone(by_name["CSDL"])

    def test_set_exam_date_then_list_reflects_it(self):
        put_res = self.client.put(
            "/courses/CSDL/exam-date",
            json={"user_id": self.user_id, "exam_date": "2026-12-20"},
        )
        self.assertEqual(put_res.status_code, 200)

        res = self.client.get("/courses", params={"user_id": self.user_id})
        by_name = {c["course_name"]: c["exam_date"] for c in res.json()["courses"]}
        self.assertEqual(by_name["CSDL"], "2026-12-20")

    def test_setting_exam_date_twice_updates_instead_of_duplicating(self):
        self.client.put("/courses/CSDL/exam-date", json={"user_id": self.user_id, "exam_date": "2026-12-20"})
        self.client.put("/courses/CSDL/exam-date", json={"user_id": self.user_id, "exam_date": "2026-12-25"})

        db = self.SessionLocal()
        try:
            rows = db.query(CourseDeadline).filter(
                CourseDeadline.user_id == self.user_id, CourseDeadline.course_name == "CSDL"
            ).all()
        finally:
            db.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].exam_date, date(2026, 12, 25))

    def test_delete_exam_date_removes_it(self):
        self.client.put("/courses/CSDL/exam-date", json={"user_id": self.user_id, "exam_date": "2026-12-20"})

        del_res = self.client.delete("/courses/CSDL/exam-date", params={"user_id": self.user_id})
        self.assertEqual(del_res.status_code, 200)

        res = self.client.get("/courses", params={"user_id": self.user_id})
        by_name = {c["course_name"]: c["exam_date"] for c in res.json()["courses"]}
        self.assertIsNone(by_name["CSDL"])

    def test_delete_exam_date_that_was_never_set_is_404(self):
        res = self.client.delete("/courses/Mạng máy tính/exam-date", params={"user_id": self.user_id})
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
