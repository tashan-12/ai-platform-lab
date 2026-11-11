"""命令行：建索引 / 查询 / 看统计。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import RagConfig, default_index_path
from .index import Index, build_index
from .retriever import Retriever


def _resolve_index(explicit: str | None, corpus: Path) -> Path:
    return Path(explicit).resolve() if explicit else default_index_path(corpus.resolve())


def _cmd_index(args: argparse.Namespace) -> int:
    corpus = Path(args.corpus).resolve()
    cfg = RagConfig()
    out = _resolve_index(args.out, corpus)

    previous = None
    if out.exists() and not args.rebuild:
        try:
            previous = Index.load(out)
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"旧索引不可用（{exc}），改为全量重建")
            previous = None

    index, stats = build_index(corpus, cfg=cfg, previous=previous, rebuild=args.rebuild)
    size = index.save(out)

    mode = "全量" if previous is None else "增量"
    print(f"[{mode}] 语料：{corpus}")
    print(
        f"文档 {stats.docs_total}（重建 {stats.docs_rebuilt} / 复用 {stats.docs_reused} / 移除 {stats.docs_removed}）"
    )
    print(f"块数：{stats.chunks}，平均块长 {index.avg_len:.0f} 字符，词表 {len(index.postings)}")
    print(f"索引文件：{out}（{size / 1024:.1f} KB）")

    for warning in stats.warnings[:10]:
        print(f"! {warning}")
    if len(stats.warnings) > 10:
        print(f"! 另有 {len(stats.warnings) - 10} 条警告未显示")

    return 0


def _cmd_query(args: argparse.Namespace) -> int:
    corpus = Path(args.corpus).resolve()
    index_path = _resolve_index(args.index, corpus)
    if not index_path.exists():
        print(f"索引不存在：{index_path}，请先运行 index 子命令")
        return 2

    index = Index.load(index_path)
    hits = Retriever(index).search(args.text, k=args.k, rerank=not args.no_rerank)

    if args.json:
        print(json.dumps([hit.to_dict() for hit in hits], ensure_ascii=False, indent=2))
        return 0

    if not hits:
        print("没有命中。")
        return 0

    for rank, hit in enumerate(hits, start=1):
        heading = " / ".join(part for part in hit.chunk.heading_path if part)
        print(f"{rank}. [{hit.score:.3f}] {hit.chunk.doc} :: {heading or '(无标题)'}")
        snippet = hit.chunk.text.strip().replace("\n", " ")[:120]
        print(f"   {snippet}")
        print(f"   bm25={hit.bm25:.2f} cos={hit.cosine:.2f} cov={hit.coverage:.2f}")
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    corpus = Path(args.corpus).resolve()
    index_path = _resolve_index(args.index, corpus)
    if not index_path.exists():
        print(f"索引不存在：{index_path}")
        return 2

    index = Index.load(index_path)
    print(json.dumps(index.summary(), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-lab-rag", description="工程文档检索：建索引 / 查询")
    sub = parser.add_subparsers(dest="command", required=True)

    p_index = sub.add_parser("index", help="构建或增量更新索引")
    p_index.add_argument("--corpus", default=".", help="语料根目录")
    p_index.add_argument("--out", default=None, help="索引输出路径")
    p_index.add_argument("--rebuild", action="store_true", help="忽略旧索引，全量重建")
    p_index.set_defaults(func=_cmd_index)

    p_query = sub.add_parser("query", help="检索")
    p_query.add_argument("text", help="查询语句")
    p_query.add_argument("--corpus", default=".", help="语料根目录（用于定位默认索引）")
    p_query.add_argument("--index", default=None, help="索引路径")
    p_query.add_argument("-k", type=int, default=5, help="返回条数")
    p_query.add_argument("--no-rerank", action="store_true", help="关闭重排")
    p_query.add_argument("--json", action="store_true", help="输出 JSON")
    p_query.set_defaults(func=_cmd_query)

    p_stats = sub.add_parser("stats", help="索引统计")
    p_stats.add_argument("--corpus", default=".")
    p_stats.add_argument("--index", default=None)
    p_stats.set_defaults(func=_cmd_stats)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
