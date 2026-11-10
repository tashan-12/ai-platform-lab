import unittest

import _bootstrap  # noqa: F401
from ai_lab_agent.rules import scan_text


class ScanTextTest(unittest.TestCase):
    def test_detects_eval(self) -> None:
        findings = scan_text("a.py", "x = eval(user_input)\n")
        self.assertEqual([f["rule"] for f in findings], ["SEC001"])

    def test_detects_shell_true(self) -> None:
        findings = scan_text("a.py", "subprocess.run(cmd, shell=True)\n")
        self.assertIn("SEC002", [f["rule"] for f in findings])

    def test_detects_hardcoded_secret(self) -> None:
        findings = scan_text("a.py", 'password = "hunter2hunter2"\n')
        self.assertEqual([f["rule"] for f in findings], ["SEC004"])

    def test_suffix_filter(self) -> None:
        # .md 文件不参与任何规则
        self.assertEqual(scan_text("README.md", 'password = "hunter2hunter2"'), [])

    def test_clean_file_has_no_findings(self) -> None:
        source = "def add(a, b):\n    return a + b\n"
        self.assertEqual(scan_text("a.py", source), [])

    def test_line_numbers_are_reported(self) -> None:
        source = "x = 1\ny = 2\nz = eval(s)\n"
        findings = scan_text("a.py", source)
        self.assertEqual(findings[0]["line"], 3)

    def test_no_duplicate_for_same_line(self) -> None:
        findings = scan_text("a.py", "eval(x)  # only once\n")
        self.assertEqual(len(findings), 1)


if __name__ == "__main__":
    unittest.main()
