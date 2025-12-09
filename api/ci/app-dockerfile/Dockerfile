# Multi-stage build for quiz backend API
FROM python:3.11-slim AS build-stage

WORKDIR /build

# Copy requirements and install dependencies system-wide in build-stage
COPY api/server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Final Stage ---
FROM python:3.11-slim AS final-stage

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Add common bin paths to PATH (system-wide and user-local)
ENV PATH=/usr/local/bin:/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5000

# Copy installed packages from build stage (system-wide)
COPY --from=build-stage /usr/local /usr/local

# Copy server code
COPY --chown=appuser:appuser api/server/ /app/
COPY --chown=appuser:appuser common/ /app/common/

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health').read()"

# Set PYTHONPATH to app root so all modules can be imported
ENV PYTHONPATH=/app

# Run server using gunicorn with factory pattern (app:create_app() properly initializes the app)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "app:create_app()"]