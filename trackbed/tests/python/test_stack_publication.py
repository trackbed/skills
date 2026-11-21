"""Isolated Git repositories exercise frozen multi-ref publication."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tests.test_helper.script_loader import load_script

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/git-rewrite/stack-publication.py"


class StackPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-b", "lower")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("commit", "--allow-empty", "-m", "Initial")
        self.git("branch", "upper")
        self.remote = self.root / "remote.git"
        self.git("init", "--bare", str(self.remote))
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "origin", "lower", "upper")
        self.other = self.root / "other"
        self.git("clone", "-b", "lower", str(self.remote), str(self.other))
        self.git("config", "user.name", "Other", cwd=self.other)
        self.git("config", "user.email", "other@example.invalid", cwd=self.other)
        self.inventory = self.root / "inventory.json"
        self.inventory.write_text(json.dumps({"branches": [{"name": "lower"}, {"name": "upper"}]}))
        self.bin = self.root / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text('#!/bin/sh\ncat "$STACK_FIXTURE"\n')
        gh.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", "STACK_FIXTURE": str(self.inventory)}
        self.state = self.root / "snapshot.json"

    def git(self, *args, cwd=None):
        return subprocess.check_output(["git", *args], cwd=cwd or self.repo, stderr=subprocess.PIPE, text=True).strip()

    def run_helper(self, operation, success=True):
        args = ["python3", str(SCRIPT), operation, "--state", str(self.state)]
        if operation == "capture":
            args += ["--remote", "origin"]
        module = load_script("stack_publication", SCRIPT)
        out, err = io.StringIO(), io.StringIO()
        previous = os.getcwd()
        try:
            os.chdir(self.repo)
            with patch.dict(os.environ, self.env, clear=True), patch.object(sys, "argv", args[1:]):
                with redirect_stdout(out), redirect_stderr(err):
                    code = module.main()
        finally:
            os.chdir(previous)
        result = subprocess.CompletedProcess(args, code, out.getvalue(), err.getvalue())
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def rewrite(self):
        self.git("commit", "--amend", "--allow-empty", "-m", "Rewritten lower")
        self.git("branch", "-f", "upper", "HEAD")

    def test_publishes_exact_active_refs_without_tags_or_configured_extra_refs(self):
        self.run_helper("capture")
        self.git("branch", "unrelated")
        self.git("config", "remote.origin.push", "refs/heads/*:refs/heads/*")
        self.git("config", "push.followTags", "true")
        self.rewrite()
        self.git("tag", "-a", "unrelated-tag", "-m", "Do not publish")
        self.run_helper("publish")
        remote = self.git("ls-remote", "origin")
        self.assertNotIn("unrelated", remote)
        for name in ("lower", "upper"):
            self.assertEqual(self.git("rev-parse", name, cwd=self.remote), self.git("rev-parse", name))

    def test_concurrent_update_after_fetch_rejects_whole_atomic_push(self):
        self.run_helper("capture")
        original_upper = self.git("rev-parse", "upper", cwd=self.remote)
        self.git("commit", "--allow-empty", "-m", "Collaborator", cwd=self.other)
        self.git("push", "origin", "lower", cwd=self.other)
        collaborator = self.git("rev-parse", "HEAD", cwd=self.other)
        self.git("fetch", "origin")
        self.rewrite()
        result = self.run_helper("publish", success=False)
        self.assertIn("stale info", result.stderr)
        self.assertEqual(self.git("rev-parse", "lower", cwd=self.remote), collaborator)
        self.assertEqual(self.git("rev-parse", "upper", cwd=self.remote), original_upper)
        self.assertTrue(self.state.exists())

    def test_git_valid_names_remain_literal_during_capture_and_publication(self):
        names = ["topic/o'brien", "topic/écriture", "_topic", "topic/$(touch${IFS}executed)"]
        for name in names:
            self.git("check-ref-format", "--branch", name)
            self.git("branch", name)
            self.git("push", "origin", f"refs/heads/{name}:refs/heads/{name}")
        self.inventory.write_text(json.dumps({"branches": [{"name": name} for name in names]}))
        self.run_helper("capture")
        self.git("commit", "--amend", "--allow-empty", "-m", "Rewrite literal-name fixtures")
        for name in names:
            self.git("branch", "-f", name, "HEAD")
        self.run_helper("publish")
        for name in names:
            self.assertEqual(
                self.git("rev-parse", f"refs/heads/{name}", cwd=self.remote), self.git("rev-parse", "HEAD")
            )
        self.assertFalse((self.repo / "executed").exists())

    def test_capture_cannot_refresh_existing_snapshot(self):
        self.run_helper("capture")
        original = self.state.read_bytes()
        self.run_helper("capture", success=False)
        self.assertEqual(self.state.read_bytes(), original)

    def advance_remote_lower(self):
        self.git("commit", "--allow-empty", "-m", "Remote", cwd=self.other)
        self.git("push", "origin", "lower", cwd=self.other)
        return self.git("rev-parse", "HEAD", cwd=self.other)

    def assert_remote_unchanged(self, lower, upper):
        self.assertEqual(self.git("rev-parse", "lower", cwd=self.remote), lower)
        self.assertEqual(self.git("rev-parse", "upper", cwd=self.remote), upper)
        self.assertTrue(self.state.exists())

    def test_preparation_integrates_behind_only_branch_in_its_worktree(self):
        remote = self.advance_remote_lower()
        self.run_helper("capture")
        self.run_helper("prepare")
        self.assertEqual(self.git("rev-parse", "HEAD"), remote)
        snapshot = json.loads(self.state.read_text())
        self.assertEqual(snapshot["phase"], "prepared")
        self.assertEqual(snapshot["prepared"]["lower"], remote)
        self.assertIn("already succeeded", self.run_helper("prepare", success=False).stderr)
        self.assertEqual(json.loads(self.state.read_text())["phase"], "prepared")
        self.rewrite()
        self.run_helper("publish")
        self.assertEqual(self.git("rev-parse", "lower", cwd=self.remote), self.git("rev-parse", "lower"))

    def test_publish_without_prepare_refuses_behind_only_branch(self):
        remote = self.advance_remote_lower()
        upper = self.git("rev-parse", "upper", cwd=self.remote)
        self.run_helper("capture")
        self.rewrite()
        result = self.run_helper("publish", success=False)
        self.assertIn("lower differed from the remote at capture", result.stderr)
        self.assertIn("phase: none", result.stderr)
        self.assert_remote_unchanged(remote, upper)

    def test_preparation_refuses_divergence(self):
        self.git("commit", "--allow-empty", "-m", "Remote", cwd=self.other)
        self.git("push", "origin", "lower", cwd=self.other)
        self.git("commit", "--allow-empty", "-m", "Local")
        before = self.git("rev-parse", "HEAD")
        self.run_helper("capture")
        self.run_helper("prepare", success=False)
        self.assertEqual(self.git("rev-parse", "HEAD"), before)

    def test_inventory_change_stops_before_publication(self):
        self.run_helper("capture")
        self.inventory.write_text(json.dumps({"branches": [{"name": "lower"}]}))
        self.rewrite()
        self.assertIn("inventory changed", self.run_helper("publish", success=False).stderr)

    def test_endpoint_changes_do_not_redirect_publication(self):
        self.run_helper("capture")
        wrong = self.root / "wrong.git"
        self.git("init", "--bare", str(wrong))
        self.git("remote", "set-url", "--push", "origin", str(wrong))
        self.rewrite()
        self.run_helper("publish")
        self.assertEqual(self.git("rev-parse", "lower", cwd=self.remote), self.git("rev-parse", "lower"))
        self.assertEqual(self.git("ls-remote", str(wrong)), "")

    def test_multiple_push_endpoints_are_rejected(self):
        self.git("config", "--add", "remote.origin.pushurl", str(self.remote))
        self.git("config", "--add", "remote.origin.pushurl", str(self.root / "wrong.git"))
        self.run_helper("capture", success=False)
        self.assertFalse(self.state.exists())

    def test_atomic_support_is_required_without_partial_fallback(self):
        self.run_helper("capture")
        old = self.git("rev-parse", "lower", cwd=self.remote)
        self.git("config", "receive.advertiseAtomic", "false", cwd=self.remote)
        self.rewrite()
        self.run_helper("publish", success=False)
        self.assertEqual(self.git("rev-parse", "lower", cwd=self.remote), old)
        self.assertEqual(self.git("rev-parse", "upper", cwd=self.remote), old)

    def test_unconfirmed_inventory_and_invalid_states_fail_before_snapshot(self):
        for entry in [{"name": "-bad"}, {"name": "lower", "isMerged": "false"}]:
            self.inventory.write_text(json.dumps({"branches": [entry]}))
            self.run_helper("capture", success=False)
            self.assertFalse(self.state.exists())

    def test_cli_capture_smoke(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "capture", "--state", str(self.state), "--remote", "origin"],
            cwd=self.repo,
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.state.read_text())["branches"], ["lower", "upper"])

    def test_ignored_file_collision_preserves_local_content_and_head(self):
        (self.repo / ".git/info/exclude").write_text("local.env\n")
        (self.repo / "local.env").write_text("unpublished local config\n")
        (self.other / "local.env").write_text("remote config\n")
        self.git("add", "local.env", cwd=self.other)
        self.git("commit", "-m", "Track environment fixture", cwd=self.other)
        self.git("push", "origin", "lower", cwd=self.other)
        old = self.git("rev-parse", "HEAD")
        self.run_helper("capture")
        self.run_helper("prepare", success=False)
        self.assertEqual((self.repo / "local.env").read_text(), "unpublished local config\n")
        self.assertEqual(self.git("rev-parse", "HEAD"), old)
        self.assertTrue(self.state.exists())
        self.assertEqual(json.loads(self.state.read_text())["phase"], "prepare_failed")
        remote = self.git("rev-parse", "lower", cwd=self.remote)
        self.rewrite()
        self.assertIn("phase: prepare_failed", self.run_helper("publish", success=False).stderr)
        self.assert_remote_unchanged(remote, old)

    def test_merged_and_queued_branches_remain_untouched(self):
        original = self.git("rev-parse", "HEAD")
        for name in ("merged", "queued"):
            self.git("branch", name)
            self.git("push", "origin", name)
        self.inventory.write_text(
            json.dumps(
                {
                    "branches": [
                        {"name": "lower"},
                        {"name": "upper"},
                        {"name": "merged", "isMerged": True},
                        {"name": "queued", "isQueued": True},
                    ]
                }
            )
        )
        self.run_helper("capture")
        self.rewrite()
        for name in ("merged", "queued"):
            self.git("branch", "-f", name, "HEAD")
        self.run_helper("publish")
        snapshot = json.loads(self.state.read_text())
        self.assertEqual(snapshot["branches"], ["lower", "upper"])
        for name in ("merged", "queued"):
            self.assertEqual(self.git("rev-parse", name, cwd=self.remote), original)

    def test_restructure_publishes_before_dropping_catalog_layer(self):
        # Execute the shipped final restructure block; the fake catalog changes
        # on unstack/init so publishing afterward would fail its inventory check.
        old_upper = self.git("rev-parse", "upper")
        self.run_helper("capture")
        self.git("commit", "--amend", "--allow-empty", "-m", "Reordered lower")
        gh = self.bin / "gh"
        gh.write_text("""#!/bin/sh
