# TacticalMesh Agent Dockerfile
# SPDX-License-Identifier: Apache-2.0
#
# Lightweight container for running the Node Agent on edge devices.

FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Create non-root user
RUN useradd -m -u 1000 agentuser && chown -R agentuser:agentuser /app
USER agentuser

# Run the agent
CMD ["python", "-m", "agent.main", "--config", "/app/config.yaml"]
