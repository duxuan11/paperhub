FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# 先复制依赖清单以利用缓存
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project || uv sync --no-install-project

# 复制源码与顶层包
COPY backend/app ./app
COPY publishers ./publishers
COPY skills ./skills

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
