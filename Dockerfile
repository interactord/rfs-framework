# RFS Framework Docker Image
# Version: 4.6.3
# General purpose Docker image for development and testing

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml setup.py README.md ./
COPY src/ ./src/

# Install RFS Framework
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e .

# RFS Framework 환경변수 기본값
ENV RFS_ENVIRONMENT=development \
    RFS_LOG_LEVEL=DEBUG \
    RFS_LOG_FORMAT=text \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# Default port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command - RFS CLI
CMD ["rfs-cli", "--help"]