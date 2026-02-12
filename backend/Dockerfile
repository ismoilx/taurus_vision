# # ============================================================================
# # STAGE 1: Builder (Dependencies Installation)
# # ============================================================================
# FROM python:3.12-slim as builder

# # Set environment variables
# ENV PYTHONDONTWRITEBYTECODE=1 \
#     PYTHONUNBUFFERED=1 \
#     PIP_NO_CACHE_DIR=1 \
#     PIP_DISABLE_PIP_VERSION_CHECK=1

# # Install system dependencies required for Python packages
# # libgl1, libglib2.0: Required for opencv-python-headless (future ML integration)
# # postgresql-client: For database healthchecks
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     libpq-dev \
#     libgl1 \
#     libglib2.0-0 \
#     && rm -rf /var/lib/apt/lists/*

# # Create virtual environment
# RUN python -m venv /opt/venv
# ENV PATH="/opt/venv/bin:$PATH"

# # Copy and install dependencies
# COPY requirements.txt .
# RUN pip install --upgrade pip && \
#     pip install -r requirements.txt

# # ============================================================================
# # STAGE 2: Runtime (Production Image)
# # ============================================================================
# FROM python:3.12-slim

# # Metadata
# LABEL maintainer="Taurus Vision <info@taurusvision.com>"
# LABEL description="Taurus Vision Backend API - Production Image"
# LABEL version="0.1.0"

# # Set environment variables
# ENV PYTHONDONTWRITEBYTECODE=1 \
#     PYTHONUNBUFFERED=1 \
#     PATH="/opt/venv/bin:$PATH" \
#     PYTHONPATH=/app

# # Install only runtime dependencies (no build tools)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     libpq5 \
#     libgl1 \
#     libglib2.0-0 \
#     curl \
#     && rm -rf /var/lib/apt/lists/*

# # Create non-root user for security
# # UID 1000 is standard for non-root users
# RUN groupadd -r taurus --gid=1000 && \
#     useradd -r -g taurus --uid=1000 --home-dir=/app --shell=/bin/bash taurus

# # Create application directory
# WORKDIR /app

# # Copy virtual environment from builder
# COPY --from=builder /opt/venv /opt/venv

# # Copy application code
# COPY --chown=taurus:taurus ./app ./app
# COPY --chown=taurus:taurus ./alembic ./alembic
# COPY --chown=taurus:taurus ./alembic.ini ./alembic.ini

# # Create directories for data with proper permissions
# RUN mkdir -p /app/data/logs /app/data/images && \
#     chown -R taurus:taurus /app/data

# # Switch to non-root user
# USER taurus

# # Expose port
# EXPOSE 8000

# # Health check
# # Checks if API is responding every 30 seconds
# HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
#     CMD curl -f http://localhost:8000/health || exit 1

# # Default command
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]


#############################################################################################################################################










# ============================================================================
# STAGE 1: Builder (Dependencies Installation)
# ============================================================================
FROM python:3.12-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for Python packages
# libgl1, libglib2.0: Required for opencv-python-headless (YOLOv11/CV)
# postgresql-client: For database healthchecks
# libgomp1: Required for PyTorch multiprocessing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ============================================================================
# STAGE 2: Runtime (Production Image)
# ============================================================================
FROM python:3.12-slim

# Metadata
LABEL maintainer="Taurus Vision <info@taurusvision.com>"
LABEL description="Taurus Vision Backend API - Production Image"
LABEL version="0.1.0"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
# UID 1000 is standard for non-root users
RUN groupadd -r taurus --gid=1000 && \
    useradd -r -g taurus --uid=1000 --home-dir=/app --shell=/bin/bash taurus

# Create application directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=taurus:taurus ./app ./app
COPY --chown=taurus:taurus ./alembic ./alembic
COPY --chown=taurus:taurus ./alembic.ini ./alembic.ini

# Create directories for data with proper permissions
RUN mkdir -p /app/data/logs /app/data/images && \
    chown -R taurus:taurus /app/data

# Switch to non-root user
USER taurus

# Expose port
EXPOSE 8000

# Health check
# Checks if API is responding every 30 seconds
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]