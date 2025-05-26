"""
Module: base_stage
Defines the abstract BaseStage class for ASR GoT processing stages.
"""

from abc import ABC, abstractmethod
from src.asr_got_reimagined.domain.models.session_data import GoTProcessorSessionData

class BaseStage(ABC):
    """
    Abstract base class for all ASR GoT processing stages.
    """

    def __init__(self, current_session_data: GoTProcessorSessionData) -> None:
        """
        Initialize the processing stage with the current session data.
        """
        self.current_session_data = current_session_data

    @abstractmethod
    def execute(self) -> GoTProcessorSessionData:
        """
        Perform the stage-specific processing and return the updated session data.
        """
        pass