"""Test THẬT trên MinIO (S3-compatible, dùng local để không cần tài khoản
Backblaze B2 thật) — STORAGE_ENDPOINT_URL trỏ sang MinIO thay vì B2, xem
docstring app/storage.py. Chạy `docker run -d -p 9010:9000 -e
MINIO_ROOT_USER=testkey -e MINIO_ROOT_PASSWORD=testsecret minio/minio server
/data` rồi tạo bucket `edututor-uploads` trước khi chạy file này (xem
README, mục Chạy test)."""
import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

os.environ.setdefault("STORAGE_ENDPOINT_URL", "http://localhost:9010")
os.environ.setdefault("STORAGE_ACCESS_KEY_ID", "testkey")
os.environ.setdefault("STORAGE_SECRET_ACCESS_KEY", "testsecret")
os.environ.setdefault("STORAGE_BUCKET_NAME", "edututor-uploads")

from app import storage


class TestStorage(unittest.TestCase):
    def setUp(self):
        storage.clear_client_cache()
        self.addCleanup(storage.clear_client_cache)
        self.key = f"test/{uuid.uuid4()}.pdf"
        self.addCleanup(self._cleanup_key)

    def _cleanup_key(self):
        try:
            storage.delete_file(self.key)
        except Exception:  # noqa: BLE001 — dọn best-effort, không phải assertion
            pass

    def test_save_then_read_round_trips_exact_bytes(self):
        content = b"%PDF-1.4 noi dung gia lap cho test"

        storage.save_file(self.key, content)
        result = storage.read_file(self.key)

        self.assertEqual(result, content)

    def test_file_exists_false_before_save_true_after(self):
        self.assertFalse(storage.file_exists(self.key))

        storage.save_file(self.key, b"data")

        self.assertTrue(storage.file_exists(self.key))

    def test_delete_file_makes_it_unreadable(self):
        storage.save_file(self.key, b"data")
        storage.delete_file(self.key)

        self.assertFalse(storage.file_exists(self.key))
        with self.assertRaises(Exception):
            storage.read_file(self.key)


if __name__ == "__main__":
    unittest.main()
