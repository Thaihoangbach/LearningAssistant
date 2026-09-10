"""Integration test cho POST /documents — BUG-4: giới hạn dung lượng file
phải chặn TRONG lúc ĐỌC, trước khi upload lên R2 (xem
app/routers/documents.py::upload_document). File gốc giờ lưu trên Cloudflare
R2 (app/storage.py) — patch storage.save_file để xác nhận nó KHÔNG được gọi
khi request bị từ chối, không cần MinIO thật chạy nền cho riêng test này.

Dùng Postgres THẬT cho get_db (không phải SQLite in-memory riêng) — thành
công upload chạy `background_tasks.add_task(_run_processing_job, ...)`, và
job đó tự mở SESSION RIÊNG qua `app.database.SessionLocal` (MED-1, xem
app/routers/documents.py) trỏ vào DATABASE_URL THẬT, không phải qua
get_db() bị override — 2 session khác nhau chỉ thấy cùng dữ liệu nếu cùng
trỏ vào MỘT database vật lý."""
import io
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Document, User
from app.routers import documents as documents_router
from pg_test_helpers import fresh_test_session_factory


class UploadSizeLimitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.TestingSessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        TestingSessionLocal = self.TestingSessionLocal

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

        # Document.user_id có ForeignKey("users.id") — Postgres THẬT thực thi
        # ràng buộc này (khác SQLite mặc định không ép FK), nên cần một User
        # tồn tại trước khi tạo Document. Dọn cả Document lẫn User trước (theo
        # đúng thứ tự FK) để test chạy lại nhiều lần trong cùng class không
        # đụng UNIQUE(email)/FK còn tham chiếu.
        seed_db = TestingSessionLocal()
        seed_db.query(Document).filter(Document.user_id == "alice").delete()
        seed_db.query(User).filter(User.id == "alice").delete()
        seed_db.add(User(id="alice", email="alice@test.local", display_name="Alice"))
        seed_db.commit()
        seed_db.close()

        save_patcher = patch.object(documents_router.storage, "save_file")
        self.save_file_mock = save_patcher.start()
        self.addCleanup(save_patcher.stop)

    def test_oversized_file_is_rejected_before_reaching_storage(self):
        original_max = documents_router.MAX_FILE_MB
        # Ngưỡng nhỏ để test chạy nhanh (không cần dựng file 30MB thật).
        documents_router.MAX_FILE_MB = 1
        self.addCleanup(setattr, documents_router, "MAX_FILE_MB", original_max)

        oversized = io.BytesIO(b"x" * (2 * 1024 * 1024))  # 2MB > ngưỡng 1MB

        res = self.client.post(
            "/documents",
            params={"user_id": "alice"},
            files={"file": ("bai-giang.pdf", oversized, "application/pdf")},
        )

        self.assertEqual(res.status_code, 400)
        self.assertIn("1MB", res.json()["detail"])
        # Bị chặn TRONG lúc đọc — storage.save_file() (upload lên R2) không
        # được gọi tới, không phải "upload xong rồi mới phát hiện quá lớn".
        self.save_file_mock.assert_not_called()

    def test_file_within_limit_is_saved_to_storage(self):
        content = b"%PDF-1.4 noi dung nho"

        res = self.client.post(
            "/documents",
            params={"user_id": "alice"},
            files={"file": ("bai-giang.pdf", io.BytesIO(content), "application/pdf")},
        )

        self.assertEqual(res.status_code, 200)
        self.save_file_mock.assert_called_once()
        saved_key, saved_content = self.save_file_mock.call_args.args
        self.assertTrue(saved_key.endswith(".pdf"))
        self.assertEqual(saved_content, content)

    def test_missing_filename_is_rejected_not_a_server_error(self):
        # UploadFile.filename rỗng/None (hợp lệ theo multipart spec, dù
        # TestClient/Starlette chặn từ tầng validate request trước khi vào
        # route ở ca cụ thể này) từng làm os.path.splitext(None) ném
        # TypeError bên trong route -> lộ ra thành 500 chung chung. Guard
        # `if not file.filename` chặn đúng trường hợp filename rỗng lọt được
        # tới route; khẳng định ở đây là KHÔNG BAO GIỜ 500, dù bị chặn ở tầng
        # nào trước đó.
        res = self.client.post(
            "/documents",
            params={"user_id": "alice"},
            files={"file": ("", io.BytesIO(b"data"), "application/pdf")},
        )

        self.assertLess(res.status_code, 500)


class UploadDisplayNameTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.TestingSessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        TestingSessionLocal = self.TestingSessionLocal

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

        seed_db = TestingSessionLocal()
        seed_db.query(Document).filter(Document.user_id == "bob").delete()
        seed_db.query(User).filter(User.id == "bob").delete()
        seed_db.add(User(id="bob", email="bob@test.local", display_name="Bob"))
        seed_db.commit()
        seed_db.close()

        save_patcher = patch.object(documents_router.storage, "save_file")
        self.save_file_mock = save_patcher.start()
        self.addCleanup(save_patcher.stop)

    def test_upload_stores_custom_display_name(self):
        res = self.client.post(
            "/documents",
            params={"user_id": "bob", "display_name": "Chương 3 - Chuẩn hoá dữ liệu"},
            files={"file": ("slide_ch3_v2_final.pdf", io.BytesIO(b"%PDF-1.4 noi dung"), "application/pdf")},
        )
        self.assertEqual(res.status_code, 200)

        listed = self.client.get("/documents", params={"user_id": "bob"})
        docs = listed.json()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["display_name"], "Chương 3 - Chuẩn hoá dữ liệu")
        self.assertEqual(docs[0]["file_name"], "slide_ch3_v2_final.pdf")

    def test_upload_without_display_name_leaves_it_null(self):
        res = self.client.post(
            "/documents",
            params={"user_id": "bob"},
            files={"file": ("notes.pdf", io.BytesIO(b"%PDF-1.4 noi dung"), "application/pdf")},
        )
        self.assertEqual(res.status_code, 200)

        listed = self.client.get("/documents", params={"user_id": "bob"})
        self.assertIsNone(listed.json()[0]["display_name"])


class TopicCourseScopingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.TestingSessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        from app.models import DocumentTopic, Topic

        self.db = self.TestingSessionLocal()
        self.addCleanup(self.db.close)
        # DocumentTopic có FK tới Document — phải dọn TRƯỚC khi xoá Document,
        # nếu không lần chạy test thứ hai trong class này (test order không
        # đảm bảo, và _save_outline ở test đầu đã tạo ra các dòng
        # DocumentTopic) sẽ vỡ ForeignKeyViolation khi xoá Document của carol.
        self.db.query(DocumentTopic).filter(DocumentTopic.user_id == "carol").delete()
        self.db.query(Topic).delete()
        self.db.query(Document).filter(Document.user_id == "carol").delete()
        self.db.query(User).filter(User.id == "carol").delete()
        self.db.add(User(id="carol", email="carol@test.local", display_name="Carol"))
        self.db.commit()

    def test_same_heading_in_different_courses_creates_separate_topics(self):
        from app.ingestion.outline import OutlineEntry
        from app.models import Topic

        doc_a = Document(user_id="carol", file_name="a.pdf", course_name="CSDL")
        doc_b = Document(user_id="carol", file_name="b.pdf", course_name="Mạng máy tính")
        self.db.add_all([doc_a, doc_b])
        self.db.commit()

        entries = [OutlineEntry(title="Giới thiệu", position_ref="Trang 1", order=0)]
        with patch.object(documents_router, "extract_outline", return_value=entries):
            documents_router._save_outline(self.db, doc_a.id, "carol", "/fake/a.pdf", "CSDL")
            documents_router._save_outline(self.db, doc_b.id, "carol", "/fake/b.pdf", "Mạng máy tính")

        topics = self.db.query(Topic).filter(Topic.user_id == "carol", Topic.name == "Giới thiệu").all()
        self.assertEqual(len(topics), 2)
        self.assertEqual(sorted(t.course_name for t in topics), ["CSDL", "Mạng máy tính"])

    def test_same_heading_in_same_course_reuses_one_topic(self):
        from app.ingestion.outline import OutlineEntry
        from app.models import Topic

        doc_a = Document(user_id="carol", file_name="a.pdf", course_name="CSDL")
        doc_b = Document(user_id="carol", file_name="a2.pdf", course_name="CSDL")
        self.db.add_all([doc_a, doc_b])
        self.db.commit()

        entries = [OutlineEntry(title="Giới thiệu", position_ref="Trang 1", order=0)]
        with patch.object(documents_router, "extract_outline", return_value=entries):
            documents_router._save_outline(self.db, doc_a.id, "carol", "/fake/a.pdf", "CSDL")
            documents_router._save_outline(self.db, doc_b.id, "carol", "/fake/a2.pdf", "CSDL")

        topics = self.db.query(Topic).filter(Topic.user_id == "carol", Topic.name == "Giới thiệu").all()
        self.assertEqual(len(topics), 1)


if __name__ == "__main__":
    unittest.main()
