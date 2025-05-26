"""
git/src/asr_got_reimagined/domain/stages/base_stage.py

Abstract base class for processing stages, without any graph dependency.
"""

from abc import ABC, abstractmethod
from src.asr_got_reimagined.domain.models.session_data import GoTProcessorSessionData


class BaseStage(ABC):
    """
    Abstract base class for all ASRGoT processing stages.
    """

    def __init__(self, current_session_data: GoTProcessorSessionData):
        """
        Initialize the stage with the current session data.
        """
        self.current_session_data = current_session_data

    @abstractmethod
    def execute(self) -> None:
        """
        Execute the stage's core logic.
        Subclasses must implement this method.
        """
        raise NotImplementedError("Subclasses must implement the execute() method.")