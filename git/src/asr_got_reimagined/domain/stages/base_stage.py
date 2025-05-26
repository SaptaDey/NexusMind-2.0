"""
Base class for all processing stages in the ASR GoT reimagined pipeline.
"""

from abc import ABC, abstractmethod
from src.asr_got_reimagined.domain.models.session_data import GoTProcessorSessionData

class BaseStage(ABC):
    """
    Abstract base class for pipeline stages.
    Each stage should implement the execute method to process the shared session data.
    """

    def __init__(self, current_session_data: GoTProcessorSessionData):
        """
        Initialize the stage with the shared session data.
        :param current_session_data: Data passed through the pipeline stages.
        """
        self.current_session_data = current_session_data

    @abstractmethod
    def execute(self) -> None:
        """
        Execute the stage's processing logic.
        Implementations should update current_session_data as needed.
        """
        pass