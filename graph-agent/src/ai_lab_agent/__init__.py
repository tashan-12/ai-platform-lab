"""LangGraph 编排的闭环 Agent：分析 -> 验证 -> 报告。

节点是纯函数（只依赖传入的 state 与工具注册表），
图组装单独放在 graph.py，所以节点逻辑不需要装 langgraph 就能测。
"""

__version__ = "0.1.0"
