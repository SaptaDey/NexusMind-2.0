from typing import Any, Callable, TypeVar, Union, overload

# No need to import unused modules

_T = TypeVar("_T")

class Logger:
    def debug(self, __message: str, *args: Any, **kwargs: Any) -> None: ...
    def info(self, __message: str, *args: Any, **kwargs: Any) -> None: ...
    def warning(self, __message: str, *args: Any, **kwargs: Any) -> None: ...
    def error(self, __message: str, *args: Any, **kwargs: Any) -> None: ...
    def critical(self, __message: str, *args: Any, **kwargs: Any) -> None: ...
    def exception(self, __message: str, *args: Any, **kwargs: Any) -> None: ...
    def log(self, __level: int, __message: str, *args: Any, **kwargs: Any) -> None: """
Logs a message with a specified integer log level.

Args:
    __level: The log level as an integer.
    __message: The message to log.
"""
...
    def remove(self, __handler_id: int = ...) -> None: """
Removes a previously added log handler by its handler ID.

Args:
    __handler_id: The identifier of the handler to remove. If omitted, removes all handlers.
"""
...
    def add(self, sink: Any, **kwargs: Any) -> int: """
Adds a new log message sink and returns its handler ID.

Args:
    sink: The destination for log messages, such as a file, stream, or callable.

Returns:
    An integer handler ID that can be used to remove the sink later.
"""
...

    @overload
    def catch(self, function: Callable[..., _T]) -> Callable[..., _T]: """
Decorator that wraps a function to automatically catch and log exceptions.

Returns:
    A wrapped function that logs any exceptions raised during execution.
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
        Decorator factory that wraps a function to catch and log specified exceptions.
        
        Args:
            exception: Exception type or tuple of types to catch.
            level: Log level to use when logging the exception.
            reraise: Whether to re-raise the exception after logging.
            message: Custom log message to use when an exception is caught.
            onerror: Callable invoked when an exception is caught.
        
        Returns:
            A decorator that wraps a function, logging exceptions according to the specified parameters.
        """
        ...

# Removed the non-overload decorated 'catch' method for stub file compliance
# def catch(self, *args: Any, **kwargs: Any) -> Any: ...

logger: Logger = ...

def configure(**kwargs: Any) -> None: """
Configures global logging settings.

Accepts arbitrary keyword arguments to customize logger behavior.
"""
...
