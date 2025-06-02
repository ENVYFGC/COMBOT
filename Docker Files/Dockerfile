# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set metadata
LABEL maintainer="ENVYFGC <contact@envyfgc.com>"
LABEL description="Combot - Universal Fighting Game Combo Bot for Discord"
LABEL version="2.0.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for security
RUN groupadd -r combot && useradd -r -g combot combot

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY combot/ ./combot/
COPY run.py .
COPY README.md .
COPY LICENSE .

# Create data directory for bot configuration
RUN mkdir -p /app/data && chown -R combot:combot /app

# Switch to non-root user
USER combot

# Set default data directory
ENV CONFIG_FILENAME=/app/data/character_bot_data.json

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Expose port (not needed for Discord bot, but good practice)
EXPOSE 8080

# Default command
CMD ["python", "run.py"]

# Alternative entry points
# CMD ["python", "-m", "combot"]
# CMD ["combot-run"]
