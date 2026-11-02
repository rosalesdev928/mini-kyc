# Multi-stage build: React frontend -> static files served by the FastAPI backend.
# One deployable image, which keeps the hosting setup to "app + MySQL".

FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STATIC_DIR=/srv/static \
    DATABASE_DIR=/srv/database
WORKDIR /srv
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY database ./database
COPY --from=frontend-build /frontend/dist ./static

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
# Hosting platforms (Render, Railway) inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
