# AI Platform Lab

> 一个"分析 → 验证 → 修复"闭环的 Agent 工程实践：**MCP 工具层 + LangGraph 编排 + RAG 检索 + 沙箱执行 + 离线评测**。

[![status](https://img.shields.io/badge/status-building-yellow)]() [![python](https://img.shields.io/badge/python-3.11+-blue)]()

---

## 它能做什么

给一个代码仓库，Agent 自动完成三步：

1. **分析**：读代码/配置，产出可疑点与风险等级（规则 + LLM 双通道）；
2. **验证**：把可疑点转成可执行用例，丢进沙箱跑一遍，拿到真实结果；
3. **修复建议**：根据验证结果生成修复建议与报告。

```text
   repo / 文件
        │
        ▼
  ┌───────────┐    MCP 工具层（read_file / run_test / search_issues）
  │  Analyzer │───────────────┐
  └───────────┘               │
        │                     ▼
        │            ┌─────────────────┐
        └───────────▶│  Verifier (沙箱) │
                     └─────────────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  Reporter       │
                     └─────────────────┘
```

## 跑出来的结果

**检索侧**（20 条真实问题，5 类，语料为本仓库 12 篇文档 / 84 个块）：

| 配置 | Recall@1 | Recall@3 | Recall@5 | MRR | P50 |
|---|---|---|---|---|---|
| BM25 基线 | **80%** | 90% | 95% | **0.853** | 1.9 ms |
| 纯向量 | 70% | 80% | 95% | 0.782 | 2.0 ms |
| **混合（推荐）** | 70% | **95%** | 100% | 0.818 | 1.9 ms |
| 混合 + 重排 | 65% | 95% | 100% | 0.804 | 2.0 ms |

> **三个不好看的结论，都留着**：
> ① 混合检索 Recall@3 比 BM25 高 5pp，但 Recall@1 低 10pp——它把"该看的文档"拉进了前三，也把原本第一的答案挤到第二；
> ② **重排在这份语料上没有收益**（Recall@3 +0pp，Recall@1 -5pp），所以默认关闭，只保留为可切换项；
> ③ 评测集只有 20 条且由作者自标注，绝对数值不可外推，只能用于同一语料内的相对比较。
> 完整数据与失败分析见 [评测报告](docs/eval-report.md)。

**Agent 侧**（靶场 7 条问题）：7 条全部经脚本复核为 confirmed，0 误报；单次全流程约 1 秒（不含模型调用）。

## 关键设计

详见 `docs/adr/`：

- [ADR-001](docs/adr/0001-tools-via-mcp.md) 工具走 MCP，而不是硬编码 function call
- [ADR-002](docs/adr/0002-graph-orchestration.md) 用图编排（LangGraph），而不是线性链
- [ADR-003](docs/adr/0003-sandbox-execution.md) 执行放沙箱，而不是同集群容器
- [ADR-004](docs/adr/0004-inprocess-vs-mcp.md) 工具通道：进程内调用与 MCP 并存
- [ADR-005](docs/adr/0005-rag-design.md) 检索：结构切分 + 混合打分 + 零依赖向量

## 目录

```text
.
├── mcp-server/        # MCP 工具服务（read_file / run_test / search_issues）
├── graph-agent/       # LangGraph 编排：analyze → verify → report
├── rag/               # 文档切分、embedding、检索、重排
├── eval/              # 20 条离线评测集与脚本
├── docs/
│   ├── adr/           # 架构决策记录
│   └── eval-report.md # 评测报告
└── demo.mp4           # 3 分钟演示（录制后补）
```

## 快速开始

```bash
git clone git@github.com:tashan-12/ai-platform-lab.git
cd ai-platform-lab

# 模块一：MCP 工具层（已可用）
cd mcp-server
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m unittest discover -s tests -v          # 38 个用例，零依赖可跑
LAB_WORKSPACE_ROOT=$PWD/.. python -m ai_lab_mcp.server

# 模块二：LangGraph 闭环 Agent（已可用）
cd ../graph-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e ../mcp-server -e ".[dev]"
python -m unittest discover -s tests -v          # 16 个用例
LAB_WORKSPACE_ROOT=$PWD/examples/sample_repo \
  python -m ai_lab_agent.cli app.py utils.py    # 7 条发现，全部复核为 confirmed
```

## Roadmap

- [x] `mcp-server`：3 个工具的 MCP Server，可接入 Claude Desktop / Cursor（38 个单测全绿）
- [x] `graph-agent`：LangGraph 三节点图 + 两条条件边，每条发现自动生成复核脚本（16 个单测，靶场 7/7 证实）
- [ ] `graph-agent` 接入 LLM 分析通道（规则兜底 + 模型增强）
- [x] `rag`：结构切分 + 增量索引 + BM25/向量混合 + 重排（27 个单测）
- [x] `eval`：20 条真实评测集 + 离线跑分（混合检索 Recall@3 90% → 95%）
- [x] `docs/adr`：3 份决策记录
- [ ] `demo.mp4`：3 分钟录屏

## License

MIT（如无特殊说明）
