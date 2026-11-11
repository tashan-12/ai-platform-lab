"""三个节点：analyze / verify / report。

节点只返回 state 的增量字段，依赖通过闭包注入（settings + registry），
所以换工具实现、换模型都不用改节点代码，测试也不用起 LangGraph。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ai_lab_mcp.config import Settings
from ai_lab_mcp.registry import ToolRegistry

from .rules import RULES, scan_text

TMP_DIR = ".agent/tmp"
_RULES_BY_ID = {rule.id: rule for rule in RULES}

# 验证脚本的模板：复现"这条发现还在不在"，用退出码表达结论。
# 0 = 还在（confirmed），1 = 不在了（not_found，可能是误报或已修复）。
VERIFY_TEMPLATE = '''import re
import sys
from pathlib import Path

TARGET = Path({target!r})
PATTERN = {pattern!r}

text = TARGET.read_text(encoding="utf-8", errors="replace")
if re.search(PATTERN, text):
    print("HIT")
    sys.exit(0)

print("MISS")
sys.exit(1)
'''


def _tmp_dir(settings: Settings) -> Path:
    path = settings.workspace_root / TMP_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def analyze_node(state: dict, settings: Settings, registry: ToolRegistry) -> dict:
    """读目标文件，跑规则，产出发现列表。"""

    targets = list(state.get("targets") or [])
    errors = list(state.get("errors") or [])
    findings: list[dict] = []

    for rel_path in targets:
        result = registry.call("read_file", path=rel_path)
        if not result.get("ok"):
            errors.append(f"读取 {rel_path} 失败：{result.get('message')}")
            continue
        findings.extend(scan_text(rel_path, result["content"]))

    return {"findings": findings, "errors": errors, "status": "analyzed"}


def verify_node(state: dict, settings: Settings, registry: ToolRegistry) -> dict:
    """为每条发现生成一个验证脚本，在沙箱里跑，用退出码判定真伪。"""

    findings = list(state.get("findings") or [])
    errors = list(state.get("errors") or [])
    attempts = int(state.get("attempts") or 0) + 1
    tmp = _tmp_dir(settings)
    verified: list[dict] = []

    for finding in findings:
        rule = _RULES_BY_ID.get(finding["rule"])
        if rule is None:
            verified.append({"id": finding["id"], "status": "error", "detail": "未知规则"})
            continue

        script_name = f"verify_{finding['id'].replace('-', '_')}.py"
        script_path = tmp / script_name
        target_abs = settings.workspace_root / finding["file"]
        script_path.write_text(
            VERIFY_TEMPLATE.format(target=str(target_abs), pattern=rule.pattern),
            encoding="utf-8",
        )

        relative_script = script_path.relative_to(settings.workspace_root)
        command = f'"{sys.executable}" "{relative_script}"'
        result = registry.call("run_test", command=command)

        if not result.get("ok"):
            detail = str(result.get("message", ""))
            errors.append(f"验证 {finding['id']} 失败：{detail}")
            verified.append(
                {"id": finding["id"], "status": "error", "exit_code": None, "detail": detail}
            )
            continue

        exit_code = result.get("exit_code")
        status = "confirmed" if exit_code == 0 else "not_found"
        verified.append(
            {
                "id": finding["id"],
                "status": status,
                "exit_code": exit_code,
                "detail": result.get("stdout", "").strip(),
            }
        )

    return {"verified": verified, "errors": errors, "attempts": attempts, "status": "verified"}


def retrieve_node(state: dict, settings: Settings, registry: ToolRegistry) -> dict:
    """按发现标题检索文档依据。

    检索模块是可选依赖：没装 ai-lab-rag 或没有索引文件时安静跳过，
    不让"没装依赖"变成整条流程的失败。
    """

    errors = list(state.get("errors") or [])

    try:
        from ai_lab_rag.index import Index
        from ai_lab_rag.retriever import Retriever
    except ImportError:
        errors.append("检索模块未安装（ai-lab-rag），跳过文档依据")
        return {"references": [], "errors": errors, "status": "retrieved"}

    index_path = Path(os.environ.get("LAB_RAG_INDEX") or (settings.workspace_root / "rag-index.json"))
    if not index_path.exists():
        return {"references": [], "errors": errors, "status": "retrieved"}

    parts = [str(state.get("goal") or "")]
    for finding in (state.get("findings") or [])[:3]:
        parts.append(str(finding.get("title") or ""))
    query = " ".join(part for part in parts if part).strip()
    if not query:
        return {"references": [], "errors": errors, "status": "retrieved"}

    try:
        hits = Retriever(Index.load(index_path)).search(query, k=3)
    except Exception as exc:  # noqa: BLE001 - 索引损坏不应中断主流程
        errors.append(f"检索失败：{type(exc).__name__}: {exc}")
        return {"references": [], "errors": errors, "status": "retrieved"}

    references = [
        {
            "doc": hit.chunk.doc,
            "heading": " / ".join(part for part in hit.chunk.heading_path if part),
            "score": round(hit.score, 3),
        }
        for hit in hits
    ]
    return {"references": references, "errors": errors, "status": "retrieved"}


def report_node(state: dict, settings: Settings, registry: ToolRegistry) -> dict:
    """把发现与验证结果合成为 markdown 报告。"""

    findings = list(state.get("findings") or [])
    verified = {item["id"]: item for item in (state.get("verified") or [])}

    confirmed = [f for f in findings if verified.get(f["id"], {}).get("status") == "confirmed"]
    not_found = [f for f in findings if verified.get(f["id"], {}).get("status") == "not_found"]
    errored = [f for f in findings if verified.get(f["id"], {}).get("status") == "error"]
    unverified = [f for f in findings if f["id"] not in verified]

    lines: list[str] = [
        "# 安全分析报告",
        "",
        f"- 目标文件：{', '.join(state.get('targets') or [])}",
        f"- 尝试次数：{state.get('attempts', 0)}",
        f"- 发现问题：{len(findings)} 条（已证实 {len(confirmed)} / 未复现 {len(not_found)} / 验证失败 {len(errored)}）",
        "",
    ]

    if confirmed:
        lines += ["## 已证实的问题", "", "| 编号 | 严重度 | 位置 | 问题 |", "|---|---|---|---|"]
        for item in confirmed:
            lines.append(
                f"| {item['id']} | {item['severity']} | {item['file']}:{item['line']} | {item['title']} |"
            )
        lines.append("")

    if not_found:
        lines += ["## 未复现（误报或已修复）", ""]
        for item in not_found:
            lines.append(f"- {item['id']} · {item['file']}:{item['line']} · {item['title']}")
        lines.append("")

    if errored:
        lines += ["## 验证失败（需要人工介入）", ""]
        for item in errored:
            lines.append(f"- {item['id']} · {verified[item['id']].get('detail', '')}")
        lines.append("")

    if unverified:
        lines += ["## 未进入验证", ""]
        for item in unverified:
            lines.append(f"- {item['id']} · {item['file']}:{item['line']}")
        lines.append("")

    if not findings:
        lines += ["没有命中任何规则。", ""]

    references = list(state.get("references") or [])
    if references:
        lines += ["## 相关文档依据", ""]
        for reference in references:
            heading = reference.get("heading") or "(无标题)"
            lines.append(f"- {reference.get('doc')} · {heading}（相关度 {reference.get('score')}）")
        lines.append("")

    lines += [
        "---",
        "",
        "> 说明：本报告由规则扫描生成，结论已通过可执行脚本复核；",
        "> 未复现的条目建议人工确认后再决定是否修复。",
    ]

    return {"report": "\n".join(lines), "status": "done"}


def route_after_analyze(state: dict) -> str:
    """没有发现就不用验证了，直接出报告。"""

    return "verify" if state.get("findings") else "report"


def route_after_verify(state: dict) -> str:
    """验证环节出基础设施错误时重试；重试次数用完就出报告。"""

    has_error = any(item.get("status") == "error" for item in (state.get("verified") or []))
    attempts = int(state.get("attempts") or 0)
    max_attempts = int(state.get("max_attempts") or 2)
    if has_error and attempts < max_attempts:
        return "verify"
    return "retrieve"


def build_nodes(settings: Settings, registry: ToolRegistry) -> dict:
    """把依赖闭包进节点，交给 graph.py 组装。"""

    return {
        "analyze": lambda state: analyze_node(state, settings, registry),
        "verify": lambda state: verify_node(state, settings, registry),
        "retrieve": lambda state: retrieve_node(state, settings, registry),
        "report": lambda state: report_node(state, settings, registry),
    }
