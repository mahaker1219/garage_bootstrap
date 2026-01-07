# Garage Test Docker Image
# Container for testing Garage S3 connectivity and data operations

FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Final stage
FROM python:3.11-slim

# Install common utilities for testing and debugging
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    bash \
    jq \
    ca-certificates \
    netcat-openbsd \
    dnsutils \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create app directory
WORKDIR /app

# Copy application code
COPY . /app/garage_test

# Set Python path
ENV PYTHONPATH="/app"

# Create non-root user for security
RUN useradd -m -s /bin/bash tester && \
    chown -R tester:tester /app

USER tester

# Default command - run connectivity tests
ENTRYPOINT ["python", "-m", "garage_test.scripts.test_connectivity"]
CMD ["--help"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import garage_test; print('OK')" || exit 1

# Labels
LABEL org.opencontainers.image.title="Garage Test" \
      org.opencontainers.image.description="Testing service for Garage S3-compatible object storage" \
      org.opencontainers.image.source="https://github.com/mahaker1219/garage_bootstrap" \
      org.opencontainers.image.vendor="garage_bootstrap"
