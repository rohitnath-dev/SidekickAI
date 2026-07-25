"""
Sidekick AI — LLM Service (OpenRouter)

Uses async httpx so it never blocks the FastAPI event loop.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class LLMException(Exception):
    """Base LLM error."""


class LLMConnectionError(LLMException):
    """Network or timeout error."""


class LLMAuthenticationError(LLMException):
    """HTTP 401 from provider."""


class LLMRateLimitError(LLMException):
    """HTTP 429 from provider."""


class LLMResponseError(LLMException):
    """Unparsable or malformed response."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class LLMClient:
    """Async client for the OpenRouter chat-completions API."""

    CHAT_PATH = "/chat/completions"
    MODELS_PATH = "/models"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.api_key: str = api_key or settings.OPENROUTER_API_KEY
        self.base_url: str = (base_url or settings.OPENROUTER_BASE_URL).rstrip("/")
        self.model: str = model or settings.OPENROUTER_MODEL
        self.timeout: float = timeout or settings.OPENROUTER_TIMEOUT

        if not self.api_key:
            logger.warning("LLMClient: no API key configured.")

        # Async client — one shared instance, closed at app shutdown.
        self._client: httpx.AsyncClient = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        )

    async def close(self) -> None:
        """Close the underlying async HTTP client."""
        if not self._client.is_closed:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.HTTP_REFERER,
            "X-Title": settings.APP_TITLE,
        }

    def _payload(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        for k, v in kwargs.items():
            if v is not None:
                payload[k] = v
        return payload

    async def _request(
        self,
        method: str,
        path: str,
        json_payload: Optional[dict[str, Any]] = None,
    ) -> httpx.Response:
        try:
            response = await self._client.request(
                method=method,
                url=path,
                headers=self._headers(),
                json=json_payload,
            )
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise LLMConnectionError(f"LLM request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            self._handle_http_error(exc)
            raise  # _handle_http_error always raises; satisfies type checkers
        except httpx.RequestError as exc:
            raise LLMConnectionError(f"LLM connection failed: {exc}") from exc

    def _handle_http_error(self, exc: httpx.HTTPStatusError) -> None:
        status = exc.response.status_code
        try:
            body = exc.response.json()
        except ValueError:
            body = exc.response.text

        if status == 401:
            raise LLMAuthenticationError(f"Auth failed: {body}") from exc
        if status == 429:
            raise LLMRateLimitError(f"Rate limit: {body}") from exc
        if 500 <= status < 600:
            raise LLMConnectionError(f"Provider error {status}: {body}") from exc
        raise LLMException(f"Unexpected LLM error {status}: {body}") from exc

    def _extract_content(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMResponseError(f"Non-JSON response: {exc}") from exc
        try:
            choices = data["choices"]
            if not choices:
                raise LLMResponseError("Empty choices list.")
            content = choices[0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise LLMResponseError("Empty content in response.")
            return content
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError(f"Unexpected response shape: {exc}") from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """Generate a completion for a single prompt."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """Send a conversation and return the assistant reply."""
        if not messages:
            raise LLMException("Cannot send empty messages list.")
        payload = self._payload(
            messages=messages,
            model=model,
            temperature=temperature or settings.OPENROUTER_TEMPERATURE,
            max_tokens=max_tokens or settings.OPENROUTER_MAX_TOKENS,
        )
        logger.debug(
            "LLM request — model=%s messages=%d", payload["model"], len(messages)
        )
        response = await self._request("POST", self.CHAT_PATH, payload)
        return self._extract_content(response)

    async def health_check(self) -> bool:
        """Return True if the provider is reachable."""
        try:
            await self.chat(
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except LLMException as exc:
            logger.warning("LLM health check failed: %s", exc)
            return False

    async def list_models(self) -> list[dict[str, Any]]:
        """Return available models from OpenRouter."""
        response = await self._request("GET", self.MODELS_PATH)
        try:
            return response.json().get("data", [])
        except ValueError as exc:
            raise LLMResponseError(f"Cannot parse models list: {exc}") from exc

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate (~4 chars/token)."""
        return max(1, len(text) // 4) if text else 0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

llm = LLMClient()


async def generate_response(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    return await llm.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
