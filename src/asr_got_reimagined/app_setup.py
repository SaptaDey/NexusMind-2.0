import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger  # type: ignore

# Add src directory to Python path if not already there
# This must be done before other project imports
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from src.asr_got_reimagined.api.routes.mcp import mcp_router  # noqa: E402
from src.asr_got_reimagined.domain.services.got_processor import (  # noqa: E402
    GoTProcessor,
)
from src.asr_got_reimagined.simple_config import settings  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app startup and shutdown events.
    This replaces the deprecated @app.on_event decorators.
    """
    # Startup
    logger.info("Application startup sequence initiated.")
    # Any other async initializations can go here.
    logger.info("Application startup completed successfully.")

    yield  # This is where the app runs

    # Shutdown
    logger.info("Application shutdown sequence initiated.")
    # Clean up resources
    if hasattr(app.state, "got_processor") and hasattr(
        app.state.got_processor, "shutdown_resources"
    ):
        try:
            await app.state.got_processor.shutdown_resources()
        except Exception as e:
            logger.error(f"Error shutting down GoTProcessor: {e}")
    logger.info("Application shutdown completed.")


def create_app() -> FastAPI:
    """
    Creates and configures the FastAPI application instance.
    """
    # Configure logger
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.app.log_level.upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )
    logger.info(
        "Logger configured with level: {}", settings.app.log_level.upper()
    )  # Create FastAPI app with lifespan
    app = FastAPI(
        title=settings.app.name,
        version=settings.app.version,
        description="NexusMind: Intelligent Scientific Reasoning through Graph-of-Thoughts MCP Server",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    # Store GoTProcessor instance on app.state
    app.state.got_processor = GoTProcessor(settings=settings)
    logger.info("GoTProcessor instance created and attached to app state.")

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )
    logger.info("CORS middleware configured to allow all origins.")

    # Add health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        logger.debug("Health check endpoint was called.")  # type: ignore
        return {"status": "healthy", "version": settings.app.version}

    # Include routers
    app.include_router(mcp_router, prefix="/mcp", tags=["MCP"])
    logger.info("API routers included. MCP router mounted at /mcp.")

    logger.info(
        "{} v{} application instance created.", settings.app.name, settings.app.version
    )
    return app
