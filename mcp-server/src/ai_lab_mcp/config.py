"""运行配置：全部来自环境变量，默认值保证本地开箱即用。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ALLOWED_COMMANDS: tuple[str, ...] = (
    "pytest",
    "python",
    "python3",
    "npm",
    "pnpm",
    "go",
    "make",
)

# 这些文件不通过 read_file 暴露给模型：密钥、证书、环境变量
DEFAULT_DENIED_NAME_PREFIXES: tuple[str, ...] = (".env",)
DEFAULT_DENIED_SUFFIXES: tuple[str, ...] = (".pem", ".key", ".p12", ".pfx", ".keystore")
DEFAULT_DENIED_DIR_PARTS: tuple[str, ...] = (".git", ".ssh", "node_modules", ".venv")


@dataclass(frozen=True)
class Settings:
    """一次运行内的不可变配置。"""

    workspace_root: Path
    allowed_commands: tuple[str, ...] = DEFAULT_ALLOWED_COMMANDS
    denied_name_prefixes: tuple[str, ...] = DEFAULT_DENIED_NAME_PREFIXES
    denied_suffixes: tuple[str, ...] = DEFAULT_DENIED_SUFFIXES
    denied_dir_parts: tuple[str, ...] = DEFAULT_DENIED_DIR_PARTS
    max_file_bytes: int = 1_000_000
    max_output_chars: int = 20_000
    command_timeout: float = 120.0
    issues_path: Path | None = None


def _split_csv(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def load_settings(workspace_root: Path | None = None) -> Settings:
    """从环境变量读取配置；未设置时回退到当前工作目录与默认白名单。"""

    root = workspace_root or Path(os.environ.get("LAB_WORKSPACE_ROOT", "."))
    allowed = _split_csv(os.environ.get("LAB_ALLOWED_COMMANDS")) or DEFAULT_ALLOWED_COMMANDS
    issues_env = os.environ.get("LAB_ISSUES_PATH")

    return Settings(
        workspace_root=root.resolve(),
        allowed_commands=allowed,
        max_file_bytes=int(os.environ.get("LAB_MAX_FILE_BYTES", "1000000")),
        max_output_chars=int(os.environ.get("LAB_MAX_OUTPUT_CHARS", "20000")),
        command_timeout=float(os.environ.get("LAB_COMMAND_TIMEOUT", "120")),
        issues_path=Path(issues_env).resolve() if issues_env else None,
    )
