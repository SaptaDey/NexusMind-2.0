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
        """
        Removes a previously added logging handler by its identifier.
        
        Args:
            handler_id: The integer ID of the handler to remove.
        """
        ...

    def add(self, sink: Any, **kwargs: Any) -> int:
        """
        Adds a new logging handler (sink) to the logger.
        
        The sink determines where log messages are sent, such as a file, stream, or custom callable. Additional keyword arguments can be provided to configure the handler's behavior.
        
        Args:
            sink: The destination for log messages (e.g., file path, stream, or callable).
            **kwargs: Optional configuration parameters for the handler.
        
        Returns:
            An integer ID representing the added handler, which can be used to remove it later.
        """
        ...

    @overload
    def catch(
        self, exception: Callable[..., T]
    ) -> Callable[..., T]:  # T should be defined now
        """
        Decorator that wraps a callable to catch and log exceptions during its execution.
        
        Returns:
            A callable with the same signature as the input, enhanced to log any exceptions raised.
        """
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
        """
        Decorator that wraps a function to catch and log specified exceptions.
        
        Args:
            exception: List of exception types to catch. If not provided, all exceptions are caught.
            default: Value to return if a caught exception occurs.
            message: Log message to use when an exception is caught.
            onerror: Callback invoked when an exception is caught.
            level: Log level for the caught exception.
            reraise: If True, re-raises the exception after logging.
            exclude: List of exception types to ignore and not catch.
        
        Returns:
            A decorator that wraps a function, catching and logging the specified exceptions.
        """
        ...  # type: ignore[empty-body]

    def catch(self, *args: Any, **kwargs: Any) -> Any:
        """
        Decorator that wraps a function to catch and log exceptions.
        
        Returns:
            The decorated function with automatic exception handling and logging.
        """
        ...  # type: ignore[empty-body]


# Create a global logger instance
logger = Logger()
