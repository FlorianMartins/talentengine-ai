# syntax=docker/dockerfile:1.7
# ---- front-end build -------------------------------------------------------------------------
FROM node:20-alpine AS web
# Path prefix when served under a sub-path (e.g. --build-arg VITE_BASE=/talentengine/); "/" by default.
ARG VITE_BASE=/
ENV VITE_BASE=${VITE_BASE}
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- runtime ---------------------------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TE_DATA_DIR=/data \
    TE_FRONTEND_DIST=/app/frontend/dist \
    TE_NER=spacy
WORKDIR /app
# git reads public repositories' file trees for the sandbox without using the GitHub API quota.
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml backend/README.md backend/
COPY backend/talentengine backend/talentengine
RUN pip install --no-cache-dir "./backend[anthropic,ner]" \
 && python -m spacy download fr_core_news_sm \
 && python -m spacy download en_core_web_sm \
 && useradd --system --uid 10001 --home /app talentengine \
 && mkdir -p /data && chown talentengine /data
COPY --from=web /web/dist /app/frontend/dist
USER talentengine
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["talentengine", "serve", "--host", "0.0.0.0", "--port", "8000"]
