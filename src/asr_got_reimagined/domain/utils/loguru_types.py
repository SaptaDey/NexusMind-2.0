"""
Type stubs for loguru to help with static type checking.
This file provides type annotations for the loguru module to suppress import and type errors.
"""
from typing import Any, Callable, List, TypeVar, overload

T = TypeVar('T')

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
    def catch(self, exception: Callable[..., T]) -> Callable[..., T]:
        ...

    @overload
    def catch(self, exception: List[Exception] = ..., *,
              default: Any = ...,
              message: str = ...,
              onerror: Callable[..., Any] = ...,
              level: str = ...,
              reraise: bool = ...,
              exclude: List[Exception] = ...) -> Callable[[Callable[..., T]], Callable[..., T]]:
        ...

    def catch(self, *args: Any, **kwargs: Any) -> Any:
        """Catch exceptions in a function and log them."""
        ...

# Create a global logger instance
logger = Logger()
