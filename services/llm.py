"""
Sidekick AI — Provider-Agnostic LLM Service

Supported providers:
- Ollama
- OpenRouter

The rest of the application uses the common LLMClient interface
and does not need to know which provider is being used.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Exceptions
# ============================================================================

class LLMException(Exception):
    """Base exception for LLM errors."""


class LLMConnectionError(LLMException):
    """Network, connection, or timeout error."""


class LLMAuthenticationError(LLMException):
    """Authentication/API-key error."""


class LLMRateLimitError(LLMException):
    """Provider rate-limit error."""


class LLMResponseError(LLMException):
    """Invalid or malformed provider response."""


# ============================================================================
# LLM Client
# ============================================================================

class LLMClient:
    """
    Provider-agnostic LLM client.

    Supported providers:
        - ollama
        - openrouter

    Existing agents should only call:
        generate(...)
        chat(...)

    They should NOT care which provider is being used.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:

        # ---------------------------------------------------------------
        # Provider
        # ---------------------------------------------------------------

        self.provider = (
            provider
            or os.getenv("LLM_PROVIDER")
            or getattr(settings, "LLM_PROVIDER", None)
            or "openrouter"
        ).lower().strip()

        if self.provider not in {"ollama", "openrouter"}:
            raise ValueError(
                f"Unsupported LLM provider: {self.provider}. "
                f"Supported providers: ollama, openrouter"
            )

        # ---------------------------------------------------------------
        # Ollama configuration
        # ---------------------------------------------------------------

        self.ollama_base_url = (
            base_url
            if self.provider == "ollama" and base_url
            else os.getenv("OLLAMA_BASE_URL")
            or getattr(settings, "OLLAMA_BASE_URL", None)
            or "http://localhost:11434"
        ).rstrip("/")

        self.ollama_model = (
            model
            if self.provider == "ollama" and model
            else os.getenv("OLLAMA_MODEL")
            or getattr(settings, "OLLAMA_MODEL", None)
            or "llama3.2"
        )

        # ---------------------------------------------------------------
        # OpenRouter configuration
        # ---------------------------------------------------------------

        self.openrouter_api_key = (
            api_key
            or os.getenv("OPENROUTER_API_KEY")
            or getattr(settings, "OPENROUTER_API_KEY", None)
            or ""
        )

        self.openrouter_base_url = (
            os.getenv("OPENROUTER_BASE_URL")
            or getattr(settings, "OPENROUTER_BASE_URL", None)
            or "https://openrouter.ai/api/v1"
        ).rstrip("/")

        self.openrouter_model = (
            model
            if self.provider == "openrouter" and model
            else os.getenv("OPENROUTER_MODEL")
            or getattr(settings, "OPENROUTER_MODEL", None)
            or "openrouter/free"
        )

        # ---------------------------------------------------------------
        # Common configuration
        # ---------------------------------------------------------------

        try:
            self.timeout = timeout or float(
                os.getenv("LLM_TIMEOUT")
                or getattr(settings, "OPENROUTER_TIMEOUT", None)
                or 60.0
            )
        except (TypeError, ValueError):
            self.timeout = 60.0

    # ====================================================================
    # Public API
    # ====================================================================

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        user_id: Optional[int] = None,
        caller: Optional[str] = None,
    ) -> str:
        """
        Generate a response from the currently selected provider.
        """

        messages: list[dict[str, str]] = []

        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        return await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
            user_id=user_id,
            caller=caller or "generate",
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        user_id: Optional[int] = None,
        caller: Optional[str] = None,
    ) -> str:
        """
        Send messages to the selected LLM provider.
        """

        if not messages:
            raise LLMException("Cannot send an empty messages list.")

        logger.info(
            "LLM request: provider=%s caller=%s user_id=%s model=%s",
            self.provider,
            caller or "chat",
            user_id,
            model or self._active_model(model),
        )

        if self.provider == "ollama":
            return await self._chat_ollama(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            )

        if self.provider == "openrouter":
            return await self._chat_openrouter(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            )

        raise LLMException(
            f"Unsupported LLM provider: {self.provider}"
        )

    # ====================================================================
    # Provider helpers
    # ====================================================================

    def _active_model(self, model: Optional[str] = None) -> str:
        if model:
            return model

        if self.provider == "ollama":
            return self.ollama_model

        return self.openrouter_model

    # ====================================================================
    # Ollama
    # ====================================================================

    async def _chat_ollama(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Send a chat request to a local Ollama server.

        Normal local Ollama does not require an API key.
        """

        url = f"{self.ollama_base_url}/api/chat"

        payload: dict[str, Any] = {
            "model": model or self.ollama_model,
            "messages": messages,
            "stream": False,
        }

        options: dict[str, Any] = {}

        if temperature is not None:
            options["temperature"] = temperature

        if max_tokens is not None:
            options["num_predict"] = max_tokens

        if options:
            payload["options"] = options

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout
            ) as client:

                response = await client.post(
                    url,
                    json=payload,
                )

        except httpx.TimeoutException as exc:
            raise LLMConnectionError(
                "Ollama request timed out."
            ) from exc

        except httpx.RequestError as exc:
            raise LLMConnectionError(
                f"Could not connect to Ollama at {self.ollama_base_url}."
            ) from exc

        if response.status_code != 200:
            self._handle_provider_status(
                response,
                provider="Ollama",
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMResponseError(
                "Ollama returned an invalid JSON response."
            ) from exc

        try:
            content = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMResponseError(
                f"Unexpected Ollama response format: {data}"
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError(
                "Ollama returned an empty response."
            )

        return content.strip()

    # ====================================================================
    # OpenRouter
    # ====================================================================

    async def _chat_openrouter(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Send a chat request to OpenRouter.
        """

        if not self.openrouter_api_key:
            raise LLMAuthenticationError(
                "OpenRouter API key is not configured."
            )

        url = (
            f"{self.openrouter_base_url}"
            "/chat/completions"
        )

        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": getattr(
                settings,
                "HTTP_REFERER",
                "https://sidekickai.onrender.com",
            ),
            "X-Title": getattr(
                settings,
                "APP_TITLE",
                "SidekickAI",
            ),
        }

        payload: dict[str, Any] = {
            "model": model or self.openrouter_model,
            "messages": messages,
        }

        if temperature is not None:
            payload["temperature"] = temperature

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout
            ) as client:

                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                )

        except httpx.TimeoutException as exc:
            raise LLMConnectionError(
                "OpenRouter request timed out."
            ) from exc

        except httpx.RequestError as exc:
            raise LLMConnectionError(
                "Could not connect to OpenRouter."
            ) from exc

        if response.status_code != 200:
            self._handle_provider_status(
                response,
                provider="OpenRouter",
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMResponseError(
                "OpenRouter returned invalid JSON."
            ) from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError(
                f"Unexpected OpenRouter response format: {data}"
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError(
                "OpenRouter returned an empty response."
            )

        return content.strip()

    # ====================================================================
    # Error handling
    # ====================================================================

    def _handle_provider_status(
        self,
        response: httpx.Response,
        provider: str,
    ) -> None:

        status = response.status_code

        # Never log/expose API keys.
        try:
            body = response.json()
        except ValueError:
            body = response.text[:500]

        if status == 401:
            raise LLMAuthenticationError(
                f"{provider} authentication failed."
            )

        if status == 403:
            raise LLMAuthenticationError(
                f"{provider} rejected the request."
            )

        if status == 429:
            raise LLMRateLimitError(
                f"{provider} rate limit reached."
            )

        if 500 <= status < 600:
            raise LLMConnectionError(
                f"{provider} server error ({status})."
            )

        raise LLMException(
            f"{provider} request failed ({status}): {body}"
        )

    # ====================================================================
    # Health / utility
    # ====================================================================

    async def health_check(self) -> bool:
        """
        Return True if the currently selected provider works.
        """

        try:
            await self.chat(
                messages=[
                    {
                        "role": "user",
                        "content": "Reply with OK.",
                    }
                ],
                max_tokens=5,
                caller="health_check",
            )
            return True

        except LLMException as exc:
            logger.warning(
                "LLM health check failed: %s",
                exc,
            )
            return False

    async def health_check_details(self) -> dict[str, Any]:
        """
        Return detailed provider health information.
        """

        try:
            await self.chat(
                messages=[
                    {
                        "role": "user",
                        "content": "Reply with OK.",
                    }
                ],
                max_tokens=5,
                caller="health_check_details",
            )

            return {
                "status": "ok",
                "provider": self.provider,
                "model": self._active_model(),
            }

        except LLMException as exc:
            return {
                "status": "error",
                "provider": self.provider,
                "model": self._active_model(),
                "reason": str(exc),
            }

    def estimate_tokens(self, text: str) -> int:
        """
        Rough token estimate.
        """

        if not text:
            return 0

        return max(1, len(text) // 4)


# ============================================================================
# Singleton
# ============================================================================

llm = LLMClient()


# ============================================================================
# Backwards-compatible helper
# ============================================================================

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