# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install uv (modern Python package manager)
RUN pip install --no-cache-dir uv

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --all-groups

# Copy the rest of the code
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Default command
CMD ["python", "-m", "src.app.main"]
