import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.llm.client_factory import get_llm_client


def _clean_env():
    """Xoá sạch biến môi trường liên quan trước mỗi test — không phụ thuộc
    .env thật của máy chạy test (cùng lý do với test_config_provider.py bên
    project chị em P-243: nhiễm biến môi trường thật là lỗi từng gặp)."""
    return patch.dict(
        os.environ, {"OPENAI_API_KEY": "", "GEMINI_API_KEY": "", "LLM_PROVIDER": ""}, clear=False
    )


class TestGetLlmClient(unittest.TestCase):
    def test_openai_key_present_selects_openai_by_default(self):
        with _clean_env(), patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("app.llm.openai_client.OpenAIClient") as mock_openai:
                get_llm_client()
                mock_openai.assert_called_once_with()

    def test_only_gemini_key_present_falls_back_to_gemini(self):
        with _clean_env(), patch.dict(os.environ, {"GEMINI_API_KEY": "gm-test"}):
            with patch("app.llm.gemini_client.GeminiClient") as mock_gemini:
                get_llm_client()
                mock_gemini.assert_called_once_with()

    def test_both_keys_present_still_prefers_openai(self):
        with _clean_env(), patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-test", "GEMINI_API_KEY": "gm-test"}
        ):
            with patch("app.llm.openai_client.OpenAIClient") as mock_openai:
                get_llm_client()
                mock_openai.assert_called_once_with()

    def test_explicit_llm_provider_overrides_key_based_default(self):
        """Cả hai key đều có, nhưng LLM_PROVIDER=gemini ép dùng Gemini — cho
        phép chuyển lại Gemini mà không cần xoá OPENAI_API_KEY."""
        with _clean_env(), patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-test", "GEMINI_API_KEY": "gm-test", "LLM_PROVIDER": "gemini"},
        ):
            with patch("app.llm.gemini_client.GeminiClient") as mock_gemini:
                get_llm_client()
                mock_gemini.assert_called_once_with()

    def test_invalid_provider_raises_clear_error(self):
        with _clean_env(), patch.dict(os.environ, {"LLM_PROVIDER": "claude"}):
            with self.assertRaises(ValueError):
                get_llm_client()


if __name__ == "__main__":
    unittest.main()
