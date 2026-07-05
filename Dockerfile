# Production image for Render (and any other single-container host):
# builds the frontend, then serves API + SPA from one FastAPI process.

# --- Stage 1: build the frontend ---
FROM node:22-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
# API is served under /api in all environments -- the frontend default.
RUN npm run build

# --- Stage 2: backend + built frontend ---
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend-build /build/dist ./static

ENV STATIC_DIR=/app/static
EXPOSE 8000

# Render injects PORT; default to 8000 for local runs.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
