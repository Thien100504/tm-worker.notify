# ──────────────────────────────────────────────
# Notification Service - Dockerfile
# ──────────────────────────────────────────────
FROM python:3.11-slim

# Set labels
LABEL maintainer="TaskManager Team"
LABEL service="notification-service"

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the service
CMD ["python", "main.py"]
