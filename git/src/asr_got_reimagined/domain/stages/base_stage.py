from abc import ABC, abstractmethod
import logging
from src.asr_got_reimagined.domain.models.session_data import GoTProcessorSessionData

logger = logging.getLogger(__name__)

class BaseStage(ABC):
    """
    Abstract base class for processing stages in the ASR GoT pipeline.
    """

    def __init__(self, current_session_data: GoTProcessorSessionData):
        """
        Initialize with the shared GoTProcessorSessionData.
        """
        self.current_session_data = current_session_data

    @abstractmethod
    def execute(self) -> None:
        """
        Main execution logic for the stage.
        """
        pass

    def run(self) -> None:
        """
        Execute the stage with standardized logging and error handling.
        """
        stage_name = self.__class__.__name__
        logger.info(f"Running stage: {stage_name}")
        try:
            self.execute()
            logger.info(f"Finished stage: {stage_name}")
        except Exception:
            logger.exception(f"Error in stage: {stage_name}")
            raise