"""Base class for all ASR-GoT processing stages."""

from abc import ABC, abstractmethod
from src.asr_got_reimagined.domain.models.session_data import GoTProcessorSessionData


class BaseStage(ABC):
    """
    Abstract base class for ASR-GoT pipeline stages.

    Each stage receives the current session data and must implement
    the `execute` method to process and return updated session data.
    """

    def __init__(self, current_session_data: GoTProcessorSessionData):
        """
        Initialize the stage with the current session data.

        Args:
            current_session_data (GoTProcessorSessionData): The session data to be processed.
        """
        self.current_session_data = current_session_data

    @abstractmethod
    def execute(self) -> GoTProcessorSessionData:
        """
        Execute the stage's processing logic.

        Returns:
            GoTProcessorSessionData: The updated session data after stage execution.
        """
        pass