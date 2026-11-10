"""Agent 的状态定义。

用 total=False 的 TypedDict：节点只返回自己改动的那几个字段，
LangGraph 会按字段合并，不用每次把整个 state 回传。
"""

from __future__ import annotations

from typing import TypedDict


class Finding(TypedDict, total=False):
    """一条静态发现。"""

    id: str            # 规则号 + 行号，例如 SEC001-L12
    rule: str          # 规则号
    title: str         # 一句话描述
    severity: str      # critical / high / medium / low
    file: str          # 相对工作区的文件路径
    line: int          # 行号
    snippet: str       # 命中的那行代码


class Verification(TypedDict, total=False):
    """一条发现的验证结果。"""

    id: str
    status: str        # confirmed / not_found / error
    exit_code: int | None
    detail: str        # 给人看的说明


class AgentState(TypedDict, total=False):
    goal: str
    targets: list[str]
    findings: list[Finding]
    verified: list[Verification]
    attempts: int
    max_attempts: int
    report: str
    status: str        # running / done
    errors: list[str]
