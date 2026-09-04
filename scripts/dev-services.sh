#!/usr/bin/env bash
# 启动 / 停止本地开发依赖服务（PostgreSQL / Redis / MinIO），无需 sudo。
# 二进制位于 $PAPERHUB_RUNTIME（默认 ~/paperhub-runtime）。
# 用法: bash scripts/dev-services.sh [start|stop|status]
set -uo pipefail

RT="${PAPERHUB_RUNTIME:-$HOME/paperhub-runtime}"
PGBIN="$RT/bin/usr/lib/postgresql/14/bin"
RDBIN="$RT/bin/usr/bin"
LIBDIRS="$RT/bin/usr/lib/x86_64-linux-gnu:$RT/bin/lib/x86_64-linux-gnu"
export LD_LIBRARY_PATH="$LIBDIRS:${LD_LIBRARY_PATH:-}"

PGDATA="$RT/postgres"
PGPORT="${PAPERHUB_PG_PORT:-5432}"
ACTION="${1:-start}"

start_postgres() {
  if [ ! -d "$PGDATA/PG_VERSION" ]; then
    echo "[postgres] 初始化数据目录..."
    "$PGBIN/initdb" -D "$PGDATA" -U paperhub --auth=trust -E UTF8 >/dev/null 2>&1
  fi
  if "$PGBIN/pg_isready" -h localhost -p "$PGPORT" -q 2>/dev/null; then
    echo "[postgres] already running"
  else
    echo "[postgres] starting..."
    "$PGBIN/pg_ctl" -D "$PGDATA" -l "$RT/postgres.log" \
      -o "-p $PGPORT -k $RT" start >/dev/null 2>&1
    "$PGBIN/psql" -h localhost -p "$PGPORT" -U paperhub -d postgres -c \
      "ALTER USER paperhub WITH PASSWORD 'paperhub';" >/dev/null 2>&1 || true
    "$PGBIN/psql" -h localhost -p "$PGPORT" -U paperhub -d postgres -tc \
      "SELECT 1 FROM pg_database WHERE datname='paperhub'" | grep -q 1 || \
      "$PGBIN/createdb" -h localhost -p "$PGPORT" -U paperhub -O paperhub paperhub
  fi
}

start_redis() {
  if "$RDBIN/redis-cli" -p 6379 ping >/dev/null 2>&1; then
    echo "[redis] already running"
  else
    echo "[redis] starting..."
    mkdir -p "$RT/redis"
    "$RDBIN/redis-server" --daemonize yes --port 6379 --dir "$RT/redis" >/dev/null 2>&1
  fi
}

start_minio() {
  if curl -sf http://localhost:9000/minio/health/live >/dev/null 2>&1; then
    echo "[minio] already running"
  else
    if [ ! -x "$RT/minio-bin" ]; then
      echo "[minio] 二进制缺失，先运行 scripts/setup-local-binaries.sh"
      return 1
    fi
    echo "[minio] starting..."
    mkdir -p "$RT/minio"
    MINIO_ROOT_USER=paperhub MINIO_ROOT_PASSWORD=paperhub-secret \
      nohup "$RT/minio-bin" server "$RT/minio" --address ":9000" --console-address ":9001" \
      > "$RT/minio.log" 2>&1 &
    sleep 2
  fi
}

stop_all() {
  echo "[redis] stopping..."; "$RDBIN/redis-cli" shutdown nosave 2>/dev/null || true
  echo "[minio] stopping..."; pkill -f "minio-bin server" 2>/dev/null || true
  echo "[postgres] stopping..."; "$PGBIN/pg_ctl" -D "$PGDATA" stop -m fast >/dev/null 2>&1 || true
}

case "$ACTION" in
  start)
    start_postgres
    start_redis
    start_minio
    echo "--- services ---"
    "$PGBIN/pg_isready" -h localhost -p "$PGPORT" && echo "postgres: ok" || echo "postgres: NOT READY"
    "$RDBIN/redis-cli" -p 6379 ping && echo "redis: ok" || echo "redis: NOT READY"
    curl -sf http://localhost:9000/minio/health/live >/dev/null && echo "minio: ok" || echo "minio: NOT READY"
    ;;
  stop)
    stop_all
    ;;
  status)
    "$PGBIN/pg_isready" -h localhost -p "$PGPORT" && echo "postgres: ok" || echo "postgres: down"
    "$RDBIN/redis-cli" -p 6379 ping && echo "redis: ok" || echo "redis: down"
    curl -sf http://localhost:9000/minio/health/live >/dev/null && echo "minio: ok" || echo "minio: down"
    ;;
  *)
    echo "usage: $0 [start|stop|status]"; exit 1;;
esac
