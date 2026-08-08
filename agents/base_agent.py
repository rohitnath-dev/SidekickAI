"""
Base agent for Sidekick AI.

Provides shared functionality for all agents:
- Logging infrastructure
- LLM access (async)
- Retry logic with exponential backoff (async)
- JSON parsing helper
- Common error handling
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from abc import ABC
from datetime import datetime
from typing import Any, Optional

from services.llm import llm

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all AI agents in Sidekick AI.

    Provides:
    - Centralized logging
    - Async LLM access
    - Async retry logic with exponential backoff
    - JSON parsing with markdown fence stripping
    - Standardized response formatting
    """

    def __init__(self, agent_name: str = "BaseAgent"):
        self.agent_name = agent_name
        self.llm = llm
        self.logger = logging.getLogger(f"agents.{agent_name}")
        self.created_at = datetime.utcnow()
        self.logger.info("Initialized %s", agent_name)

    # ------------------------------------------------------------------
    # Async LLM helper
    
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        user_id: Optional[int] = None,
        caller: Optional[str] = None,
    ) -> str:
        """Call the LLM and return the generated text without catching exceptions."""
        caller_name = caller or self.__class__.__name__
        return await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            user_id=user_id,
            caller=caller_name,
        )

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
        Execute an async coroutine function with exponential backoff retry.

        Args:
            coro_func: Async function to call.
            *args: Positional arguments for the function.
            max_retries: Maximum retry attempts.
            initial_delay: Initial delay in seconds.
            backoff_factor: Multiplier for delay between retries.
            **kwargs: Keyword arguments for the function.

        Returns:
            Result of the coroutine.

        Raises:
            Exception: If all retries fail.
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
                    getattr(coro_func, "__name__", str(coro_func)),
                )
                return await coro_func(*args, **kwargs)
            except Exception as exc:
                last_exception = exc
                if attempt == max_retries:
                    self.logger.error(
                        "%s: all %d retries exhausted for %s: %s",
                        self.agent_name,
                        max_retries,
                        getattr(coro_func, "__name__", str(coro_func)),
                        exc,
                    )
                    raise
                self.logger.warning(
                    "%s: attempt %d failed, retrying in %.1fs: %s",
                    self.agent_name,
                    attempt + 1,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
                delay *= backoff_factor

        if last_exception:
            raise last_exception

    # ------------------------------------------------------------------
    # JSON parsing helper
    # ------------------------------------------------------------------

    def parse_json_response(self, text: str) -> dict | list:
        """
        Parse a JSON response from the LLM.

        - Strips markdown code fences (```json ... ``` or ``` ... ```)
        - Calls json.loads
        - Returns {} or [] on failure (preserving the expected shape)

        Returns:
            Parsed dict or list, or {} on failure.
        """
        if not text or not isinstance(text, str):
            self.logger.warning("%s: empty or non-string LLM response", self.agent_name)
            return {}

        cleaned = text.strip()

        # Strip markdown fences
        fence_match = re.match(
            r"^```(?:json)?\s*(.*?)\s*```$",
            cleaned,
            flags=re.DOTALL,
        )
        if fence_match:
            cleaned = fence_match.group(1).strip()

        if not cleaned:
            self.logger.warning("%s: empty content after stripping fences", self.agent_name)
            return {}

        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, TypeError) as exc:
            self.logger.error(
                "%s: JSON parse failed: %s | raw: %s",
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
        """Return a standardized response envelope."""
        return {
            "success": success,
            "agent": self.agent_name,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
            "error": error,
        }
