import asyncio
from dataclasses import dataclass
from typing import Any
import httpx

@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str
    model: str


class OpenAICompatibleClient:
    """
    Universal async client communicating with any OpenAI-compatible completions endpoint:
    DeepSeek, OpenRouter, Gemini (OpenAI endpoint), Ollama, vLLM.
    """

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 90.0):
        # Normalize base_url to ensure it doesn't duplicate /v1
        base = base_url.rstrip("/")
        if not base.endswith("/v1"):
            self.endpoint = f"{base}/v1/chat/completions"
        else:
            self.endpoint = f"{base}/chat/completions"

        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def complete(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_retries: int = 3,
    ) -> LLMResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        last_error = None
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(self.endpoint, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        choice = data["choices"][0]
                        usage = data.get("usage", {})
                        return LLMResponse(
                            content=choice["message"].get("content") or "",
                            prompt_tokens=usage.get("prompt_tokens", 0),
                            completion_tokens=usage.get("completion_tokens", 0),
                            finish_reason=choice.get("finish_reason", "stop"),
                            model=data.get("model", self.model),
                        )
                    elif resp.status_code in (429, 500, 502, 503):
                        retry_after = resp.headers.get("retry-after")
                        sleep_time = float(retry_after) if retry_after and retry_after.isdigit() else (4.0 * (attempt + 1))
                        last_error = f"HTTP {resp.status_code}: {resp.text}"
                        await asyncio.sleep(sleep_time)
                    else:
                        raise RuntimeError(f"API Error {resp.status_code}: {resp.text}")
            except httpx.RequestError as e:
                last_error = str(e)
                await asyncio.sleep(3.0 * (attempt + 1))

        raise RuntimeError(f"Failed to complete LLM request after {max_retries} attempts. Last error: {last_error}")
