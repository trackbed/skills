from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECKER = Path(__file__).resolve().parents[1] / "test_helper/check_bats_assertions.py"
SPEC = importlib.util.spec_from_file_location("check_bats_assertions", CHECKER)
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class BatsAssertionCheckTests(unittest.TestCase):
    def test_rejects_negation_and_conditional_even_before_success(self):
        for assertion in (
            "! true",
            "!\ttrue",
            "[[\ta == b ]]",
            "! true || { echo ignored; }",
            "[[ a == b ]] || { true; }",
            "! true || false && true",
            "! true || return 0",
            "! true || return 256",
            "! true || { return 0; return 1; }",
            "! true || { exit 0; exit 1; }",
            "! true || { exec true; return 1; }",
            "[[ a == b ]]",
            "[[ a == b && c == d ]]",
            "! true || false || true",
            "[[ a == b ]] || [[ c == d ]]",
        ):
            with self.subTest(assertion=assertion):
                self.assertEqual(checker.unsafe_assertions(assertion + "\necho later\n"), [(1, 1)])

    def test_rejects_successful_or_arms_before_a_failure_guard(self):
        for assertion in (
            "! true || echo failure || false",
            "! true || true || false",
            "[[ a == b ]] || echo failure || false",
            "[[ a == b ]] || true || false",
            "[[ a == b ]] || CONDITION || false",
            "[[ a == b ]] || echo '[[ a == a ]] || false' || false",
            "! true || echo '|| false' || false",
            "! true; echo ignored || false",
            "[[ a == b ]]; echo ignored || false",
        ):
            with self.subTest(assertion=assertion):
                self.assertEqual(checker.unsafe_assertions(assertion + "\necho later\n"), [(1, 1)])
        self.assertEqual(checker.unsafe_assertions("[[ a == b ]] || [[ c == c ]] || false"), [])
        self.assertEqual(checker.unsafe_assertions("! true || [[ a == a ]] || false"), [])

    def test_accepts_explicit_failure_and_control_flow(self):
        for assertion in (
            "! grep x file || false",
            "!\tgrep x file || false",
            "[[\ta == a ]] || false",
            "[[ a == b ]] || return 1",
            "[[ a == b ]] || exit 1",
            "[[ a == b ]] || [[ c == d ]] || false",
            "[[ a == b ]] || { echo failure; return 1; }",
            "if ! grep x file; then",
            "if [[ a == b ]]; then",
            '[[ -n "$url" ]] && break',
            "# ! true",
        ):
            with self.subTest(assertion=assertion):
                self.assertEqual(checker.unsafe_assertions(assertion), [])

    def test_multiline_assertions_and_diagnostic_blocks(self):
        self.assertEqual(checker.unsafe_assertions("[[\n a == b\n]]\necho later"), [(1, 3)])
        self.assertEqual(checker.unsafe_assertions("!\n true\necho later"), [(1, 2)])
        for text in (
            "[[\n a == b\n]] || false",
            "!\n false || false",
            '[[ a == b ]] || {\n echo "failure" >&2\n return 1\n}',
            '! true || {\n echo "failure"\n exit 1\n}',
            '! true || { printf "failure\n"; return 1; }',
        ):
            with self.subTest(text=text):
                self.assertEqual(checker.unsafe_assertions(text), [])
        for text in (
            "! true || {\n echo ignored\n}\necho later",
            "! true || { false &&\n return 1\n}\necho later",
            "! true || { echo ignored ||\n exit 1\n}\necho later",
        ):
            with self.subTest(text=text):
                self.assertEqual(checker.unsafe_assertions(text), [(1, 3)])

    def test_quoted_patterns_do_not_supply_guards(self):
        for assertion in ("! grep 'x || false' file", "! grep '&&' file", '! grep "||" file'):
            self.assertEqual(checker.unsafe_assertions(assertion), [(1, 1)])
        self.assertEqual(checker.unsafe_assertions("! grep '<<EOF' file\n! true"), [(1, 1), (2, 2)])

    def test_continuation_reports_whole_command(self):
        self.assertEqual(checker.unsafe_assertions("! grep x \\\n file\necho later"), [(1, 2)])

    def test_heredocs_and_here_strings(self):
        text = "cat <<'FIXTURE'\n! true\n[[ a == b ]]\nFIXTURE\n! grep x <<<y\n"
        self.assertEqual(checker.unsafe_assertions(text), [(5, 5)])
        self.assertEqual(checker.unsafe_assertions("cat <<-EOF\n\t! true\n\tEOF\n! true"), [(4, 4)])

    def test_cli_fails_with_file_and_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.bats"
            path.write_text('@test "false" {\n! true\necho later\n}\n')
            result = subprocess.run([sys.executable, str(CHECKER), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn(f"{path}:2:", result.stdout)
            path.write_text('@test "false" {\n! true || false\necho later\n}\n')
            result = subprocess.run([sys.executable, str(CHECKER), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
