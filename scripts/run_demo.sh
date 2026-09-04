#!/usr/bin/env bash
# 端到端演示：上传 → 解析 → Figure → 阅读 → Chat → 生成公众号 → 草稿箱
# 前置：make services + make backend + make worker 已启动
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="uv run --directory $ROOT/cli paperhub"
DEMO_PDF="$ROOT/demo/paper.pdf"
API="http://localhost:8000"

echo "==> 生成 demo 论文"
cd "$ROOT/backend" && uv run python "$ROOT/scripts/gen_demo_papers.py"

echo ""
echo "==> Demo 1: 上传论文"
PID=$(curl -s -X POST "$API/api/v1/papers/upload" -F "file=@$DEMO_PDF" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "    paper_id = $PID"

echo "==> 等待解析与 Figure 检测完成..."
for i in $(seq 1 30); do
  ST=$(curl -s "$API/api/v1/papers/$PID" | python3 -c "import sys,json;print(json.load(sys.stdin)['status'])")
  echo "    状态: $ST"
  case "$ST" in
    READY|ANALYZED|CONTENT_GENERATED|PUBLISHED) break;;
    FAILED) echo "解析失败，查看 jobs"; exit 1;;
  esac
  sleep 2
done

echo ""
echo "==> Demo 1 结果: Markdown + Figure"
curl -s "$API/api/v1/papers/$PID/markdown" | python3 -c "import sys,json;m=json.load(sys.stdin)['markdown'];print('    Markdown 长度:', len(m));print('    含 Figure 图片:', 'images/' in m)"
curl -s "$API/api/v1/papers/$PID/figures" | python3 -c "import sys,json;f=json.load(sys.stdin);print('    Figure 数量:', len(f))"

echo ""
echo "==> Demo 3: Chat「总结这篇论文」"
$CLI ask "$PID" "总结这篇论文" | head -c 500
echo ""

echo ""
echo "==> Demo 4: Chat「分析 Figure 1」"
$CLI ask "$PID" "分析 Figure 1" | head -c 400
echo ""

echo ""
echo "==> Demo 5: 生成微信公众号文章"
$CLI generate-wechat "$PID" --style "科研论文解读"

echo ""
echo "==> Demo 6: 发送到微信公众号草稿箱"
$CLI publish-wechat "$PID"

echo ""
echo "==> Demo 7: CLI 全流程回顾"
$CLI status "$PID"

echo ""
echo "==> 演示完成。打开 http://localhost:3000 查看 Web UI"
