# Multi-stage build
FROM python:3.11-slim as build-stage

WORKDIR /app

# Install dependencies
COPY multiplayer/server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim as final-stage

WORKDIR /app

# Copy dependencies from build stage
COPY --from=build-stage /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build-stage /usr/local/bin /usr/local/bin

# Copy application code
COPY multiplayer/server/ ./server/
COPY common/ ./common/

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5001/api/health')"

# Set environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/server

# Run with eventlet worker for WebSocket support
# Use wsgi.py entry point to ensure monkey patching happens before imports
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5001", "--timeout", "120", "server.wsgi:app"]
