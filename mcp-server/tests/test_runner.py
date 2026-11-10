import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import _bootstrap  # noqa: F401
from ai_lab_mcp.config import Settings
from ai_lab_mcp.runner import run_test
from ai_lab_mcp.security import CommandNotAllowedError, PathEscapeError

PY = Path(sys.executable).name


class RunTestToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.settings = Settings(workspace_root=self.root, allowed_commands=(PY, "pytest"))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_runs_allowed_command(self) -> None:
        result = run_test(self.settings, f'{PY} -c "print(42)"')
        self.assertEqual(result.exit_code, 0)
        self.assertIn("42", result.stdout)
        self.assertFalse(result.timed_out)

    def test_captures_nonzero_exit(self) -> None:
        result = run_test(self.settings, f'{PY} -c "import sys; sys.exit(3)"')
        self.assertEqual(result.exit_code, 3)

    def test_rejects_non_whitelisted(self) -> None:
        with self.assertRaises(CommandNotAllowedError):
            run_test(self.settings, "rm -rf .")

    def test_times_out(self) -> None:
        settings = replace(self.settings, command_timeout=0.3)
        result = run_test(settings, f'{PY} -c "import time; time.sleep(3)"')
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_code)

    def test_rejects_cwd_escape(self) -> None:
        with self.assertRaises(PathEscapeError):
            run_test(self.settings, f"{PY} -c pass", cwd="..")


if __name__ == "__main__":
    unittest.main()
