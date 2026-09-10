"""_build_study_plan_result (app/routers/chat.py) — quyết định KHI NÀO nhường
lịch ôn nhiều môn sang trang Kế hoạch ôn thay vì cố tính trong chat (spec §10,
docs/superpowers/specs/2026-09-09-study-plan-multi-course-design.md). Test
trực tiếp hàm module-level thay vì dựng toàn bộ /chat/ask (guardrail + LLM
thật) chỉ để kiểm tra một nhánh rẽ."""
import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from app.models import Document, Topic, User
from app.routers.chat import _build_study_plan_result, _mentions_multiple_known_courses
from pg_test_helpers import fresh_test_session_factory


class MentionsMultipleKnownCoursesTest(unittest.TestCase):
    def test_zero_or_one_course_mentioned_is_false(self):
        self.assertFalse(
            _mentions_multiple_known_courses("còn 5 ngày nữa thi CSDL", ["CSDL", "Mạng máy tính"])
        )

    def test_two_courses_mentioned_is_true(self):
        self.assertTrue(
            _mentions_multiple_known_courses(
                "CSDL thi trước, Mạng máy tính thi sau, ôn sao đây", ["CSDL", "Mạng máy tính"]
            )
        )


class BuildStudyPlanResultRedirectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        self.db = self.SessionLocal()
        self.addCleanup(self.db.close)
        self.user_id = str(uuid.uuid4())
        self.db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", display_name="Fiona"))
        self.db.flush()
        self.db.add(Document(user_id=self.user_id, file_name="a.pdf", course_name="CSDL", status="sẵn sàng"))
        self.db.add(Document(user_id=self.user_id, file_name="b.pdf", course_name="Mạng máy tính", status="sẵn sàng"))
        self.db.add(Topic(user_id=self.user_id, name="Chuẩn hoá dữ liệu", course_name="CSDL"))
        self.db.commit()

    def test_multiple_days_mentioned_flag_triggers_redirect(self):
        result = _build_study_plan_result(
            self.db, self.user_id, None, days=5,
            question="5 ngày nữa thi, 10 ngày nữa thi", multiple_days_mentioned=True,
        )
        self.assertIn("trang Kế hoạch ôn", result.answer)

    def test_mentioning_two_known_courses_triggers_redirect_even_without_days_flag(self):
        result = _build_study_plan_result(
            self.db, self.user_id, None, days=5,
            question="CSDL và Mạng máy tính tôi nên ôn sao", multiple_days_mentioned=False,
        )
        self.assertIn("trang Kế hoạch ôn", result.answer)

    def test_single_course_question_is_not_redirected(self):
        result = _build_study_plan_result(
            self.db, self.user_id, None, days=5,
            question="còn 5 ngày nữa thi CSDL, ôn sao", multiple_days_mentioned=False,
        )
        self.assertNotIn("trang Kế hoạch ôn", result.answer)
        self.assertIn("Chuẩn hoá dữ liệu", result.answer)


if __name__ == "__main__":
    unittest.main()
