import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401 - 把 src 加入 sys.path
from ai_lab_mcp.config import Settings
from ai_lab_mcp.security import (
    CommandNotAllowedError,
    PathDeniedError,
    PathEscapeError,
    check_command,
    is_denied,
    resolve_within,
)


class ResolveWithinTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        (self.root / "sub").mkdir()
        (self.root / "sub" / "a.txt").write_text("hi", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_inside_relative_path(self) -> None:
        target = resolve_within(self.root, "sub/a.txt")
        self.assertEqual(target.name, "a.txt")
        self.assertTrue(target.exists())

    def test_rejects_parent_escape(self) -> None:
        with self.assertRaises(PathEscapeError):
            resolve_within(self.root, "../outside.txt")

    def test_rejects_absolute_outside(self) -> None:
        with self.assertRaises(PathEscapeError):
            resolve_within(self.root, "/etc/passwd")

    def test_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as other:
            secret = Path(other) / "secret.txt"
            secret.write_text("x", encoding="utf-8")
            link = self.root / "link.txt"
            link.symlink_to(secret)

            with self.assertRaises(PathEscapeError):
                resolve_within(self.root, "link.txt")

    def test_allows_root_itself(self) -> None:
        self.assertEqual(resolve_within(self.root, "."), self.root)


class DeniedRuleTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.settings = Settings(workspace_root=self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_denies_env_file(self) -> None:
        self.assertTrue(is_denied(self.root / ".env", self.settings))

    def test_denies_pem(self) -> None:
        self.assertTrue(is_denied(self.root / "server.pem", self.settings))

    def test_denies_git_internal(self) -> None:
        self.assertTrue(is_denied(self.root / ".git" / "config", self.settings))

    def test_allows_normal_file(self) -> None:
        self.assertFalse(is_denied(self.root / "README.md", self.settings))


class CommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(workspace_root=Path.cwd(), allowed_commands=("python3", "pytest"))

    def test_allows_whitelisted(self) -> None:
        check_command(["pytest", "-q"], self.settings)

    def test_rejects_unknown(self) -> None:
        with self.assertRaises(CommandNotAllowedError):
            check_command(["rm", "-rf", "."], self.settings)

    def test_rejects_empty(self) -> None:
        with self.assertRaises(CommandNotAllowedError):
            check_command([], self.settings)


if __name__ == "__main__":
    unittest.main()
