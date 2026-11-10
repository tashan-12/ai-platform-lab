"""search_issues：在本地 issues.json 里做轻量关键词检索。

没上向量检索是刻意的：这一步只需要"能用"，把向量检索留给 rag/ 模块对比评测。
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import Settings


def _issues_file(settings: Settings) -> Path:
    return settings.issues_path or settings.workspace_root / "config" / "issues.json"


def load_issues(settings: Settings) -> list[dict]:
    path = _issues_file(settings)
    if not path.exists():
        raise FileNotFoundError(f"issues 文件不存在：{path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("issues 文件必须是 JSON 数组")
    return data


def _tokens(query: str) -> list[str]:
    """中文没有空格分词，这里用「按空白与标点切分 + 子串匹配」，够轻够快。"""

    normalized = query.lower().replace("，", " ").replace("、", " ")
    parts = [part for part in normalized.split() if part]
    return parts or [query.lower()]


def search_issues(settings: Settings, query: str, limit: int = 5) -> list[dict]:
    """返回与 query 相关的 issue，按相关度降序。"""

    if limit <= 0:
        return []

    tokens = _tokens(query)
    scored: list[tuple[int, dict]] = []

    for issue in load_issues(settings):
        title = str(issue.get("title", "")).lower()
        body = str(issue.get("body", "")).lower()
        tags = " ".join(issue.get("tags", [])).lower()

        score = 0
        for token in tokens:
            if token in title:
                score += 3
            if token in body:
                score += 2
            if token in tags:
                score += 1

        if score > 0:
            scored.append(
                (
                    score,
                    {
                        "id": issue.get("id"),
                        "title": issue.get("title"),
                        "status": issue.get("status"),
                        "tags": issue.get("tags", []),
                        "score": score,
                    },
                )
            )

    scored.sort(key=lambda item: (-item[0], str(item[1].get("id"))))
    return [item[1] for item in scored[:limit]]


def search_issues_json(settings: Settings, query: str, limit: int = 5) -> str:
    return json.dumps({"query": query, "results": search_issues(settings, query, limit)}, ensure_ascii=False, indent=2)
