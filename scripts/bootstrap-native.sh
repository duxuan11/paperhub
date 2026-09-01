#!/usr/bin/env bash
# 一键安装原生依赖（无需 sudo）并启动服务。
# 二进制与数据位于 $PAPERHUB_RUNTIME（默认 ~/paperhub-runtime）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "==> PaperHub 原生环境引导（用户空间，无需 sudo）"

bash "$ROOT/scripts/setup-local-binaries.sh"
bash "$ROOT/scripts/dev-services.sh" start

echo ""
echo "完成。后续可用: make backend / make worker / make frontend"
