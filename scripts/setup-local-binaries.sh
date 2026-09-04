#!/usr/bin/env bash
# 在用户空间（无需 sudo）下载并解压 PostgreSQL / Redis / MinIO 二进制。
# 运行数据放在 Linux 文件系统（默认 ~/paperhub-runtime），避免 WSL drvfs 权限问题。
set -euo pipefail

RT="${PAPERHUB_RUNTIME:-$HOME/paperhub-runtime}"
DL="$RT/.downloads"
mkdir -p "$RT/bin" "$DL"

APT_OPTS=(
  -o "Dir::State=$HOME/.apttmp"
  -o "Dir::State::lists=$HOME/.apttmp/lists"
  -o "Dir::Cache=$HOME/.apttmp"
  -o "Dir::Cache::archives=$HOME/.apttmp/cache/archives"
)

echo "==> 刷新 apt 索引（用户目录）"
mkdir -p "$HOME/.apttmp/lists/partial" "$HOME/.apttmp/cache/archives/partial"
(cd "$HOME/.apttmp" && apt-get "${APT_OPTS[@]}" update -qq)

echo "==> 下载并解压 PostgreSQL 14"
cd "$DL"
apt-get "${APT_OPTS[@]}" download postgresql-14 postgresql-client-14 libpq5
for d in postgresql-14 postgresql-client-14 libpq5; do
  dpkg -x ${d}_*.deb "$RT/bin"
done

echo "==> 下载并解压 Redis"
apt-get "${APT_OPTS[@]}" download redis-server redis-tools libjemalloc2 liblua5.1-0 liblzf1 libssl3 libsystemd0 lua-bitop lua-cjson libatomic1
for d in redis-server redis-tools libjemalloc2 liblua5.1-0 liblzf1 libssl3 libsystemd0 lua-bitop lua-cjson libatomic1; do
  dpkg -x ${d}_*.deb "$RT/bin" 2>/dev/null || true
done

echo "==> 下载 MinIO"
if [ ! -x "$RT/minio-bin" ]; then
  curl -sSLo "$RT/minio-bin" https://dl.min.io/server/minio/release/linux-amd64/minio
  chmod +x "$RT/minio-bin"
fi

echo "==> 完成。运行时目录: $RT"
