# Stage 1: Builder
FROM python:3.11.12-slim AS builder

# Install build-time dependencies (curl for rust)
RUN apt-get update && \
    apt-get install --no-install-recommends -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Rust for pydantic compilation
ENV PATH="/root/.cargo/bin:${PATH}"
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain stable --profile minimal

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt requirements-selenium.txt ./
RUN pip install --no-cache-dir -r requirements.txt

ARG SELENIUM_SUPPORT=true
RUN if [ "$SELENIUM_SUPPORT" = "true" ]; then \
        pip install --no-cache-dir -r requirements-selenium.txt; \
    fi

# Stage 2: Final Runtime Image
FROM python:3.11.12-slim

ARG SELENIUM_SUPPORT=true

# Install runtime system dependencies conditionally
RUN if [ "$SELENIUM_SUPPORT" = "true" ]; then \
        apt-get update && \
        apt-get install --no-install-recommends -y ffmpeg flac && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/*; \
    fi

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Activate virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY finanze /finanze
COPY ./resources /finanze/resources

ENTRYPOINT ["python", "finanze"]