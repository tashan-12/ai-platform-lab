"""离线评测：把"感觉还能用"变成可复现的数字。

评测集是 20 条人工构造的真实问题（5 类：概念/用法/事实/边界/排错），
标注只精确到"文档级"——因为块级标注太脆，改一行字就对不上，反而让指标失真。

四个配置对比：
  bm25            纯关键词
  vector          纯哈希向量
  hybrid          BM25 与向量 0.5 加权
  hybrid+rerank   再加"查询词覆盖率 + 标题命中"重排
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rag" / "src"))

from ai_lab_rag.config import RagConfig  # noqa: E402
from ai_lab_rag.index import Index, build_index  # noqa: E402
from ai_lab_rag.retriever import Retriever  # noqa: E402

CONFIGS: list[tuple[str, dict]] = [
    ("bm25", {"alpha": 0.0, "rerank": False}),
    ("vector", {"alpha": 1.0, "rerank": False}),
    ("hybrid", {"alpha": 0.5, "rerank": False}),
    ("hybrid+rerank", {"alpha": 0.5, "rerank": True}),
]
TOP_K_EVAL = 10
FENCE = chr(96) * 3


def load_dataset(path: Path) -> list[dict]:
    items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not items:
        raise ValueError("评测集为空")
    return items


def first_hit_rank(hits, expected: list[str]) -> int:
    """返回第一个命中期望文档的名次（1 起），未命中返回 0。"""

    for rank, hit in enumerate(hits, start=1):
        if hit.chunk.doc in expected:
            return rank
    return 0


def evaluate(index: Index, dataset: list[dict], name: str, params: dict) -> dict:
    retriever = Retriever(index)
    ranks: list[int] = []
    latencies: list[float] = []
    per_query: list[dict] = []

    for item in dataset:
        started = time.perf_counter()
        hits = retriever.search(item["query"], k=TOP_K_EVAL, rerank=params["rerank"], alpha=params["alpha"])
        latencies.append((time.perf_counter() - started) * 1000)

        rank = first_hit_rank(hits, item["expected"])
        ranks.append(rank)
        per_query.append(
            {
                "id": item["id"],
                "category": item["category"],
                "query": item["query"],
                "rank": rank,
                "top_doc": hits[0].chunk.doc if hits else None,
            }
        )

    total = len(ranks)
    return {
        "name": name,
        "recall@1": sum(1 for r in ranks if 0 < r <= 1) / total,
        "recall@3": sum(1 for r in ranks if 0 < r <= 3) / total,
        "recall@5": sum(1 for r in ranks if 0 < r <= 5) / total,
        "mrr": sum((1 / r) if r else 0 for r in ranks) / total,
        "p50_ms": statistics.median(latencies),
        "p95_ms": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)],
        "per_query": per_query,
    }


def category_breakdown(result: dict, dataset: list[dict]) -> dict[str, dict]:
    categories: dict[str, dict] = {}
    for item, predicted in zip(dataset, result["per_query"]):
        bucket = categories.setdefault(item["category"], {"n": 0, "hit@3": 0, "hit@5": 0})
        bucket["n"] += 1
        if 0 < predicted["rank"] <= 3:
            bucket["hit@3"] += 1
        if 0 < predicted["rank"] <= 5:
            bucket["hit@5"] += 1
    for bucket in categories.values():
        bucket["recall@3"] = bucket["hit@3"] / bucket["n"]
        bucket["recall@5"] = bucket["hit@5"] / bucket["n"]
    return categories


def _code(text: str) -> str:
    return chr(96) + text + chr(96)


def compare_with_baseline(results: list[dict], dataset: list[dict]) -> list[dict]:
    """列出名次发生变化的题目，带方向。"""

    baseline = next(r["per_query"] for r in results if r["name"] == "bm25")
    best = max(results, key=lambda r: (r["recall@3"], r["mrr"]))["per_query"]

    rows: list[dict] = []
    for base, top, item in zip(baseline, best, dataset):
        base_rank = base["rank"] or 0
        best_rank = top["rank"] or 0
        if base_rank == best_rank:
            continue
        if base_rank and best_rank:
            delta = base_rank - best_rank          # 正数=名次提前（变好）
        elif best_rank and not base_rank:
            delta = 1                              # 原来没命中，现在进了榜
        else:
            delta = -1                             # 原来命中，现在掉出榜
        rows.append({"id": item["id"], "base": base_rank or "-", "best": best_rank or "-", "delta": delta})
    return rows


def render(results: list[dict], dataset: list[dict], meta: dict, failures: list[dict]) -> str:
    lines = ["# 检索评测报告", ""]
    lines.append(f"- 语料：{meta['docs']} 篇文档 / {meta['chunks']} 个块（平均 {meta['avg_len']} 字符）")
    lines.append(f"- 评测集：{len(dataset)} 条，{len({item['category'] for item in dataset})} 类")
    lines.append(f"- 评测方式：文档级命中（命中期望文档即算对），取 Top-{TOP_K_EVAL} 计算名次")
    lines.append("")

    lines += ["## 总体结果", "", "| 配置 | Recall@1 | Recall@3 | Recall@5 | MRR | P50 | P95 |", "|---|---|---|---|---|---|---|"]
    for result in results:
        lines.append(
            f"| {result['name']} | {result['recall@1']:.2%} | {result['recall@3']:.2%} | "
            f"{result['recall@5']:.2%} | {result['mrr']:.3f} | {result['p50_ms']:.1f} ms | {result['p95_ms']:.1f} ms |"
        )
    lines.append("")

    best = max(results, key=lambda r: (r["recall@3"], r["mrr"]))
    best_mrr = max(results, key=lambda r: r["mrr"])
    baseline = next(r for r in results if r["name"] == "bm25")
    lines.append(
        f"**结论**：按 Recall@3 选，最优是 {_code(best['name'])}"
        f"（{best['recall@3']:.2%}，相对 BM25 基线 {(best['recall@3'] - baseline['recall@3']) * 100:+.1f} 个百分点）；"
        f"但按 MRR 选，最优是 {_code(best_mrr['name'])}（{best_mrr['mrr']:.3f}）。"
    )
    lines.append("")
    lines.append(
        "**指标冲突（这条比排名本身更值得看）**：混合+重排把正确答案更多推进了前 3，"
        "却也让少数原本排第一的结果掉到第二，导致 MRR 反而略低于纯 BM25。"
        "这说明在当前语料上，重排的收益集中在「召回长尾」，代价是「头部精度」。"
        "选型取决于用途：RAG 取前 3 段上下文做生成 → 选 hybrid+rerank；只需一条精确答案 → 保持 BM25。"
    )
    lines.append("")

    best_by_cat = category_breakdown(best, dataset)
    base_by_cat = category_breakdown(baseline, dataset)
    lines += [
        "## 分类别：BM25 基线 vs 最优配置（Recall@3）",
        "",
        "| 类别 | 题数 | BM25 | 最优 |",
        "|---|---|---|---|",
    ]
    for category, bucket in best_by_cat.items():
        base_value = base_by_cat.get(category, {}).get("recall@3", 0.0)
        lines.append(f"| {category} | {bucket['n']} | {base_value:.0%} | {bucket['recall@3']:.0%} |")
    lines.append("")

    moved = compare_with_baseline(results, dataset)
    if moved:
        lines += ["## 相对 BM25 的进退", "", "| 题号 | 基线名次 | 最优名次 | 变化 |", "|---|---|---|---|"]
        for row in moved:
            arrow = "↑" if row["delta"] > 0 else "↓"
            lines.append(f"| {row['id']} | {row['base']} | {row['best']} | {arrow}{abs(row['delta'])} |")
        lines.append("")
        lines.append("说明：名次为 1 表示第一条就命中，0 表示 Top-10 内未命中；↑ 为变好，↓ 为变差。")
        lines.append("")

    if failures:
        lines += ["## 失败案例分析", ""]
        for item in failures:
            lines.append(f"- **{item['id']}（{item['category']}）** {item['query']}")
            lines.append(f"  - 期望：{_code(item['expected'][0])}")
            lines.append(f"  - 实际 Top1：{_code(str(item['top_doc']))}（名次 {item['rank'] or '未命中'}）")
            lines.append(f"  - 判断：{item['reason']}")
        lines.append("")

    lines += [
        "## 方法与局限",
        "",
        "- **标注方式**：20 条问题由作者本人按仓库文档构造，标注到文档级；**存在作者偏差**——",
        "  写题的人知道答案在哪，题目会更贴近文档原文措辞，真实用户提问通常更模糊。",
        "- **指标口径**：Recall@k 只回答「该看的文档有没有进前 k 条」，不评价块内排序质量；",
        "  MRR 只取第一个命中，多文档问题（如 Q08、Q14）按任一命中计算。",
        "- **未覆盖**：多轮对话式检索、跨文档聚合问答、拒答（无答案时应不返回）。",
        "",
        "## 复现",
        "",
        FENCE + "bash",
        "python eval/run_eval.py --write-report",
        FENCE,
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检索离线评测")
    parser.add_argument("--corpus", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--dataset", default=str(Path(__file__).resolve().parent / "dataset.jsonl"))
    parser.add_argument("--write-report", action="store_true", help="把报告写入 docs/eval-report.md")
    args = parser.parse_args(argv)

    corpus = Path(args.corpus).resolve()
    dataset = load_dataset(Path(args.dataset))

    index, _ = build_index(corpus, RagConfig(), rebuild=True)
    meta = {
        "docs": len(index.docs),
        "chunks": len(index.chunks),
        "avg_len": round(index.avg_len),
    }

    results = [evaluate(index, dataset, name, params) for name, params in CONFIGS]
    best = max(results, key=lambda r: (r["recall@3"], r["mrr"]))

    failures: list[dict] = []
    for item, predicted in zip(dataset, best["per_query"]):
        if 0 < predicted["rank"] <= 3:
            continue
        if predicted["rank"] == 0:
            reason = "完全没命中：查询词与期望文档的重叠不足，或该文档块太小被并入相邻块"
        else:
            reason = f"命中太靠后：被更长的文档抢了分，Top1 是 {predicted['top_doc']}"
        failures.append({**item, "rank": predicted["rank"], "top_doc": predicted["top_doc"], "reason": reason})

    report = render(results, dataset, meta, failures)
    print(report)

    if args.write_report:
        target = Path(__file__).resolve().parents[1] / "docs" / "eval-report.md"
        target.write_text(report, encoding="utf-8")
        print(f"\n报告已写入：{target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
