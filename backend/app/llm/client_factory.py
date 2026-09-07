"""Chọn LLM client thật sẽ dùng trong toàn app — một điểm duy nhất, thay vì
mỗi router (`chat.py`, `quiz.py`, `flashcard.py`) tự khởi tạo `GeminiClient()`
hay `OpenAIClient()` riêng.

Ưu tiên: `LLM_PROVIDER` (nếu đặt tường minh) -> có `OPENAI_API_KEY` thì dùng
OpenAI (mặc định của dự án) -> còn lại rơi về Gemini. Cùng nguyên tắc chọn
theo "key nào có sẵn" mà project chị em P-243 dùng (`src/core/config.py`,
`_nha_cung_cap`) — đổi provider chỉ cần đổi biến môi trường, không phải sửa
code hay đổi lại từng nơi gọi.
"""

import os

from app.llm.rag import LLMClient


def get_llm_client() -> LLMClient:
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()

    if not provider:
        provider = "openai" if os.environ.get("OPENAI_API_KEY") else "gemini"

    if provider == "openai":
        from app.llm.openai_client import OpenAIClient

        return OpenAIClient()
    if provider == "gemini":
        from app.llm.gemini_client import GeminiClient

        return GeminiClient()

    raise ValueError(
        f"LLM_PROVIDER không hợp lệ: {provider!r}. Chỉ nhận 'openai' hoặc 'gemini'."
    )
