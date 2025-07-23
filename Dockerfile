# ─── STAGE 1: Build React ──────────────────────────────────────────────────────
FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend
# copy package.json (and lockfile) and install
COPY frontend/package*.json ./
RUN npm ci
# copy the rest of your React source, build to /app/frontend/build
COPY frontend/ ./
RUN npm run build

# ─── STAGE 2: Build Flask+Bundle ───────────────────────────────────────────────
FROM python:3.11-slim

# set a non‑root user (optional but recommended)
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# install OS deps for any Python packages that need compilation
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      libglib2.0-0 \
      libsm6 \
      libgtk2.0-0 \
      libgtk-3-0 \
      curl \
 && rm -rf /var/lib/apt/lists/*

# copy and install Python requirements
COPY Backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy your Flask app
COPY Backend/ ./

# copy built React assets into your Flask static folder
COPY --from=frontend-build /app/frontend/build ./frontend/build

# switch to non‑root user
USER appuser

# expose the port your Flask app listens on
EXPOSE 5000

# use gunicorn for production
CMD ["gunicorn", "main:app", "-b", "0.0.0.0:5000", "--workers", "3"]
