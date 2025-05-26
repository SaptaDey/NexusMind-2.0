"""Base class for all processing stages in the ASR GoT pipeline."""

from abc import ABC, abstractmethod

from ..models.session_data import GoTProcessorSessionData


class BaseStage(ABC):
    """Abstract base class for processing stages."""

    def __init__(self, current_session_data: GoTProcessorSessionData):
        """
        Initialize the stage with current session data.

        :param current_session_data: Session data for the GoT processor.
        """
        self.current_session_data = current_session_data

    @abstractmethod
    def execute(self) -> None:
        """
        Execute the stage's processing logic.

        Subclasses must implement this method.
        """
        raise NotImplementedError("Subclasses must implement this method.")