"""静态扫描规则。

刻意保持"小而准"：只覆盖几类高频、容易被证伪的问题，
因为下一步的验证环节要能为每条发现生成一个可执行的确认脚本。
规则越多不代表越好——漏报可以靠后面接 LLM，误报会直接毁掉可信度。
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    severity: str
    pattern: str
    suffixes: tuple[str, ...]

    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.pattern)


RULES: tuple[Rule, ...] = (
    Rule(
        id="SEC001",
        title="使用 eval 执行动态代码",
        severity="high",
        pattern=r"(?<![\w.])eval\s*\(",
        suffixes=(".py",),
    ),
    Rule(
        id="SEC002",
        title="subprocess 开启 shell=True",
        severity="high",
        pattern=r"shell\s*=\s*True",
        suffixes=(".py",),
    ),
    Rule(
        id="SEC003",
        title="使用 os.system 执行命令",
        severity="high",
        pattern=r"os\.system\s*\(",
        suffixes=(".py",),
    ),
    Rule(
        id="SEC004",
        title="疑似硬编码口令或密钥",
        severity="critical",
        pattern=r"(?i)(password|passwd|secret|api_key|apikey|token)\s*=\s*[\"'][^\"']{6,}[\"']",
        suffixes=(".py", ".yaml", ".yml", ".json", ".ini", ".cfg"),
    ),
    Rule(
        id="SEC005",
        title="关闭 TLS 校验（verify=False）",
        severity="medium",
        pattern=r"verify\s*=\s*False",
        suffixes=(".py",),
    ),
    Rule(
        id="SEC006",
        title="反序列化不可信数据（pickle）",
        severity="high",
        pattern=r"pickle\.loads?\s*\(",
        suffixes=(".py",),
    ),
)


def scan_text(rel_path: str, content: str) -> list[dict]:
    """按后缀过滤规则，逐行匹配，返回发现列表。"""

    findings: list[dict] = []
    compiled = {rule.id: rule.compiled() for rule in RULES}

    for line_no, line in enumerate(content.splitlines(), start=1):
        for rule in RULES:
            if not rel_path.endswith(rule.suffixes):
                continue
            if compiled[rule.id].search(line):
                findings.append(
                    {
                        "id": f"{rule.id}-L{line_no}",
                        "rule": rule.id,
                        "title": rule.title,
                        "severity": rule.severity,
                        "file": rel_path,
                        "line": line_no,
                        "snippet": line.strip()[:160],
                    }
                )
    return findings
