# Stage 1: Build stage - Install dependencies using Poetry
FROM python:3.13.3-slim-bookworm@sha256:914bf5c12ea40a97a78b2bff97fbdb766cc36ec903bfb4358faf2b74d73b555b AS builder

# Set working directory
WORKDIR /opt/poetry

# Install system dependencies needed for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_VERSION=1.8.2
RUN pip install "poetry==${POETRY_VERSION}"

# Copy only files necessary for dependency installation
COPY poetry.lock pyproject.toml ./

# Configure Poetry to not create a virtual environment in the project directory
# Instead, it will install into the system Python environment (or a venv we specify later)
RUN poetry config virtualenvs.create false && \
    poetry lock --no-update && \
    poetry install --no-dev --no-interaction --no-ansi

# Stage 2: Runtime stage - Create the final application image
FROM python:3.13.3-slim-bookworm@sha256:914bf5c12ea40a97a78b2bff97fbdb766cc36ec903bfb4358faf2b74d73b555b AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Set path for Poetry-installed packages and the source directory
    PYTHONPATH="/app" \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Create a non-root user and group
RUN groupadd -r appuser && useradd --no-log-init -r -g appuser appuser

# Copy installed dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application source code
COPY ./src ./src
COPY ./config ./config
# This ensures the application structure is maintained correctly for imports

# Ensure the entrypoint script (if any) is executable
# COPY ./entrypoint.sh /entrypoint.sh
# RUN chmod +x /entrypoint.sh

# Change ownership to the appuser
RUN chown -R appuser:appuser ${APP_HOME} ./config

# Switch to the non-root user
USER appuser

# Expose the port the app runs on (default for FastAPI/Uvicorn is 8000)
# This will be mapped in docker-compose.yml
EXPOSE 8000

# Command to run when the container starts
# Use the full module path from the src directory
CMD ["uvicorn", "src.asr_got_reimagined.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Optional entrypoint script if more complex startup logic is needed
# ENTRYPOINT ["/entrypoint.sh"]