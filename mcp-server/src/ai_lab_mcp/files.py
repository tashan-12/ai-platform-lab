"""read_file 工具的实现：只读、限大小、禁密钥、禁越界。"""

from __future__ import annotations

import json

from .config import Settings
from .security import ensure_allowed_file, resolve_within


def read_text_file(
    settings: Settings,
    path: str,
    *,
    max_bytes: int | None = None,
) -> dict:
    """读取工作区内的文本文件，返回可直接 JSON 序列化的结果。"""

    limit = max_bytes if max_bytes is not None else settings.max_file_bytes
    target = resolve_within(settings.workspace_root, path)
    ensure_allowed_file(target, settings)

    if not target.exists():
        raise FileNotFoundError(f"文件不存在：{path}")
    if target.is_dir():
        raise IsADirectoryError(f"{path} 是目录，不是文件")

    size = target.stat().st_size
    truncated = size > limit
    with target.open("rb") as fh:
        raw = fh.read(limit)

    text = raw.decode("utf-8", errors="replace")
    if truncated and text.endswith("\ufffd"):
        text = text[:-1]  # 按字节截断可能切在多字节字符中间，丢掉这个替换符

    return {
        "path": str(target.relative_to(settings.workspace_root.resolve())),
        "size": size,
        "truncated": truncated,
        "content": text,
    }


def read_text_file_json(settings: Settings, path: str, *, max_bytes: int | None = None) -> str:
    return json.dumps(
        read_text_file(settings, path, max_bytes=max_bytes),
        ensure_ascii=False,
        indent=2,
    )
