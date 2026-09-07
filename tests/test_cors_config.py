"""ARCH-5 — CORS trước đây LUÔN cho phép http://localhost:5173 kèm
allow_credentials=True, kể cả khi FRONTEND_URL đã trỏ tới một domain
production thật (Vercel...). Test hàm THUẦN `compute_allowed_origins`
(app/main.py) trực tiếp — không phụ thuộc biến môi trường hay side-effect
nào (module app.main vẫn được import như một phần tất yếu để lấy hàm, nhưng
bản thân hàm không đọc os.environ)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import compute_allowed_origins


class TestComputeAllowedOrigins(unittest.TestCase):
    def test_no_frontend_url_configured_falls_back_to_localhost_dev(self):
        self.assertEqual(compute_allowed_origins(None), ["http://localhost:5173"])

    def test_frontend_url_configured_excludes_localhost(self):
        origins = compute_allowed_origins("https://edututor.example.com")

        self.assertEqual(origins, ["https://edututor.example.com"])
        self.assertNotIn("http://localhost:5173", origins)

    def test_frontend_url_equal_to_localhost_is_not_duplicated(self):
        origins = compute_allowed_origins("http://localhost:5173")

        self.assertEqual(origins, ["http://localhost:5173"])


if __name__ == "__main__":
    unittest.main()
