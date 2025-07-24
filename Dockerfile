# ─── STAGE 1: Build React ──────────────────────────────────────────────────────
FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ─── STAGE 2: Build Flask+Bundle ───────────────────────────────────────────────
FROM python:3.11-slim

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# install OS deps for PyAudio compilation
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      libglib2.0-0 \
      libsm6 \
      libgtk2.0-0 \
      libgtk-3-0 \
      libxext6 \
      libxrender-dev \
      libgl1-mesa-glx \
      libxrender1 \
      libfontconfig1 \
      libice6 \
      portaudio19-dev \
      libasound2-dev \
      curl \
 && rm -rf /var/lib/apt/lists/*

# copy and install Python requirements
COPY Backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy your Flask app
COPY Backend/ ./

# copy built React assets - this creates the frontend/build directory structure
COPY --from=frontend-build /app/frontend/build ./frontend/build

# Debug commands to see the actual directory structure
RUN echo "=== Current working directory ===" && pwd
RUN echo "=== Directory structure from /app ===" && find /app -type d | head -20
RUN echo "=== Looking for index.html ===" && find /app -name "index.html" -type f
RUN echo "=== Contents of /app ===" && ls -la /app/
RUN echo "=== Contents of /app/frontend/ ===" && ls -la /app/frontend/ || echo "frontend directory not found"
RUN echo "=== Contents of /app/frontend/build/ ===" && ls -la /app/frontend/build/ || echo "frontend/build directory not found"

# switch to non‑root user
USER appuser

EXPOSE 5000

# use python directly for now to see debug output
CMD ["python", "main.py"]