FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# workspace 依赖清单（lock 在根目录）
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/pyproject.toml
COPY mcp-server/pyproject.toml mcp-server/pyproject.toml
COPY cli/pyproject.toml cli/pyproject.toml
RUN uv sync --frozen --no-install-project || uv sync --no-install-project

# 复制源码
COPY mcp-server/server.py ./server.py
COPY mcp-server/tools ./tools

# MCP Server 通过 stdio 与 Open WebUI 通信
CMD ["uv", "run", "python", "server.py"]
