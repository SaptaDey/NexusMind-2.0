"""
BaseStage: Abstract base for all processing stages in the ASRGoT reimagined pipeline.
"""

import abc

from src.asr_got_reimagined.domain.models.processor_session_data import GoTProcessorSessionData


class BaseStage(abc.ABC):
    """
    Abstract base class for pipeline stages.
    Each stage operates solely on GoTProcessorSessionData.
    """

    def __init__(self, current_session_data: GoTProcessorSessionData):
        """
        Initialize the stage with the current session data.
        """
        self.current_session_data = current_session_data

    @abc.abstractmethod
    def execute(self) -> None:
        """
        Execute the stage's processing logic.
        Must be implemented by all subclasses.
        """
        raise NotImplementedError("Subclasses must implement the execute() method")