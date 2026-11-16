"""Execute shipped checkpoint and publication excerpts in isolated repositories."""

import os
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]


def blocks(path):
    return [textwrap.dedent(s) for s in re.findall(r"^[ \t]*```bash\n(.*?)^[ \t]*```", path.read_text(), re.S | re.M)]


class ReviewRewriteSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-b", "feature")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.repo / ".gitignore").write_text(".context/\n")
        (self.repo / "work").write_text("original\n")
        self.git("add", ".")
        self.git("commit", "-m", "Initial fixture")
        skill = PLUGIN / "skills/pr:resolve-review/SKILL.md"
        excerpts = blocks(skill)
        self.checkpoint = next(s for s in excerpts if s.startswith("mkdir -p .context/resolve-review"))
        self.restore = next(s for s in excerpts if "CHECKPOINT_RESTORE_STATUS=not-needed" in s)
        self.cleanup = next(s for s in excerpts if "VALIDATION_STATUS:-not-run" in s)

    def git(self, *args, cwd=None):
        return subprocess.check_output(["git", *args], cwd=cwd or self.repo, stderr=subprocess.PIPE, text=True).strip()

    def shell(self, script, **env):
        return subprocess.run(
            ["bash", "-eu", "-c", script],
            cwd=self.repo,
            env={**os.environ, **env},
            text=True,
            capture_output=True,
            check=False,
        )

    def test_report_remains_available_and_unrelated_work_is_restored(self):
        report = self.repo / "input report[*].md"
        report.write_text("input\n")
        (self.repo / "work").write_text("staged\n")
        self.git("add", "work")
        (self.repo / "work").write_text("unstaged\n")
        (self.repo / "unrelated").write_text("untracked\n")
        result = self.shell(
            self.checkpoint
            + """
test -f "$CHECKPOINT_INPUT"
test ! -f unrelated
printf 'rewritten\n' > "$CHECKPOINT_INPUT"
"""
            + self.restore
            + self.cleanup
            + """
test "$CHECKPOINT_RESTORE_STATUS" = restored
test ! -f "$CHECKPOINT_FILE"
""",
            CHECKPOINT_INPUT=report.name,
            VALIDATION_STATUS="passed",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report.read_text(), "rewritten\n")
        self.assertEqual((self.repo / "unrelated").read_text(), "untracked\n")
        self.assertEqual((self.repo / "work").read_text(), "unstaged\n")
        self.assertEqual(self.git("show", ":work"), "staged")
        self.assertTrue(self.git("stash", "list"))

    def test_report_only_does_not_adopt_an_existing_stash(self):
        (self.repo / "work").write_text("old stash\n")
        self.git("stash", "push", "-m", "other run")
        old = self.git("rev-parse", "refs/stash")
        (self.repo / "report.md").write_text("report\n")
        result = self.shell(
            self.checkpoint + '\ntest -z "$CHECKPOINT_STASH_SHA"\n' + self.restore, CHECKPOINT_INPUT="report.md"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("rev-parse", "refs/stash"), old)

    def test_interleaved_worktree_stash_does_not_change_checkpoint_ownership(self):
        other = self.root / "other"
        self.git("worktree", "add", "-b", "other", str(other), "HEAD")
        (self.repo / "work").write_text("own work\n")
        (other / "work").write_text("other work\n")
        wrapper = """git() {
  command git "$@"
  result=$?
  if [ "$1 $2" = "stash push" ]; then
    command git -C "$OTHER_WORKTREE" stash push -m other-session
  fi
  return "$result"
}
"""
        result = self.shell(
            wrapper
            + self.checkpoint
            + """
test "$CHECKPOINT_STASH_SHA" != "$(command git rev-parse refs/stash)"
"""
            + self.restore,
            OTHER_WORKTREE=str(other),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.repo / "work").read_text(), "own work\n")
        self.assertEqual(len(self.git("stash", "list", "--format=%H").splitlines()), 2)
        self.assertEqual(self.git("show", "refs/stash:work"), "other work")

    def test_report_only_checkpoint_does_not_adopt_an_interleaved_stash(self):
        other = self.root / "other"
        self.git("worktree", "add", "-b", "other", str(other), "HEAD")
        (other / "work").write_text("other work\n")
        (self.repo / "report.md").write_text("input\n")
        wrapper = """git() {
  command git "$@"
  result=$?
  if [ "$1 $2" = "stash push" ]; then
    command git -C "$OTHER_WORKTREE" stash push -m other-session
  fi
  return "$result"
}
"""
        result = self.shell(
            wrapper + self.checkpoint + '\ntest -z "$CHECKPOINT_STASH_SHA"\n' + self.restore,
            OTHER_WORKTREE=str(other),
            CHECKPOINT_INPUT="report.md",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.repo / "work").read_text(), "original\n")
        self.assertEqual(self.git("show", "refs/stash:work"), "other work")
        self.assertTrue((self.repo / "report.md").exists())

    def test_restore_conflict_keeps_stash_and_checkpoint(self):
        (self.repo / "work").write_text("local\n")
        result = self.shell(
            self.checkpoint
            + """
printf 'fix\n' > work
git add work
git commit -m Fix
"""
            + self.restore
            + self.cleanup
            + """
test "$CHECKPOINT_RESTORE_STATUS" = conflicted
test -f "$CHECKPOINT_FILE"
git cat-file -e "$CHECKPOINT_STASH_SHA"
""",
            VALIDATION_STATUS="passed",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.git("stash", "list"))

    def test_failed_validation_retains_checkpoint(self):
        result = self.shell(
            self.checkpoint + self.restore + self.cleanup + '\ntest -f "$CHECKPOINT_FILE"\n', VALIDATION_STATUS="failed"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_intervening_push_is_rejected_after_fetch_for_both_rewrite_flows(self):
        remote = self.root / "remote.git"
        self.git("init", "--bare", str(remote))
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "origin", "feature")
        collaborator = self.root / "collaborator"
        self.git("clone", "--branch", "feature", str(remote), str(collaborator))
        self.git("config", "user.name", "Collaborator", cwd=collaborator)
        self.git("config", "user.email", "collaborator@example.invalid", cwd=collaborator)
        for name in ("fixup-flow", "consolidation-flow"):
            with self.subTest(name=name):
                self.git("fetch", "origin")
                self.git("reset", "--hard", "origin/feature")
                excerpts = blocks(PLUGIN / f"skills/pr:fix-ci/references/{name}.md")
                capture = excerpts[0]
                push = next(s for s in excerpts if "HEAD:$REWRITE_REMOTE_REF" in s)
                result = self.shell(
                    capture
                    + """
git -C "$COLLABORATOR" commit --allow-empty -m Collaborator
git -C "$COLLABORATOR" push origin feature
git fetch origin
git commit --amend --allow-empty -m Rewritten
"""
                    + push,
                    IN_STACK="false",
                    COLLABORATOR=str(collaborator),
                )
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("stale info", result.stderr)
                self.assertEqual(
                    self.git("rev-parse", "refs/heads/feature", cwd=remote),
                    self.git("rev-parse", "HEAD", cwd=collaborator),
                )


if __name__ == "__main__":
    unittest.main()
