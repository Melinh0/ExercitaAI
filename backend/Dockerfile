FROM python:3.12-slim-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        vim \
        netcat-openbsd \
        gcc \
        python3-dev \
        tesseract-ocr \
        tesseract-ocr-por \
        tesseract-ocr-eng \
        libgl1-mesa-glx \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libgomp1 \
        libreoffice-impress \
        libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.7.9 /uv /uvx /bin/

ENV PATH="/root/.local/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./

ENV UV_PROJECT_ENVIRONMENT=/opt/venv

RUN uv sync --frozen --no-dev --no-install-project

ENV PATH="/opt/venv/bin:$PATH"

COPY . .

EXPOSE 5000