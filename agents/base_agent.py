"""
Base agent for Sidekick AI.

Provides shared functionality for all agents:
- Logging infrastructure
- LLM access
- Retry logic with exponential backoff
- JSON parsing helper
- Common response formatting
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from abc import ABC
from datetime import datetime
from typing import Any, Optional

from services.llm import LLMClient, llm


logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all Sidekick AI agents.

    Agents can optionally receive a request-specific LLMClient.

    If no client is supplied, the application's default global
    LLM client is used. This keeps existing code backward compatible.
    """

    def __init__(
        self,
        agent_name: str = "BaseAgent",
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        self.agent_name = agent_name

        # Use a request-specific client when supplied.
        # Otherwise use the application's default LLM client.
        self.llm = llm_client or llm

        self.logger = logging.getLogger(
            f"agents.{agent_name}"
        )

        self.created_at = datetime.utcnow()

        self.logger.info(
            "Initialized %s using provider=%s",
            agent_name,
            getattr(self.llm, "provider", "unknown"),
        )

    # ------------------------------------------------------------------
    # Async LLM helper
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        user_id: Optional[str | int] = None,
        caller: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Call the configured LLM client.

        The agent does not need to know whether the provider is
        OpenRouter, Ollama, or another supported provider.
        """

        caller_name = caller or self.__class__.__name__

        return await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            user_id=user_id,
            caller=caller_name,
        )

    # ------------------------------------------------------------------
    # Async retry with exponential backoff
    # ------------------------------------------------------------------

    async def retry_with_backoff(
        self,
        coro_func,
        *args,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        **kwargs,
    ) -> Any:
        """
        Execute an async coroutine function with exponential backoff.
        """

        delay = initial_delay
        last_exception: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(
                    "%s: attempt %d/%d for %s",
                    self.agent_name,
                    attempt + 1,
                    max_retries + 1,
                    getattr(
                        coro_func,
                        "__name__",
                        str(coro_func),
                    ),
                )

                return await coro_func(
                    *args,
                    **kwargs,
                )

            except Exception as exc:
                last_exception = exc

                if attempt == max_retries:
                    self.logger.error(
                        "%s: all retries exhausted for %s: %s",
                        self.agent_name,
                        getattr(
                            coro_func,
                            "__name__",
                            str(coro_func),
                        ),
                        exc,
                    )
                    raise

                self.logger.warning(
                    "%s: attempt %d failed; retrying in %.1fs: %s",
                    self.agent_name,
                    attempt + 1,
                    delay,
                    exc,
                )

                await asyncio.sleep(delay)
                delay *= backoff_factor

        if last_exception:
            raise last_exception

        raise RuntimeError(
            f"{self.agent_name}: retry operation failed unexpectedly."
        )

    # ------------------------------------------------------------------
    # JSON parsing helper
    # ------------------------------------------------------------------

    def parse_json_response(
        self,
        text: str,
    ) -> dict | list:
        """
        Parse JSON returned by an LLM.

        Supports normal JSON and markdown fenced JSON responses.
        Returns an empty dict when parsing fails.
        """

        if not text or not isinstance(text, str):
            self.logger.warning(
                "%s: empty or invalid LLM response",
                self.agent_name,
            )
            return {}

        cleaned = text.strip()

        # Remove ```json ... ``` or ``` ... ``` fences.
        fence_match = re.match(
            r"^```(?:json)?\s*(.*?)\s*```$",
            cleaned,
            flags=re.DOTALL,
        )

        if fence_match:
            cleaned = fence_match.group(1).strip()

        if not cleaned:
            return {}

        try:
            return json.loads(cleaned)

        except (json.JSONDecodeError, TypeError) as exc:
            self.logger.error(
                "%s: JSON parsing failed: %s | raw=%s",
                self.agent_name,
                exc,
                cleaned[:200],
            )
            return {}

    # ------------------------------------------------------------------
    # Standard response formatter
    # ------------------------------------------------------------------

    def format_response(
        self,
        success: bool,
        data: Any = None,
        error: Optional[str] = None,
    ) -> dict:
        """
        Return a standardized agent response.
        """

        return {
            "success": success,
            "agent": self.agent_name,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
            "error": error,
        }