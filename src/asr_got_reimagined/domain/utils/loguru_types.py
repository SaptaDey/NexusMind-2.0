"""
Type stubs for loguru to help with static type checking.
This file provides type annotations for the loguru module to suppress import and type errors.
"""

from typing import (
    Any,
    Callable,
    TypeVar,
    overload,
)  # Removed List

T = TypeVar("T")  # Defined T


class Logger:
    """Type stub for loguru.Logger class."""

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log info level message."""
        ...

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log debug level message."""
        ...

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log warning level message."""
        ...

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log error level message."""
        ...

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log critical level message."""
        ...

    def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log exception with traceback."""
        ...

    def remove(self, handler_id: int) -> None:
        """Remove a previously added handler."""
        ...

    def add(self, sink: Any, **kwargs: Any) -> int:
        """Add a new handler to the logger."""
        ...

    @overload
    def catch(
        self, exception: Callable[..., T]
    ) -> Callable[..., T]:  # T should be defined now
        ...  # type: ignore[empty-body]

    @overload
    def catch(
        self,
        exception: list[Exception] = ...,
        *,  # Changed List to list
        default: Any = ...,
        message: str = ...,
        onerror: Callable[..., Any] = ...,
        level: str = ...,
        reraise: bool = ...,
        exclude: list[Exception] = ...,
    ) -> Callable[
        [Callable[..., T]], Callable[..., T]
    ]:  # Changed List to list, T should be defined
        ...  # type: ignore[empty-body]

    def catch(self, *args: Any, **kwargs: Any) -> Any:
        """Catch exceptions in a function and log them."""
        ...  # type: ignore[empty-body]


# Create a global logger instance
logger = Logger()
