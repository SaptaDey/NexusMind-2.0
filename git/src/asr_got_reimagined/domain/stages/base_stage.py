"""
Abstract base class for ASR GoT reimagined pipeline stages.
Holds the session data and defines the processing interface.
"""

from abc import ABC, abstractmethod
from src.asr_got_reimagined.domain.models.session_data import GoTProcessorSessionData


class BaseStage(ABC):
    """
    Base stage for the processing pipeline. Subclasses must implement the process method.
    """

    def __init__(self, current_session_data: GoTProcessorSessionData):
        """
        Initialize the stage with the current processing session data.
        """
        self.current_session_data = current_session_data

    @abstractmethod
    def process(self) -> None:
        """
        Execute stage-specific processing logic using the session data.
        """
        raise NotImplementedError("Subclasses must implement the process method.")