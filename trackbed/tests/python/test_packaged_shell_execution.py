"""Execute packaged excerpts in fresh Bash and zsh processes without publication."""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
SHELLS = ("bash", "zsh")


def host_substitute(text):
    """Model the positional-token substitution that previously broke excerpts."""
    return re.sub(r"\$[0-9]+", "HOST_ARGUMENT", text)


class PackagedShellExecutionTests(unittest.TestCase):
    def run_shell(self, shell, code, cwd, env=None):
        self.assertIsNotNone(shutil.which(shell), f"Required fixture shell missing: {shell}")
        return subprocess.run(
            [shell, "-c", host_substitute(code)],
            cwd=cwd,
            env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(PLUGIN), **(env or {})},
            text=True,
            capture_output=True,
            check=False,
        )

    def test_rebase_awk_and_refspec_arguments_survive(self):
        text = (PLUGIN / "skills/pr:rebase/SKILL.md").read_text()
        awk = next(line for line in text.splitlines() if line.startswith("PRE_REBASE_REMOTE_OID="))
        push = next(line for line in text.splitlines() if line.startswith("git push "))
        for shell in SHELLS:
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as tmp:
                code = "\n".join(
                    [
                        "LEASE_BRANCH=feature/test",
                        'REMOTE_REFS="' + "a" * 40 + '\trefs/heads/feature/test"',
                        awk,
                        '[ "$PRE_REBASE_REMOTE_OID" = "' + "a" * 40 + '" ] || exit 1',
                        "CURRENT_BRANCH=feature/test",
                        # Intercept publication: capture arguments only.
                        'git() { printf "<%s>\\n" "$@"; }',
                        push,
                    ]
                )
                result = self.run_shell(shell, code, tmp)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("<refs/heads/feature/test:refs/heads/feature/test>", result.stdout)
                self.assertIn("<--force-with-lease=refs/heads/feature/test:" + "a" * 40 + ">", result.stdout)

    def test_literal_awk_field_filters_after_host_substitution(self):
        for shell in SHELLS:
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as tmp:
                text = (PLUGIN / "skills/code:refactor-opportunities/SKILL.md").read_text()
                pipeline = text.split("```bash\n   git log --since=", 1)[1].split("\n   ```", 1)[0]
                awk_pipeline = pipeline[pipeline.index("awk '") :]
                history = (
                    "".join(f">>> {index}\none/a.py\ntwo/b.py\n" for index in range(3))
                    + ">>> nested\none/a.py\none/nested/c.py\n"
                )
                result = self.run_shell(
                    shell,
                    "printf '%s' \"$COCHANGE_FIXTURE\" | " + awk_pipeline,
                    tmp,
                    {"COCHANGE_FIXTURE": history},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.split(), ["3", "one/a.py", "two/b.py"])
                text = (PLUGIN / "skills/pr:resolve-review/SKILL.md").read_text()
                lookup = next(
                    line for line in text.splitlines() if line.startswith("CHECKPOINT_STASH_SHA=") and "awk" in line
                )
                result = self.run_shell(
                    shell,
                    'CHECKPOINT_STASHES="abc owned-marker"\nCHECKPOINT_STASH_MARKER=owned-marker\n'
                    + lookup
                    + '\nprintf "%s" "$CHECKPOINT_STASH_SHA"',
                    tmp,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "abc")

    def test_convention_capture_preserves_spaced_paths_and_html_filter(self):
        text = (PLUGIN / "skills/pr:convention-review/SKILL.md").read_text()
        function = re.search(r"capture_untracked_scope\(\) \{.*?\n\}", text, re.S).group()
        for shell in SHELLS:
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as tmp:
                subprocess.run(["git", "init", "-q", tmp], check=True)
                Path(tmp, "a [1]*.txt").write_text("fixture\n")
                Path(tmp, "report.html").write_text("omitted\n")
                scope = Path(tmp, ".git/scope")
                scope.mkdir()
                (scope / "changed-files.txt").write_text("a [1]*.txt\n")
                code = (
                    function + "\nREVIEW_SCOPE_DIR=.git/scope\ncapture_untracked_scope .git/scope/diff .git/scope/list"
                )
                result = self.run_shell(shell, code, tmp)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((scope / "list").read_bytes(), b"a [1]*.txt\0")
                self.assertIn("+fixture", (scope / "diff").read_text())

    def test_stack_inventory_in_fresh_shell_rejects_bad_or_changed_inventory(self):
        helper = PLUGIN / "skills/git:recreate-commits/scripts/stack-branch-names.sh"
        for shell in SHELLS:
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as tmp:
                gh = Path(tmp, "gh")
                gh.write_text('#!/bin/sh\nprintf "%s" "$FIXTURE_STACK"\n')
                gh.chmod(0o755)
                env = {
                    "PATH": tmp + os.pathsep + os.environ["PATH"],
                    "FIXTURE_STACK": '{"branches":[{"name":"feature/a"},{"name":"feature/b"}]}',
                }
                result = self.run_shell(shell, '"' + str(helper) + '"', tmp, env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "feature/a\nfeature/b\n")
                frozen = result.stdout.rstrip("\n")
                env["FIXTURE_STACK"] = '{"branches":[{"name":"feature/a"}]}'
                result = self.run_shell(
                    shell,
                    'actual=$("' + str(helper) + '") && [ "$actual" = "$FROZEN" ]',
                    tmp,
                    {**env, "FROZEN": frozen},
                )
                self.assertNotEqual(result.returncode, 0)
                env["FIXTURE_STACK"] = '{"branches":[]}'
                self.assertNotEqual(self.run_shell(shell, '"' + str(helper) + '"', tmp, env).returncode, 0)

    def test_cleanup_excerpt_runs_in_fresh_shell_and_preserves_content(self):
        text = (PLUGIN / "skills/linear:review-pr/references/pr-inspection.md").read_text()
        cleanup = text.split("## Cleanup")[1].split("```bash\n")[1].split("\n```")[0]
        for shell in SHELLS:
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp, "repo")
                repo.mkdir()
                subprocess.run(["git", "init", "-q", str(repo)], check=True)
                parent = Path(tmp, "parent [1]* with spaces")
                wt = parent / "wt"
                wt.mkdir(parents=True)
                (wt / ".git").touch()
                sentinel = wt / "keep"
                sentinel.touch()
                env = {"ORIG_ROOT": str(repo), "TMP_PARENT": str(parent), "WORKTREE_DIR": str(wt)}
                self.assertNotEqual(self.run_shell(shell, cleanup, wt, env).returncode, 0)
                self.assertTrue(sentinel.exists())
                sentinel.unlink()
                # Start inside the worktree, as the inspection procedure does, and require
                # the post-removal check to run from a directory that still exists.
                result = self.run_shell(shell, cleanup + "\ngit worktree list --porcelain > /dev/null", wt, env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(parent.exists())


if __name__ == "__main__":
    unittest.main()
