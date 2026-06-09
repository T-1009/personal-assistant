FROM ghcr.io/astral-sh/uv:python3.12-bookworm

WORKDIR /app

# Install dependencies into system Python (not a venv) for reliable container startup
ENV UV_PROJECT_ENVIRONMENT=/usr/local

# Copy dependency files first for Docker layer caching
COPY personal-assistant-service/pyproject.toml personal-assistant-service/uv.lock ./

# Install dependencies (production only)
RUN uv sync --frozen --no-dev

# Copy application code
COPY personal-assistant-service/app/ ./app/
COPY personal-assistant-service/.agentarts_config.yaml ./
COPY personal-assistant-service/config.yaml ./

EXPOSE 8080

# Use system Python directly — no uv run, no venv, no shell tricks
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
