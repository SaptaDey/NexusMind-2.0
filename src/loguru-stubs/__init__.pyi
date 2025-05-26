from typing import Any, Callable, TypeVar, Union, overload

# No need to import unused modules

_T = TypeVar("_T")

class Logger:
    def debug(self, __message: str, *args: Any, **kwargs: Any) -> None: ...
    def info(self, __message: str, *args: Any, **kwargs: Any) -> None: ...
    def warning(self, __message: str, *args: Any, **kwargs: Any) -> None: ...
    def error(self, __message: str, *args: Any, **kwargs: Any) -> None: """
Logs a message with severity 'ERROR'.

Use this method to record error events that might still allow the application to continue running.
"""
...
    def critical(self, __message: str, *args: Any, **kwargs: Any) -> None: """
Logs a message with critical severity.

Use this method to record events that indicate a serious error or failure.
"""
...
    def exception(self, __message: str, *args: Any, **kwargs: Any) -> None: """
Logs a message with exception information at the exception level.

Use this method to log an error message along with the current exception traceback if called within an exception handler.
"""
...
    def log(self, __level: int, __message: str, *args: Any, **kwargs: Any) -> None: """
Logs a message with a specified severity level.

Args:
    __level: Integer representing the log severity level.
    __message: The message to be logged.
"""
...
    def remove(self, __handler_id: int = ...) -> None: """
Removes a logging handler identified by its handler ID.

Args:
    __handler_id: The integer ID of the handler to remove.
"""
...
    def add(self, sink: Any, **kwargs: Any) -> int: """
Adds a logging sink and returns its handler ID.

Args:
	sink: The destination for log messages, such as a file, stream, or callable.

Returns:
	The integer handler ID assigned to the added sink.
"""
...

    @overload
    def catch(self, function: Callable[..., _T]) -> Callable[..., _T]: """
Decorator that wraps a function to catch and log any exceptions raised during its execution.

Returns:
    The wrapped function with automatic exception logging.
"""
...

    @overload
    def catch(
        self,
        exception: Union[type[BaseException], tuple[type[BaseException], ...]] = ...,
        *,
        level: str = ...,
        reraise: bool = ...,
        message: str = ...,
        onerror: Callable[..., Any] = ...,
    ) -> Callable[[Callable[..., _T]], Callable[..., _T]]: """
        Creates a decorator that catches specified exceptions in a function and logs them.
        
        The decorator logs exceptions of the given type(s) at the specified log level, optionally re-raises them, logs a custom message, and can execute a callback when an exception is caught.
        
        Args:
            exception: The exception type or tuple of types to catch.
            level: The log level to use when logging the exception.
            reraise: If True, re-raises the exception after logging.
            message: Custom message to log when an exception is caught.
            onerror: Callable to execute if an exception is caught.
        
        Returns:
            A decorator that wraps a function, logging and optionally handling exceptions as specified.
        """
        ...

# Removed the non-overload decorated 'catch' method for stub file compliance
# def catch(self, *args: Any, **kwargs: Any) -> Any: ...

logger: Logger = ...

def configure(**kwargs: Any) -> None: """
Configures the logging system using the specified keyword arguments.

Accepts arbitrary configuration options to customize logging behavior.
"""
...
