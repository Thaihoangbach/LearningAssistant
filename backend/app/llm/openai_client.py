"""LLM client thật, gọi OpenAI API.

Implement đúng interface `LLMClient` (`complete(prompt) -> str`) mà
`app/llm/rag.py` mong đợi — nhờ vậy `rag.py`/`quiz_generator.py`/
`flashcard_generator.py`/`guardrail.py` không cần biết đang gọi OpenAI hay
bất kỳ provider nào khác (cùng khuôn với `gemini_client.py`).

Model mặc định `gpt-4o-mini`: rẻ nhất trong dòng model OpenAI còn đủ mạnh cho
các việc pipeline này cần (tổng hợp câu trả lời có căn cứ, JSON verdict theo
từng luận điểm, sinh quiz/flashcard) — phù hợp với ngân sách nhỏ (khác free
tier Gemini, OpenAI tính phí theo token ngay từ request đầu tiên).

CHƯA GỌI ĐƯỢC TRONG SANDBOX NÀY: cần `pip install openai` và một API key
thật (https://platform.openai.com/api-keys). Sandbox không có mạng nên không
test được lượt gọi API thật ở đây.
"""

import os
import time


class OpenAIClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Thiếu OPENAI_API_KEY. Lấy key tại "
                "https://platform.openai.com/api-keys và đặt vào biến môi trường."
            )
        self.model_name = model
        self.max_retries = max_retries
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def complete(self, prompt: str) -> str:
        client = self._get_client()
        # Import cục bộ, cùng lý do với `_get_client` — module `openai` chỉ
        # cần thiết khi thật sự dùng provider này.
        from openai import APIConnectionError, RateLimitError

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.choices[0].message.content or ""
            except (RateLimitError, APIConnectionError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    backoff_seconds = 2**attempt * 5  # 5s, 10s, 20s...
                    time.sleep(backoff_seconds)
                    continue
                raise
        raise last_error  # type: ignore[misc]
