# PaperHub 常用命令（原生本地运行）

SHELL := /bin/bash
.NOTPARALLEL:

.PHONY: help sync bootstrap services db frontend mcp cli demo test build stop

help:
	@echo "PaperHub 命令："
	@echo "  make sync        首次/更新：在根目录同步共享 venv (uv sync)"
	@echo "  make bootstrap   安装原生依赖(postgres/redis/minio)并初始化"
	@echo "  make services    启动 postgres/redis/minio 本地服务"
	@echo "  make frontend    启动 Next.js 前端 (等价 cd frontend && npm run dev)"
	@echo "  make mcp         启动 MCP Server (stdio)"
	@echo "  make cli         运行 CLI"
	@echo "  make demo        生成 demo 论文并跑通一次端到端"
	@echo "  make test        后端 pytest"
	@echo "  make build       前端构建检查"
	@echo "  make stop        停止本地服务"
	@echo ""
	@echo "后端/worker 用 npm 启动（不再用 make）："
	@echo "  cd backend && npm run server   启动 FastAPI 后端 (端口 8000)"
	@echo "  cd backend && npm run worker   启动 Arq worker"

sync:
	uv sync

bootstrap:
	bash scripts/bootstrap-native.sh

services:
	bash scripts/dev-services.sh

db:
	bash scripts/init-db.sh

frontend:
	cd frontend && npm run dev

mcp:
	cd mcp-server && uv run python server.py

cli:
	cd cli && uv run paperhub --help

demo:
	bash scripts/run_demo_once.sh

test:
	cd backend && uv run pytest -q

build:
	cd frontend && npm run build

stop:
	bash scripts/dev-services.sh stop
