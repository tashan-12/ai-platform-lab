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

> 🚧 建设中。评测数据在 `docs/eval-report.md`，完成后回填下表。

| 指标 | baseline（不用 RAG / 不验证） | 本方案 | 说明 |
|---|---|---|---|
| 定位准确率 | TODO | TODO | 20 条评测集 |
| 平均耗时 | TODO | TODO | 单次任务 |
| 人工复核率 | TODO | TODO | 需要人工介入的比例 |

## 关键设计

详见 `docs/adr/`：

- [ADR-001](docs/adr/0001-tools-via-mcp.md) 工具走 MCP，而不是硬编码 function call
- [ADR-002](docs/adr/0002-graph-orchestration.md) 用图编排（LangGraph），而不是线性链
- [ADR-003](docs/adr/0003-sandbox-execution.md) 执行放沙箱，而不是同集群容器

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

> 🚧 随各模块落地补充。当前只有目录骨架。

```bash
git clone git@github.com:<你的账号>/ai-platform-lab.git
cd ai-platform-lab
```

## Roadmap

- [ ] `mcp-server`：3 个工具的 MCP Server，可接入 Claude Desktop / Cursor
- [ ] `graph-agent`：LangGraph 三节点图，含条件边与回退
- [ ] `rag`：切分 + embedding + 向量检索 + rerank
- [ ] `eval`：20 条评测集 + 离线跑分脚本
- [ ] `docs/adr`：3 份决策记录
- [ ] `demo.mp4`：3 分钟录屏

## License

MIT（如无特殊说明）