case "$1 $2" in
  "stack view") cat "$STACK_FIXTURE" ;;
  "stack unstack") printf '{"branches":[]}\n' > "$STACK_FIXTURE" ;;
  "stack init") printf '{"branches":[{"name":"lower"}]}\n' > "$STACK_FIXTURE" ;;
  *) exit 99 ;;
esac
""")
        skill = SCRIPT.parents[2] / "skills/pr:stack/SKILL.md"
        section = skill.read_text().split("4. Publish the frozen original branch set", 1)[1]
        block = section.split("```bash\n", 1)[1].split("```", 1)[0]
        block = block.replace("<recorded-trunk>", "main").replace("<branches bottom-to-top>", "lower")
        env = {**self.env, "CLAUDE_PLUGIN_ROOT": str(SCRIPT.parents[2]), "STACK_PUBLICATION_STATE": str(self.state)}
        result = subprocess.run(
            ["bash", "-eu", "-c", block], cwd=self.repo, env=env, text=True, capture_output=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.inventory.read_text())["branches"], [{"name": "lower"}])
        self.assertEqual(self.git("rev-parse", "lower", cwd=self.remote), self.git("rev-parse", "lower"))
        self.assertEqual(self.git("rev-parse", "upper", cwd=self.remote), old_upper)

    def test_missing_remote_ref_uses_absence_lease(self):
        self.git("push", "origin", "--delete", "upper")
        self.run_helper("capture")
        self.assertEqual(json.loads(self.state.read_text())["expected"]["upper"], "")
        self.run_helper("publish")
        self.assertEqual(self.git("rev-parse", "upper", cwd=self.remote), self.git("rev-parse", "upper"))


if __name__ == "__main__":
    unittest.main()
