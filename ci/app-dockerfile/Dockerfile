# Multi-stage build for quiz backend API
FROM python:3.11-slim AS build-stage

WORKDIR /build

# Copy requirements and install dependencies system-wide in build-stage
# Installing system-wide (into /usr/local) avoids using per-user
# .local layout and makes it straightforward to copy system python
# packages and executables into the final image.
COPY src/requirements.txt .
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
# When installing system-wide in build-stage, packages are placed under
# /usr/local (bin, lib, etc.). Copy that directory into the final image
# so the installed packages and executables (gunicorn, etc.) are available.
COPY --from=build-stage /usr/local /usr/local

# Copy application code (exclude db.json - initialized via mongodb-init Job)
COPY --chown=appuser:appuser src/ /app/

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health').read()"

# Set PYTHONPATH to include both db and python directories
ENV PYTHONPATH=/app/db:/app/python:$PYTHONPATH

# Stay in /app so both db/ and python/ modules can be imported
# Use python.main:app to specify the module path for gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "python.main:app"]