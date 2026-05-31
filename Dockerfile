# Multi-stage Dockerfile for LedgerFlow
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create writable directory for SQLite database
RUN mkdir -p /app/data && chmod 777 /app/data

# Expose port (Render uses PORT env variable)
EXPOSE 8000

# Run the application - use PORT env var if set (Render), default to 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
