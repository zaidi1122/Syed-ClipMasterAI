# ──────────────────────────────────────────────────────────────────
#  Jigarzzz❤️ — Hugging Face Spaces Dockerfile
#  Python 3.11 slim + FFmpeg + all deps
# ──────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Install system deps: FFmpeg + fonts
# (ImageMagick removed — codebase renders text via PIL/ImageDraw, not moviepy TextClip)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    fonts-dejavu-core \
    fonts-liberation \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies first (for layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create writable directories for uploads and outputs
RUN mkdir -p uploads outputs && chmod 777 uploads outputs

# Hugging Face Spaces requires the app to listen on port 7860
ENV PORT=7860
ENV HOST=0.0.0.0
# Point moviepy/imageio at system FFmpeg instead of trying to download its own
ENV IMAGEIO_FFMPEG_EXE=/usr/bin/ffmpeg
ENV FFMPEG_BINARY=/usr/bin/ffmpeg

# Expose port
EXPOSE 7860

# Run with gunicorn — 1 worker, 4 threads, 300s timeout for long video jobs
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 300 --access-logfile - app:app
