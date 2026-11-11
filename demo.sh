#!/usr/bin/env bash
# 一键演示：装环境 → 跑测试 → 建索引 → 跑 Agent → 跑评测
# 失败即停（set -e），每步都有明确输出，便于录屏。
set -eo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ -z "$PYTHON" ]; then PYTHON=python3; fi
if [ -z "$VENV" ]; then VENV="$ROOT/.venv-demo"; fi
# 国内网络通常需要代理拉 PyPI：PIP_ARGS="--proxy http://127.0.0.1:7890" ./demo.sh
if [ -z "$PIP_ARGS" ]; then PIP_ARGS=""; fi
OUT="$ROOT/outputs"

step() { printf "\n\033[1m==> %s\033[0m\n" "$1"; }
note() { printf "    %s\n" "$1"; }

step "0/6 检查 Python 版本"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3, 11), sys.version; print("    python", sys.version.split()[0])'

step "1/6 准备虚拟环境与依赖"
if [ ! -x "$VENV/bin/python" ]; then
  note "创建 venv：$VENV"
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install -q $PIP_ARGS --upgrade pip
if ! "$VENV/bin/python" -m pip install -q $PIP_ARGS -e "$ROOT/mcp-server" -e "$ROOT/rag" -e "$ROOT/graph-agent"; then
  note "依赖安装失败。若在受限网络里，请重试："
  note '  PIP_ARGS="--proxy http://127.0.0.1:7890" ./demo.sh'
  exit 1
fi
note "已安装 ai-lab-mcp / ai-lab-rag / ai-lab-agent"

step "2/6 跑三个模块的单元测试"
for pkg in mcp-server rag graph-agent; do
  note "$pkg"
  ( cd "$ROOT/$pkg" && "$VENV/bin/python" -m unittest discover -s tests -q 2>&1 | tail -2 )
done

step "3/6 建检索索引（对仓库文档）"
"$VENV/bin/python" -m ai_lab_rag.cli index --corpus "$ROOT" --rebuild

step "4/6 跑 Agent（对手写靶场，7 条问题）"
mkdir -p "$OUT"
LAB_WORKSPACE_ROOT="$ROOT/graph-agent/examples/sample_repo" \
LAB_RAG_INDEX="$ROOT/rag-index.json" \
  "$VENV/bin/python" -m ai_lab_agent.cli app.py utils.py --out "$OUT/agent-report.md" | tail -20

step "5/6 跑检索评测（20 条）"
"$VENV/bin/python" "$ROOT/eval/run_eval.py" --write-report > "$OUT/eval-report.md"
sed -n '1,14p' "$OUT/eval-report.md"

step "6/6 完成"
note "Agent 报告：$OUT/agent-report.md"
note "评测报告：$OUT/eval-report.md（同时写入 docs/eval-report.md）"
note "全部测试与演示通过。"
