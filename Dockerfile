FROM python:3.11-slim

LABEL org.opencontainers.image.title="Bond Integration for Unfolded Circle Remote"
LABEL org.opencontainers.image.description="Control Bond-connected ceiling fans, fireplaces, and other devices"
LABEL org.opencontainers.image.vendor="Meir Miyara"
LABEL org.opencontainers.image.licenses="MPL-2.0"
LABEL org.opencontainers.image.url="https://github.com/mase1981/uc-intg-bond"
LABEL org.opencontainers.image.source="https://github.com/mase1981/uc-intg-bond"

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY driver.json .
COPY uc_intg_bond/ ./uc_intg_bond/

# Create directories for config and logs
RUN mkdir -p /app/config /app/logs

# Set environment variables
ENV UC_CONFIG_HOME=/app/config
ENV UC_INTEGRATION_INTERFACE=0.0.0.0
ENV UC_INTEGRATION_HTTP_PORT=9090
ENV UC_DISABLE_MDNS_PUBLISH=false
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:9090/ || exit 1

# Run the integration
CMD ["python", "-m", "uc_intg_bond.driver"]