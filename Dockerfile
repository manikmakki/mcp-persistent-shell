# Multi-stage build for MCP Persistent Shell Server
# Base: debian-slim for good APT support and small footprint

# Build stage
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.12-slim-bookworm

# Install runtime dependencies and utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    wget \
    git \
    ca-certificates \
    # Python development tools
    python3-venv \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1000 mcpuser && \
    useradd -m -u 1000 -g mcpuser -s /bin/bash mcpuser

# Create workspace directory
RUN mkdir -p /workspace && \
    chown mcpuser:mcpuser /workspace

# Create config directory
RUN mkdir -p /etc/mcp-persistent-shell && \
    chown mcpuser:mcpuser /etc/mcp-persistent-shell

# Copy Python packages from builder
COPY --from=builder /root/.local /home/mcpuser/.local

# Copy application code
COPY --chown=mcpuser:mcpuser src /app/src
COPY --chown=mcpuser:mcpuser pyproject.toml /app/
COPY --chown=mcpuser:mcpuser config/security.yaml /etc/mcp-persistent-shell/security.yaml

# Set working directory
WORKDIR /app

# Add local bin to PATH
ENV PATH="/home/mcpuser/.local/bin:${PATH}"
ENV PYTHONPATH="/app/src"

# Default environment (can be overridden)
ENV MCP_SHELL_HOST=0.0.0.0
ENV MCP_SHELL_PORT=3000
ENV MCP_SHELL_LOG_LEVEL=info
ENV MCP_SHELL_LOG_FORMAT=json

# Switch to non-root user
USER mcpuser

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Run server
CMD ["python", "-m", "mcp_persistent_shell"]
