import uvicorn
from loguru import logger  # Import logger if you want to log here too
import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.asr_got_reimagined.app_setup import create_app
from src.asr_got_reimagined.config import settings

app = create_app()

if __name__ == "__main__":
    logger.info("Starting NexusMind server using Uvicorn...")
    logger.info(
        "Host: {}, Port: {}, Log Level: {}",
        settings.app.host,
        settings.app.port,
        settings.app.log_level,
    )
    uvicorn.run(
        "asr_got_reimagined.main:app",  # Path to the app instance
        host=settings.app.host,
        port=settings.app.port,
        log_level=settings.app.log_level.lower(),  # Uvicorn expects lowercase log level
        reload=True,  # Enable reload for development, disable in production
        # workers=4 # Example for production: number of worker processes
    )
