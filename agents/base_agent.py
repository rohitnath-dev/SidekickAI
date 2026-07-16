"""
Base agent for Sidekick AI.

Provides shared functionality for all agents:
- Logging infrastructure
- LLM access
- Retry logic with exponential backoff
- Input validation
- Error handling
- Common helper methods
"""

import logging
from abc import ABC
from typing import Any, Optional
from datetime import datetime

from services.llm import llm
from config import settings

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all AI agents in Sidekick AI.

    Provides:
    - Centralized logging
    - Mesh AI service access
    - Retry logic with exponential backoff
    - Input validation
    - Error handling
    - Timestamp tracking
    """

    def __init__(self, agent_name: str = "BaseAgent"):
        """
        Initialize the base agent.

        Args:
            agent_name: Descriptive name for logging purposes
        """
        self.agent_name = agent_name
        self.llm = llm
        self.logger = logging.getLogger(f"{__name__}.{agent_name}")
        self.created_at = datetime.utcnow()

        self.logger.info(
            f"Initialized {agent_name}",
            extra={"agent": agent_name, "timestamp": self.created_at.isoformat()}
        )

    def log_info(self, message: str, **extra_data) -> None:
        """
        Log info-level messages.

        Args:
            message: Log message
            **extra_data: Additional context data
        """
        self.logger.info(
            message,
            extra={"agent": self.agent_name, **extra_data}
        )

    def log_debug(self, message: str, **extra_data) -> None:
        """
        Log debug-level messages.

        Args:
            message: Log message
            **extra_data: Additional context data
        """
        self.logger.debug(
            message,
            extra={"agent": self.agent_name, **extra_data}
        )

    def log_error(self, message: str, exception: Optional[Exception] = None, **extra_data) -> None:
        """
        Log error-level messages.

        Args:
            message: Log message
            exception: Exception object (optional)
            **extra_data: Additional context data
        """
        if exception:
            self.logger.error(
                message,
                exc_info=exception,
                extra={"agent": self.agent_name, **extra_data}
            )
        else:
            self.logger.error(
                message,
                extra={"agent": self.agent_name, **extra_data}
            )

    def log_warning(self, message: str, **extra_data) -> None:
        """
        Log warning-level messages.

        Args:
            message: Log message
            **extra_data: Additional context data
        """
        self.logger.warning(
            message,
            extra={"agent": self.agent_name, **extra_data}
        )

    def validate_input(self, value: Any, expected_type: type, field_name: str) -> None:
        """
        Validate input type.

        Args:
            value: Input value to validate
            expected_type: Expected type
            field_name: Field name for error messages

        Raises:
            TypeError: If value is not of expected type
            ValueError: If value is None or empty
        """
        if value is None:
            raise ValueError(f"{field_name} cannot be None")

        if not isinstance(value, expected_type):
            raise TypeError(
                f"{field_name} must be {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )

        if isinstance(value, str) and not value.strip():
            raise ValueError(f"{field_name} cannot be empty")

    def validate_dict(self, data: dict, required_keys: list[str], data_name: str = "data") -> None:
        """
        Validate dictionary has all required keys.

        Args:
            data: Dictionary to validate
            required_keys: List of required keys
            data_name: Name of data for error messages

        Raises:
            TypeError: If data is not a dict
            ValueError: If required keys are missing
        """
        if not isinstance(data, dict):
            raise TypeError(f"{data_name} must be a dictionary")

        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            raise ValueError(
                f"{data_name} missing required keys: {', '.join(missing_keys)}"
            )

    def retry_with_backoff(
        self,
        func,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with exponential backoff retry logic.

        Args:
            func: Function to execute
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            backoff_factor: Multiplier for delay between retries
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            Exception: If all retries fail
        """
        import time

        delay = initial_delay
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                self.log_debug(
                    f"Executing {func.__name__}",
                    attempt=attempt + 1,
                    max_attempts=max_retries + 1
                )
                return func(*args, **kwargs)

            except Exception as e:
                last_exception = e

                if attempt == max_retries:
                    self.log_error(
                        f"Max retries ({max_retries}) exceeded for {func.__name__}",
                        exception=e,
                        function=func.__name__
                    )
                    raise

                self.log_warning(
                    f"Attempt {attempt + 1} failed, retrying in {delay}s",
                    function=func.__name__,
                    attempt=attempt + 1,
                    delay=delay,
                    error=str(e)
                )

                time.sleep(delay)
                delay *= backoff_factor

        if last_exception:
            raise last_exception

    def format_response(self, success: bool, data: Any = None, error: str = None) -> dict:
        """
        Format response in standardized format.

        Args:
            success: Whether operation succeeded
            data: Response data
            error: Error message (if applicable)

        Returns:
            Formatted response dictionary
        """
        return {
            "success": success,
            "agent": self.agent_name,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
            "error": error,
        }

    def sanitize_string(self, value: str) -> str:
        """
        Sanitize string input.

        Args:
            value: String to sanitize

        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            return value

        return value.strip()

    def extract_field(self, data: dict, field: str, default: Any = None) -> Any:
        """
        Safely extract field from dictionary.

        Args:
            data: Dictionary to extract from
            field: Field name
            default: Default value if field missing

        Returns:
            Field value or default
        """
        if not isinstance(data, dict):
            return default

        return data.get(field, default)

    def merge_dicts(self, base: dict, override: dict) -> dict:
        """
        Merge two dictionaries with override taking precedence.

        Args:
            base: Base dictionary
            override: Override dictionary

        Returns:
            Merged dictionary
        """
        result = base.copy() if isinstance(base, dict) else {}
        if isinstance(override, dict):
            result.update(override)
        return result
