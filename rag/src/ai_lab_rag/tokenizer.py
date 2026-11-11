"""分词：拉丁词 + 中文二元组（bigram）。

为什么不用 jieba：多一个依赖、多一份词典，而检索质量提升对"工程文档"这种
术语密集、句式短的语料并不明显。中文用 bigram 是 Lucene CJKAnalyzer 的做法，
对"增量索引""条件边"这类词已经够用。
"""

from __future__ import annotations

import re

_LATIN = re.compile(r"[a-zA-Z][a-zA-Z0-9_+\-.#]*")
_CJK = re.compile(r"[\u4e00-\u9fff]+")

# 停用词只保留极少数高频虚词，删多了会伤召回
_STOPWORDS = frozenset(
    {"的", "了", "是", "在", "和", "与", "或", "就", "都", "而", "及", "把", "被", "the", "a", "an", "of", "to", "is", "and", "or", "in"}
)


def _cjk_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for run in _CJK.findall(text):
        if len(run) == 1:
            tokens.append(run)
            continue
        tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def tokenize(text: str) -> list[str]:
    """返回小写的词元列表（保留重复，由调用方决定是否计数）。"""

    lowered = text.lower()
    tokens = [match.group(0) for match in _LATIN.finditer(lowered)]
    tokens.extend(_cjk_tokens(lowered))
    return [token for token in tokens if token not in _STOPWORDS]


def unique_tokens(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for token in tokenize(text):
        seen.setdefault(token, None)
    return list(seen)
