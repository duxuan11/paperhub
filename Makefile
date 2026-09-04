# PaperHub 常用命令（原生本地运行）

SHELL := /bin/bash
.NOTPARALLEL:

.PHONY: help bootstrap services db backend worker frontend mcp cli demo test build stop

help:
	@echo "PaperHub 命令："
	@echo "  make bootstrap   安装原生依赖(postgres/redis/minio)并初始化"
	@echo "  make services    启动 postgres/redis/minio 本地服务"
	@echo "  make backend     启动 FastAPI 后端 (uv run)"
	@echo "  make worker      启动 Arq worker"
	@echo "  make frontend    启动 Next.js 前端 (nvm node)"
	@echo "  make mcp         启动 MCP Server (stdio)"
	@echo "  make demo        生成 demo 论文并跑通一次端到端"
	@echo "  make test        后端 pytest"
	@echo "  make build       前端构建检查"
	@echo "  make stop        停止本地服务"

bootstrap:
	bash scripts/bootstrap-native.sh

services:
	bash scripts/dev-services.sh

db:
	bash scripts/init-db.sh

backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd backend && uv run arq app.workers.main.WorkerSettings

frontend:
	cd frontend && bash -c 'source $$HOME/.nvm/nvm.sh && nvm use 20 >/dev/null 2>&1 || nvm use; npm run dev'

mcp:
	cd mcp-server && uv run python server.py

cli:
	cd cli && uv run paperhub --help

demo:
	bash scripts/run_demo.sh

test:
	cd backend && uv run pytest -q

build:
	cd frontend && bash -c 'source $$HOME/.nvm/nvm.sh && nvm use 20 >/dev/null 2>&1 || nvm use; npm run build'

stop:
	bash scripts/dev-services.sh stop
