# Stage 1: Build stage
FROM python:3.14-alpine AS builder

# Install uv from the official binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install build dependencies (Alpine needs these for some C-extension packages)
RUN apk add --no-cache gcc musl-dev libffi-dev

# Copy only the dependency files first to leverage Docker caching
COPY pyproject.toml uv.lock ./

# Install dependencies globally in the builder stage
RUN uv pip install --no-cache --system -r pyproject.toml

# Stage 2: Final Runtime Image
FROM python:3.14-alpine

WORKDIR /app

# Copy only the installed packages from the builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy your source code
COPY . .

# Run your script
CMD ["python", "main.py"]