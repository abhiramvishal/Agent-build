from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class OllamaClient:
    base_url: str = "http://localhost:11434"
    timeout_seconds: int = 60
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0

    def generate(self, model: str, prompt: str) -> str:
        """
        Call Ollama's /api/generate endpoint with streaming disabled.

        Raises requests.RequestException on repeated failures.
        """
        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(
                    url,
                    data=json.dumps(payload),
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout_seconds,
                )
                resp.raise_for_status()
                data = resp.json()
                # Ollama's non-streaming response usually has top-level "response"
                text = data.get("response")
                if not isinstance(text, str):
                    raise ValueError(f"Unexpected Ollama response shape: {data!r}")
                return text
            except Exception as exc:  # noqa: BLE001 - want broad safety here
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_backoff_seconds)
        assert last_error is not None
        raise last_error

