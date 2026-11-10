"""安全策略：路径不得越出工作区，命令必须在白名单内。"""

from __future__ import annotations

from pathlib import Path

from .config import Settings


class PathEscapeError(ValueError):
    """请求的路径越出了工作区根目录。"""


class PathDeniedError(PermissionError):
    """路径命中禁用规则（密钥、证书、.git 等）。"""


class CommandNotAllowedError(PermissionError):
    """命令不在白名单内。"""


def resolve_within(root: Path, candidate: str) -> Path:
    """把 candidate 解析成绝对路径，并确认它位于 root 之内。

    先 resolve 再比较，可以同时挡住 ".." 越级和符号链接逃逸两种情况。
    """

    root = root.resolve()
    raw = Path(candidate)
    target = (raw if raw.is_absolute() else root / raw).resolve()

    if target != root and root not in target.parents:
        raise PathEscapeError(
            f"路径越界：{candidate!r} 解析为 {target}，不在工作区 {root} 内"
        )
    return target


def is_denied(target: Path, settings: Settings) -> bool:
    """按文件名前缀、后缀、目录片段判断是否禁止访问。"""

    name = target.name
    if any(name.startswith(prefix) for prefix in settings.denied_name_prefixes):
        return True
    if any(name.endswith(suffix) for suffix in settings.denied_suffixes):
        return True
    return any(part in settings.denied_dir_parts for part in target.parts)


def ensure_allowed_file(target: Path, settings: Settings) -> None:
    if is_denied(target, settings):
        raise PathDeniedError(f"禁止访问：{target.name}")


def check_command(argv: list[str], settings: Settings) -> None:
    """只允许白名单里的可执行文件，防止模型调用 rm / curl 之类。"""

    if not argv:
        raise CommandNotAllowedError("空命令")

    exe = Path(argv[0]).name
    if exe not in settings.allowed_commands:
        raise CommandNotAllowedError(
            f"命令 {exe!r} 不在白名单内，允许：{', '.join(settings.allowed_commands)}"
        )
