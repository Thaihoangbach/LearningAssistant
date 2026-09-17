"""Regression cấp branch — final review Fix 7.

Mọi test khác trong tests/ override `get_current_user` qua
`app.dependency_overrides`, nên chỉ chứng minh filter theo user_id đúng KHI ĐÃ
có identity, không chứng minh dependency thật (đọc cookie, decode JWT, tra
DB) có thực sự được wire vào route hay không. File này KHÔNG override
`get_current_user` — gọi thẳng một endpoint tiêu biểu của mỗi router đã
migrate sang `Depends(get_current_user)`, không kèm cookie, và assert 401.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

import unittest

from fastapi.testclient import TestClient

from app.main import app

# TestClient không tự gửi cookie nào trừ khi được set trước — mỗi request ở
# đây coi như một client chưa đăng nhập.
client = TestClient(app)


class AuthRequiredOnAllRoutersTest(unittest.TestCase):
    def test_documents_requires_auth(self):
        res = client.get("/documents")
        self.assertEqual(res.status_code, 401)

    def test_chat_conversations_requires_auth(self):
        res = client.get("/chat/conversations")
        self.assertEqual(res.status_code, 401)

    def test_mastery_requires_auth(self):
        res = client.get("/mastery")
        self.assertEqual(res.status_code, 401)

    def test_flashcard_due_requires_auth(self):
        res = client.get("/flashcard/due")
        self.assertEqual(res.status_code, 401)

    def test_study_plan_requires_auth(self):
        res = client.get("/study-plan", params={"course_names": "x"})
        self.assertEqual(res.status_code, 401)

    def test_profile_requires_auth(self):
        res = client.get("/profile")
        self.assertEqual(res.status_code, 401)

    def test_courses_requires_auth(self):
        res = client.get("/courses")
        self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
