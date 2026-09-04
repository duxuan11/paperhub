FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project || uv sync --no-install-project

COPY server.py ./server.py
COPY tools ./tools

# MCP Server 通过 stdio 与 Open WebUI 通信
CMD ["uv", "run", "python", "server.py"]
