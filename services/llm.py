from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


# =========================================================================
# Custom Exceptions
# =========================================================================


class LLMException(Exception):
    """Base exception for all LLM-related errors."""


class LLMConnectionError(LLMException):
    """Raised when the LLM service cannot be reached or returns a server error."""


class LLMAuthenticationError(LLMException):
    """Raised when authentication with the LLM provider fails (HTTP 401)."""


class LLMRateLimitError(LLMException):
    """Raised when the LLM provider throttles requests (HTTP 429)."""


class LLMResponseError(LLMException):
    """Raised when the LLM provider returns an invalid or unparsable response."""


# =========================================================================
# LLM Client
# =========================================================================


class LLMClient:
    """
    A production-grade client for communicating with the OpenRouter API.
    
    """

    CHAT_COMPLETIONS_PATH = "/chat/completions"
    MODELS_PATH = "/models"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Initialize the LLM client with configuration values.
        
        """
        self.api_key: str = api_key or settings.OPENROUTER_API_KEY
        self.base_url: str = (base_url or settings.OPENROUTER_BASE_URL).rstrip("/")
        self.model: str = model or settings.OPENROUTER_MODEL
        self.timeout: float = timeout or settings.OPENROUTER_TIMEOUT

        if not self.api_key:
            logger.warning("LLMClient initialized without an OpenRouter API key.")

        self._client: httpx.Client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
        )

        logger.debug(
            "LLMClient initialized (base_url=%s, model=%s, timeout=%s)",
            self.base_url,
            self.model,
            self.timeout,
        )

    def __del__(self) -> None:
        """Ensure the underlying HTTP client is closed on garbage collection."""
        try:
            self.close()
        except Exception:  # noqa: BLE001 - best-effort cleanup, never raise
            pass

    def close(self) -> None:
        """Close the underlying httpx.Client, releasing pooled connections."""
        if getattr(self, "_client", None) is not None and not self._client.is_closed:
            self._client.close()
            logger.debug("LLMClient HTTP client closed.")

    # ---------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        """Build the HTTP headers required by the OpenRouter API."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Construct the JSON payload for a chat completion request.

        Only includes optional parameters (temperature, max_tokens, and any
        additional keyword arguments) when they are explicitly provided.
        """
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
        }

        if temperature is not None:
            payload["temperature"] = temperature

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        for key, value in kwargs.items():
            if value is not None:
                payload[key] = value

        return payload

    def _request(
        self,
        method: str,
        path: str,
        json_payload: Optional[dict[str, Any]] = None,
    ) -> httpx.Response:
        """
        Execute an HTTP request against the OpenRouter API.

        Handles timing, logging, and translation of transport-level failures
        (timeouts, connection errors) into the appropriate custom exception.
        Raises the response's HTTP status errors via raise_for_status(),
        which are subsequently translated in _handle_error().
        """
        start_time = time.monotonic()
        try:
            response = self._client.request(
                method=method,
                url=path,
                headers=self._headers(),
                json=json_payload,
            )
            elapsed = time.monotonic() - start_time
            logger.info(
                "LLM request completed (method=%s, path=%s, status=%s, elapsed=%.3fs)",
                method,
                path,
                response.status_code,
                elapsed,
            )
            response.raise_for_status()
            return response

        except httpx.TimeoutException as exc:
            elapsed = time.monotonic() - start_time
            logger.error(
                "LLM request timed out (method=%s, path=%s, elapsed=%.3fs): %s",
                method,
                path,
                elapsed,
                exc,
            )
            raise LLMConnectionError(f"Request to LLM provider timed out: {exc}") from exc

        except httpx.HTTPStatusError as exc:
            self._handle_error(exc)
            raise  # _handle_error always raises; this satisfies static analysis

        except httpx.RequestError as exc:
            elapsed = time.monotonic() - start_time
            logger.error(
                "LLM request failed (method=%s, path=%s, elapsed=%.3fs): %s",
                method,
                path,
                elapsed,
                exc,
            )
            raise LLMConnectionError(f"Failed to connect to LLM provider: {exc}") from exc

    def _handle_error(self, exc: httpx.HTTPStatusError) -> None:
        """
        Translate an HTTP status error from the LLM provider into the
        appropriate custom exception, based on the response status code.
        """
        status_code = exc.response.status_code

        try:
            error_body = exc.response.json()
        except ValueError:
            error_body = exc.response.text

        logger.error(
            "LLM provider returned an error (status=%s, body=%s)",
            status_code,
            error_body,
        )

        if status_code == 401:
            raise LLMAuthenticationError(
                f"Authentication with LLM provider failed: {error_body}"
            ) from exc

        if status_code == 429:
            raise LLMRateLimitError(
                f"LLM provider rate limit exceeded: {error_body}"
            ) from exc

        if 500 <= status_code < 600:
            raise LLMConnectionError(
                f"LLM provider server error ({status_code}): {error_body}"
            ) from exc

        raise LLMException(
            f"Unexpected error from LLM provider ({status_code}): {error_body}"
        ) from exc

    def _parse_response(self, response: httpx.Response) -> str:
        """
        Extract the assistant's message content from a chat completion response.

        Raises LLMResponseError if the response body is not valid JSON or does
        not contain the expected structure.
        """
        try:
            data = response.json()
        except ValueError as exc:
            logger.error("Failed to parse LLM response as JSON: %s", exc)
            raise LLMResponseError(f"Invalid JSON response from LLM provider: {exc}") from exc

        try:
            choices = data["choices"]
            if not choices:
                raise LLMResponseError("LLM response contained no choices.")

            message = choices[0]["message"]
            content = message["content"]

            if not isinstance(content, str) or not content.strip():
                raise LLMResponseError("LLM response message content is empty or invalid.")

            return content

        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Unexpected LLM response structure: %s | payload=%s", exc, data)
            raise LLMResponseError(f"Unexpected response structure from LLM provider: {exc}") from exc

    # ---------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate a completion for a single user prompt.

        Optionally accepts a system prompt to steer the model's behavior.
        Returns the assistant's response text.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Send a full conversation history to the LLM and return the assistant's reply.

        This is the core method used by higher-level features that need
        multi-turn context (e.g. chat sessions, agents).
        """
        if not messages:
            raise LLMException("Cannot send an empty messages list to the LLM provider.")

        payload = self._payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        logger.debug("Sending chat completion request (model=%s, n_messages=%d)", 
                     payload["model"], len(messages))

        response = self._request(
            method="POST",
            path=self.CHAT_COMPLETIONS_PATH,
            json_payload=payload,
        )

        return self._parse_response(response)

    def health_check(self) -> bool:
        """
        Perform a lightweight health check against the LLM provider.

        Returns True if the provider responds successfully to a minimal
        chat completion request, False otherwise. Never raises.
        """
        try:
            self.chat(
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except LLMException as exc:
            logger.warning("LLM health check failed: %s", exc)
            return False

    def list_models(self) -> list[dict[str, Any]]:
        """
        Retrieve the list of models available from the OpenRouter API.

        Returns a list of model metadata dictionaries as provided by the
        provider's /models endpoint.
        """
        response = self._request(method="GET", path=self.MODELS_PATH)

        try:
            data = response.json()
            return data.get("data", [])
        except ValueError as exc:
            logger.error("Failed to parse models list response: %s", exc)
            raise LLMResponseError(f"Invalid JSON response when listing models: {exc}") from exc

    def estimate_tokens(self, text: str) -> int:
        """
        Provide a rough estimate of the token count for a given text.

        This uses a simple heuristic (approximately 4 characters per token)
        suitable for quick budgeting decisions. It is not a substitute for
        an actual tokenizer when precise counts are required.
        """
        if not text:
            return 0
        return max(1, len(text) // 4)


# =========================================================================
# Singleton instance
# =========================================================================

llm = LLMClient()


# =========================================================================
# Convenience wrappers
# =========================================================================


def generate_response(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """Module-level convenience wrapper around the singleton LLMClient.generate()."""
    return llm.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def health_check() -> bool:
    """Module-level convenience wrapper around the singleton LLMClient.health_check()."""
    return llm.health_check()


# =========================================================================
# Manual testing block
# =========================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    print("=== SidekickAI LLM Service Manual Test ===")

    print("\n[1] Running health check...")
    is_healthy = health_check()
    print(f"Health check result: {is_healthy}")

    if is_healthy:
        print("\n[2] Sending test prompt...")
        try:
            result = generate_response(
                prompt="In one sentence, what is the capital of France?",
                system_prompt="You are a concise assistant.",
                temperature=0.7,
                max_tokens=50,
            )
            print(f"Response: {result}")
        except LLMException as exc:
            print(f"Generation failed: {exc}")

        print("\n[3] Listing available models...")
        try:
            models = llm.list_models()
            print(f"Retrieved {len(models)} models.")
        except LLMException as exc:
            print(f"Failed to list models: {exc}")
    else:
        print("Skipping further tests since health check failed.")

    llm.close()