"""LLM client thật, gọi Google Gemini API (free tier).

Implement đúng interface `LLMClient` (`complete(prompt) -> str`) mà
`app/llm/rag.py` mong đợi — nhờ vậy `rag.py` không cần biết đang gọi Gemini
hay bất kỳ provider nào khác.

Free tier Gemini giới hạn theo request/phút (model mặc định gemini-3.1-flash-lite,
có thể thay đổi theo chính sách Google — kiểm tra lại trước khi demo). Có
retry với backoff khi gặp lỗi rate limit (HTTP 429) để không vỡ trải nghiệm
khi nhiều lượt hỏi gần nhau.

Lưu ý: gemini-2.0-flash đã bị Google deprecate và ngừng phục vụ (shut down
1/6/2026) — quota free tier của model đó về 0 nên mọi request đều lỗi 429
dù retry bao nhiêu lần cũng không cứu được, phải đổi sang model mới.

CHƯA GỌI ĐƯỢC TRONG SANDBOX NÀY: cần `pip install google-generativeai` và
một API key thật (lấy miễn phí tại https://aistudio.google.com/apikey).
Sandbox không có mạng nên không test được lượt gọi API thật ở đây.
"""

import os
import time


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str = "gemini-3.1-flash-lite", max_retries: int = 3):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Thiếu GEMINI_API_KEY. Lấy key miễn phí tại "
                "https://aistudio.google.com/apikey và đặt vào biến môi trường."
            )
        self.model_name = model
        self.max_retries = max_retries
        self._client = None

    def _get_model(self):
        if self._client is None:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model_name)
        return self._client

    def complete(self, prompt: str) -> str:
        model = self._get_model()
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:  # noqa: BLE001 - cần bắt mọi lỗi API để retry
                last_error = e
                is_rate_limit = "429" in str(e) or "rate limit" in str(e).lower()
                if is_rate_limit and attempt < self.max_retries - 1:
                    backoff_seconds = 2**attempt * 5  # 5s, 10s, 20s...
                    time.sleep(backoff_seconds)
                    continue
                raise
        raise last_error  # type: ignore[misc]
