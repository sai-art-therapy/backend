# syntax=docker/dockerfile:1.7

FROM python:3.14.7-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/gdam

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --requirement requirements.txt

RUN groupadd --system --gid 10001 gdam \
    && useradd --system --uid 10001 --gid gdam --create-home --home-dir /home/gdam --shell /usr/sbin/nologin gdam

COPY --chown=gdam:gdam app ./app
COPY --chown=gdam:gdam scripts ./scripts
COPY --chown=gdam:gdam deploy/docker-entrypoint.sh /usr/local/bin/gdam-entrypoint

RUN chmod 0555 /usr/local/bin/gdam-entrypoint \
    && mkdir -p uploads/htp/original uploads/htp/result app/db/chroma ml_models/yolo \
    && chown -R gdam:gdam uploads app/db/chroma ml_models

USER gdam

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3).read()"]

ENTRYPOINT ["gdam-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
