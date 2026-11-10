"""命令行入口：python -m ai_lab_agent.cli app.py utils.py"""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_lab_mcp.config import load_settings

from .graph import build_graph


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ai-lab-agent",
        description="分析 -> 验证 -> 报告：对目标文件做规则扫描并逐条复核",
    )
    parser.add_argument("targets", nargs="+", help="要分析的文件，相对工作区根目录")
    parser.add_argument("--root", default=None, help="工作区根目录，默认取 LAB_WORKSPACE_ROOT")
    parser.add_argument("--max-attempts", type=int, default=2, help="验证失败时的最大重试次数")
    parser.add_argument("--out", default=None, help="把报告写到指定文件")
    args = parser.parse_args(argv)

    settings = load_settings(Path(args.root) if args.root else None)
    graph = build_graph(settings)

    final_state = graph.invoke(
        {
            "goal": "扫描目标文件中的安全问题并逐条复核",
            "targets": args.targets,
            "attempts": 0,
            "max_attempts": args.max_attempts,
        }
    )

    report = final_state.get("report", "")
    print(report)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"\n报告已写入：{args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
