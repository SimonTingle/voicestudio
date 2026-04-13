# ==========================================
# Builder Stage: Compile React Frontend
# ==========================================
FROM oven/bun:1-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy frontend specifications
COPY frontend/package.json ./
COPY frontend/bun.lock ./

# Install dependencies fast
RUN bun install --frozen-lockfile

# Copy frontend source and build static files
COPY frontend/ ./
# Output goes to /app/frontend/dist
RUN bun run build

# ==========================================
# Runtime Stage: Python & PyTorch Backend
# ==========================================
FROM pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime AS runtime
WORKDIR /app

# Enable unbuffered logs and optimizations
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/omnivoice_data/huggingface

# Install system dependencies (FFmpeg is critical for torchaudio/scene splitting)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install `uv` for blazing-fast reliable pip resolution
RUN pip install --no-cache-dir uv

# Copy python packaging specs
COPY pyproject.toml uv.lock ./

# Native wheels from PyPI embed CUDA matching `torch >= 2.4` standard index
# By installing via `uv`, the process completes exponentially faster
RUN uv pip install --system --no-cache -e .  

# Copy application source
COPY backend/ ./backend/
COPY omnivoice/ ./omnivoice/

# Copy the pre-built React frontend from the builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose the single unified API and UI port
EXPOSE 8000

# Mount points for persistent data (sqlite db, user voices, huggingface cache)
VOLUME ["/app/omnivoice_data"]

# Bind to 0.0.0.0 for external access
ENTRYPOINT ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
