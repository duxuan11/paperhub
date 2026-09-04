#!/usr/bin/env bash
# 初始化 PostgreSQL 数据库与用户（paperhub/paperhub）。
set -euo pipefail

DB_USER="paperhub"
DB_PASS="paperhub"
DB_NAME="paperhub"

echo "==> 确保数据库用户与库存在"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
  sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"

echo "==> 数据库就绪: ${DB_NAME} (user=${DB_USER})"
