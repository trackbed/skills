from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

if __package__:
    from .script_loader import load_script
else:
    from script_loader import load_script

CHECKER = Path(__file__).resolve().parents[1] / "test_helper/check_bats_assertions.py"
checker = load_script("check_bats_assertions", CHECKER)


class BatsAssertionCheckTests(unittest.TestCase):
    def test_suite_can_run_directly(self):
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run(
                [sys.executable, "-E", str(Path(__file__).resolve()), "--help"],
                cwd=cwd,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

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
        self.assertEqual(checker.unsafe_assertions('! grep "first\n<<EOF\nsecond" file || false\n'), [])
        self.assertEqual(checker.unsafe_assertions("run bash -c '\ncat <<EOF\n! true\nEOF\n'\n"), [])

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

    def test_raw_pins_count_commands_in_guidance_source(self):
        text = r"""
grep -q anchor "$skill"
! grep -qF -- '--old' "$skill" || false
printf '%s' "$section" | grep -qF anchor
run bash -c '
grep -qF anchor "$skill"
cat <<EOF
grep -qF fixture "$skill"
EOF
'
echo "first
<<EOF
second"
grep \
  -qF anchor "$skill"
# grep -qF anchor "$skill"
echo 'grep -qF anchor "$skill"'
cat <<'FIXTURE'
grep -qF anchor "$skill"
FIXTURE
"""
        self.assertEqual(checker.count_raw_pins(text), 5)

    def test_cli_enforces_each_guidance_suite_ceiling(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gut-check-guidance.bats"
            path.write_text('grep -qF anchor "$skill"\n')
            result = subprocess.run([sys.executable, str(CHECKER), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn(f"{path}: 1 raw grep pins exceed baseline 0", result.stdout)

            path.write_text('assert_required_text "$skill" anchor\n')
            result = subprocess.run([sys.executable, str(CHECKER), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
