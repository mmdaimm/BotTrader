# Production Dockerfile for Railway.app Deployment
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies list and install
COPY WebTraderBot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY WebTraderBot /app

# Start FastAPI Uvicorn Server
CMD uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8080}
