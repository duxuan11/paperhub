#!/usr/bin/env bash
# 一键端到端演示：自动确保基础服务 + 拉起 backend/worker，跑完 demo 后清理临时进程。
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RT="${PAPERHUB_RUNTIME:-$HOME/paperhub-runtime}"
BACKEND_LOG="$RT/demo-backend.log"
WORKER_LOG="$RT/demo-worker.log"
API="http://localhost:8000"

BACKEND_PID=""
WORKER_PID=""
BACKEND_STARTED=0
WORKER_STARTED=0
CLEANUP_DONE=0

kill_tree() {
  local pid="$1"
  local child
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

cleanup() {
  if [ "$CLEANUP_DONE" = 1 ]; then return; fi
  CLEANUP_DONE=1
  echo ""
  echo "==> 清理本脚本拉起的进程..."
  if [ "$BACKEND_STARTED" = 1 ] && [ -n "$BACKEND_PID" ]; then
    kill_tree "$BACKEND_PID"
    sleep 1
    kill -9 "$BACKEND_PID" 2>/dev/null || true
    echo "    已停止 backend (pid $BACKEND_PID)"
  fi
  if [ "$WORKER_STARTED" = 1 ] && [ -n "$WORKER_PID" ]; then
    kill_tree "$WORKER_PID"
    sleep 1
    kill -9 "$WORKER_PID" 2>/dev/null || true
    echo "    已停止 worker (pid $WORKER_PID)"
  fi
}
trap cleanup EXIT

echo "==> 同步 workspace 依赖"
cd "$ROOT" && uv sync --quiet

echo "==> 确保基础服务 (postgres/redis/minio) 已启动"
bash "$ROOT/scripts/dev-services.sh" start || true
if ! curl -sf http://localhost:9000/minio/health/live >/dev/null 2>&1; then
  echo "错误: MinIO 未就绪，请先运行 make bootstrap" >&2
  exit 1
fi

if curl -sf "$API/api/v1/health" >/dev/null 2>&1; then
  echo "==> backend 已在运行，直接复用"
else
  echo "==> 启动 backend (日志: $BACKEND_LOG)"
  (cd "$ROOT/backend" && exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 >"$BACKEND_LOG" 2>&1) &
  BACKEND_PID=$!
  BACKEND_STARTED=1
fi

if pgrep -f "\.venv/bin/(uv run )?arq app\.workers\.main\.WorkerSettings" >/dev/null 2>&1; then
  echo "==> worker 已在运行，直接复用"
else
  echo "==> 启动 worker (日志: $WORKER_LOG)"
  (cd "$ROOT/backend" && exec uv run arq app.workers.main.WorkerSettings >"$WORKER_LOG" 2>&1) &
  WORKER_PID=$!
  WORKER_STARTED=1
fi

echo "==> 等待 backend 就绪..."
READY=0
for i in $(seq 1 30); do
  if curl -sf "$API/api/v1/health" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 2
done
if [ "$READY" != 1 ]; then
  echo "错误: backend 启动超时，查看日志: $BACKEND_LOG" >&2
  exit 1
fi
echo "    backend ready"

echo ""
bash "$ROOT/scripts/run_demo.sh"
DEMO_RC=$?

exit $DEMO_RC
