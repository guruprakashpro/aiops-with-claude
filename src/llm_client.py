"""
Unified LLM Client wrapping the Groq SDK.

Optimizations demonstrated:
- Retry logic with exponential backoff for rate limits
- Token usage tracking
- Streaming support
- JSON mode support
"""

import os
import time
import json
from typing import Generator, Optional
from groq import Groq, RateLimitError, APIError
from dotenv import load_dotenv

load_dotenv()

# Model constants - FAST for simple tasks, SMART for complex reasoning
FAST_MODEL = "llama-3.1-8b-instant"
SMART_MODEL = "llama-3.3-70b-versatile"


class LLMClient:
    """
    Unified Groq LLM client with:
    - Exponential backoff retry on rate limits
    - Token usage tracking
    - Streaming and JSON mode support
    """

    def __init__(self, api_key: Optional[str] = None):
        self.client = Groq(api_key=api_key or os.environ.get("GROQ_API_KEY"))
        self.last_usage: dict = {}
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_requests: int = 0

    def complete(
        self,
        messages: list[dict],
        model: str = SMART_MODEL,
        stream: bool = False,
        json_mode: bool = False,
        temperature: float = 0.3,
    ) -> str:
        """
        Basic completion with retry logic.

        Args:
            messages: List of {"role": ..., "content": ...} dicts
            model: Groq model ID
            stream: If True, use streaming (returns joined result)
            json_mode: If True, force JSON response format
            temperature: Sampling temperature (lower = more deterministic)

        Returns:
            Completion text as string
        """
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if stream:
                    # For streaming, collect all chunks and return joined string
                    full_text = ""
                    response = self.client.chat.completions.create(
                        stream=True, **kwargs
                    )
                    for chunk in response:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            full_text += delta
                    # Note: streaming doesn't return usage; estimate from text
                    self.last_usage = {
                        "prompt_tokens": 0,
                        "completion_tokens": len(full_text.split()),
                        "total_tokens": len(full_text.split()),
                    }
                    self._total_requests += 1
                    return full_text
                else:
                    response = self.client.chat.completions.create(**kwargs)
                    usage = response.usage
                    self.last_usage = {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                    }
                    self._total_prompt_tokens += usage.prompt_tokens
                    self._total_completion_tokens += usage.completion_tokens
                    self._total_requests += 1
                    return response.choices[0].message.content

            except RateLimitError as e:
                if attempt == max_retries - 1:
                    raise
                # Exponential backoff: 2s, 4s, 8s
                wait_time = 2 ** (attempt + 1)
                print(f"[Rate limit] Waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                time.sleep(wait_time)

            except APIError as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** (attempt + 1)
                print(f"[API error] {e}. Waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                time.sleep(wait_time)

        return ""

    def stream_complete(
        self,
        messages: list[dict],
        model: str = SMART_MODEL,
        temperature: float = 0.3,
    ) -> Generator[str, None, None]:
        """
        Generator that yields text chunks in real time.

        Optimization: Streaming dramatically reduces perceived latency -
        users see output immediately instead of waiting for the full response.

        Args:
            messages: List of message dicts
            model: Groq model ID

        Yields:
            Text chunks as they arrive from the API
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    stream=True,
                )
                self._total_requests += 1
                for chunk in response:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                return

            except RateLimitError:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** (attempt + 1)
                time.sleep(wait_time)

            except APIError as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** (attempt + 1)
                time.sleep(wait_time)

    def get_usage_summary(self) -> dict:
        """Return cumulative token usage across all calls in this session."""
        return {
            "total_requests": self._total_requests,
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
            "last_call": self.last_usage,
        }
