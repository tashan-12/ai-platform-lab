"""run_test 工具的实现：白名单 + 超时 + 输出截断 + 最小环境变量。"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from dataclasses import asdict, dataclass

from .config import Settings
from .security import check_command, resolve_within

# 只透传运行必需的环境变量，避免把用户 shell 里的密钥带进子进程
_PASSTHROUGH_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "VIRTUAL_ENV", "TMPDIR")


@dataclass
class RunResult:
    command: list[str]
    cwd: str
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict:
        return asdict(self)


def _minimal_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key in _PASSTHROUGH_ENV}
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _truncate(text: str, limit: int) -> str:
    """超长输出保留头尾，中间用一行标记替代，避免撑爆模型上下文。"""

    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n... [已截断 {len(text) - limit} 字符] ...\n{text[-half:]}"


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_test(settings: Settings, command: str, cwd: str = ".") -> RunResult:
    """执行一条白名单命令。命令用 shlex 切分，不经过 shell。"""

    argv = shlex.split(command)
    check_command(argv, settings)

    workdir = resolve_within(settings.workspace_root, cwd)
    if not workdir.is_dir():
        raise NotADirectoryError(f"工作目录不存在：{cwd}")

    started = time.monotonic()
    timed_out = False
    exit_code: int | None
    stdout = ""
    stderr = ""

    try:
        proc = subprocess.run(
            argv,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=settings.command_timeout,
            env=_minimal_env(),
            check=False,
        )
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = _as_text(exc.stdout)
        stderr = _as_text(exc.stderr)

    duration_ms = int((time.monotonic() - started) * 1000)
    try:
        relative_cwd = str(workdir.relative_to(settings.workspace_root.resolve()))
    except ValueError:
        relative_cwd = str(workdir)

    return RunResult(
        command=argv,
        cwd=relative_cwd,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_ms=duration_ms,
        stdout=_truncate(stdout, settings.max_output_chars),
        stderr=_truncate(stderr, settings.max_output_chars),
    )


def run_test_json(settings: Settings, command: str, cwd: str = ".") -> str:
    return json.dumps(run_test(settings, command, cwd).to_dict(), ensure_ascii=False, indent=2)
