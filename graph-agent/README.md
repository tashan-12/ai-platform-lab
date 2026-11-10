# graph-agent

用 LangGraph 把"分析 → 验证 → 报告"串成一个闭环 Agent。
分析阶段的每条发现，都会被**转成一个可执行脚本去复核**——不能复现的，就不进报告。

```text
        START
          │
          ▼
     ┌─────────┐   没有发现
     │ analyze │──────────────┐
     └────┬────┘              │
          │ 有发现             │
          ▼                   │
     ┌─────────┐  验证出错且未超次数
     │ verify  │◀──┐           │
     └────┬────┘   │           │
          └────────┘           │
          │ 完成                │
          ▼                   ▼
     ┌─────────┐◀─────────────┘
     │ report  │
     └────┬────┘
          ▼
         END
```

## 三个节点

| 节点 | 做什么 | 依赖 | 产出 |
|---|---|---|---|
| `analyze` | 读目标文件，跑规则集，产出发现 | `read_file` | `findings` |
| `verify` | 每条发现生成一个确认脚本，在沙箱里跑 | `run_test` | `verified`（confirmed / not_found / error） |
| `report` | 汇总成 markdown，分开列"已证实 / 未复现 / 验证失败" | — | `report` |

## 为什么要有 verify 这一步

只做静态扫描的工具满地都是，问题在于**误报**：规则写得越宽，报告越长，越没人看。

所以这里多做一步——**为每条发现生成一个"这条问题还在不在"的脚本**，用退出码判定：

```python
# 自动生成的验证脚本（节选）
text = TARGET.read_text(encoding="utf-8", errors="replace")
if re.search(PATTERN, text):
    sys.exit(0)    # 还在 -> confirmed
sys.exit(1)        # 不在了 -> not_found（误报或已修复）
```

好处是**结论可复核**：报告里每条"已证实"，背后都有一次真实执行记录（退出码 + stdout），不是模型说了一句"我认为有问题"。

## 两条条件边

1. **analyze → verify 或 report**：没命中任何规则就直接出报告，不浪费一次验证；
2. **verify → verify 或 report**：验证环节出现基础设施错误（工具失败、超时）时重试，`max_attempts` 用尽后转报告。**有界循环**，不会卡死。

## 跑一遍

```bash
cd graph-agent

# 用仓库自带的靶子（故意不安全的代码）
cd examples/sample_repo
LAB_WORKSPACE_ROOT=$PWD ../../.venv/bin/python -m ai_lab_agent.cli app.py utils.py
```

或者装上之后直接用：

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ../mcp-server -e ".[dev]"

LAB_WORKSPACE_ROOT=$PWD/examples/sample_repo ai-lab-agent app.py utils.py
```

输出示例：

```markdown
# 安全分析报告

- 目标文件：app.py, utils.py
- 尝试次数：1
- 发现问题：7 条（已证实 7 / 未复现 0 / 验证失败 0）

## 已证实的问题

| 编号 | 严重度 | 位置 | 问题 |
|---|---|---|---|
| SEC004-L9 | critical | app.py:9 | 疑似硬编码口令或密钥 |
| SEC002-L15 | high | app.py:15 | subprocess 开启 shell=True |
...
```

## 测试

```bash
python -m unittest discover -s tests -v
```

16 个用例：规则命中/行号/后缀过滤（7）、三个节点（6）、图端到端（3，未装 langgraph 时自动跳过）。

**节点测试不需要 langgraph** —— 节点是纯函数，只依赖 `(state, settings, registry)`，所以核心逻辑永远能被快速验证。

## 已知边界

- 规则是"小而准"的 6 条，追求低误报而不是全覆盖；补齐召回要靠接 LLM（见 roadmap）；
- 验证脚本只确认"代码里还有没有这个模式"，不做语义级判定——真正的语义验证要留给沙箱里跑目标项目自己的测试；
- 报告不自动写文件，由 CLI 的 `--out` 决定。

## 和 mcp-server 的关系

工具调用走 `ToolRegistry` 的**进程内**通道，不起子进程、不走 stdio。这条路比 MCP 快，但少了跨进程隔离；
取舍记录在 [ADR-001](../docs/adr/0001-tools-via-mcp.md) 与后续的 ADR-004（待补）。
