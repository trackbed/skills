"""Run pr:create's Step 8.4 creation block against a stub gh for each attachment outcome."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REFERENCE = Path(__file__).resolve().parents[2] / "skills" / "pr:create" / "references" / "confirmation-and-creation.md"
BLOCK_PATTERN = re.compile(r"```bash\n(cd \"\{repo-root\}\" \|\| exit 1\n.*?\nexit \"\$PR_CREATE_STATUS\"\n)```", re.S)
PR_URL = "https://github.com/acme/app/pull/7"

STUB_GH = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "$GH_LOG"
case "$1 $2" in
  "pr list") echo "${OPEN_COUNT:-0}"; exit 0 ;;
  "pr create") ;;
  *) exit 64 ;;
esac
calls=$(grep -c '^pr create' "$GH_LOG")
attach=false
for arg in "$@"; do [ "$arg" = --attach ] && attach=true; done
case "$SCENARIO" in
  success) echo "$PR_URL"; exit 0 ;;
  partial) echo "failed to upload ./a.png: 500" >&2; echo "$PR_URL"; exit 1 ;;
  upload-before-creation)
    if [ "$attach" = true ]; then echo "could not upload ./a.png: 403" >&2; exit 1; fi
    echo "$PR_URL"; exit 0 ;;
  network) echo "error connecting to api.github.com" >&2; exit 1 ;;
  retry-fails)
    if [ "$calls" = 1 ]; then echo "attaching files is not supported" >&2; exit 1; fi
    echo "pull request create failed: GraphQL error" >&2; exit 1 ;;
esac
exit 99
"""


class CreationBlockTest(unittest.TestCase):
    def setUp(self) -> None:
        match = BLOCK_PATTERN.search(REFERENCE.read_text(encoding="utf-8"))
        self.assertIsNotNone(match, "creation block not found")
        assert match is not None
        self.block = match.group(1)
        self.tmp = Path(tempfile.mkdtemp())
        self.bin = self.tmp / "bin"
        self.plugin = self.tmp / "plugin"
        self.repo = self.tmp / "repo"
        for directory in (self.bin, self.plugin / "scripts", self.repo):
            directory.mkdir(parents=True)
        (self.bin / "gh").write_text(STUB_GH, encoding="utf-8")
        (self.bin / "gh").chmod(0o755)
        stack = self.plugin / "scripts" / "resolve-stack-membership.sh"
        stack.write_text("#!/usr/bin/env bash\necho 'STACK_MEMBERSHIP=none'\n", encoding="utf-8")
        stack.chmod(0o755)
        self.log = self.tmp / "gh.log"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_block(self, scenario: str, attachments: bool = True) -> tuple[subprocess.CompletedProcess[str], list[str]]:
        evidence_dir = Path(tempfile.mkdtemp(prefix="trackbed-pr-evidence.", dir="/tmp"))
        title = Path(tempfile.mkstemp(prefix="trackbed-pr-title.", dir="/tmp")[1])
        body = Path(tempfile.mkstemp(prefix="trackbed-pr-body.", dir="/tmp")[1])
        title.write_text("feat: add list", encoding="utf-8")
        body.write_text("body", encoding="utf-8")
        (evidence_dir / "body.md").write_text("![After](./a.png)", encoding="utf-8")
        (evidence_dir / "fallback-body.md").write_text("_After_", encoding="utf-8")
        (evidence_dir / "attach.nul").write_bytes(b"./a.png#After\0./b.mp4\0")
        values = {
            "{repo-root}": str(self.repo),
            "{pr-title-file}": str(title),
            "{pr-body-file}": str(body),
            "{pr-evidence-dir}": str(evidence_dir) if attachments else "",
            "{pr-publish-body-file}": str(evidence_dir / "body.md") if attachments else str(body),
            "{pr-fallback-body-file}": str(evidence_dir / "fallback-body.md") if attachments else "",
            "{pr-attach-file}": str(evidence_dir / "attach.nul") if attachments else "",
            "{base-branch}": "main",
            "{feature-branch}": "feature/list",
        }
        script = self.block
        for placeholder, value in values.items():
            script = script.replace(placeholder, value)
        self.assertNotRegex(script, r"\{[a-z-]+\}")
        env = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "CLAUDE_PLUGIN_ROOT": str(self.plugin),
            "GH_LOG": str(self.log),
            "SCENARIO": scenario,
            "PR_URL": PR_URL,
        }
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env, check=False)
        if not attachments:
            shutil.rmtree(evidence_dir)
        self.assertFalse(evidence_dir.exists() or title.exists() or body.exists(), "temporary files must be removed")
        calls = self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []
        return result, calls

    def labels(self, result: subprocess.CompletedProcess[str]) -> dict[str, str]:
        return dict(line.split("=", 1) for line in result.stdout.splitlines() if re.match(r"^[A-Z_]+=", line))

    def test_success_passes_every_attachment_once(self) -> None:
        result, calls = self.run_block("success")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.labels(result), {"PR_CREATE_STATUS": "0", "ATTACHMENTS_PASSED": "2", "ATTACHMENT_RETRY": "false"}
        )
        self.assertEqual(len(calls), 1)
        self.assertIn("--attach ./a.png#After --attach ./b.mp4", calls[0])

    def test_partial_upload_keeps_the_created_pull_request_without_retrying(self) -> None:
        result, calls = self.run_block("partial")
        self.assertEqual(result.returncode, 1)
        self.assertIn(PR_URL, result.stdout.splitlines())
        self.assertEqual(self.labels(result)["ATTACHMENT_RETRY"], "false")
        self.assertEqual([call for call in calls if call.startswith("pr list")], [])

    def test_upload_failure_before_creation_retries_once_with_the_fallback_body(self) -> None:
        result, calls = self.run_block("upload-before-creation")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.labels(result)["ATTACHMENT_RETRY"], "true")
        creates = [call for call in calls if call.startswith("pr create")]
        self.assertEqual(len(creates), 2)
        self.assertNotIn("--attach", creates[1])
        self.assertIn("fallback-body.md", creates[1])

    def test_a_network_failure_is_not_retried(self) -> None:
        result, calls = self.run_block("network")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.labels(result)["ATTACHMENT_RETRY"], "false")
        self.assertEqual(len(calls), 1)

    def test_a_failed_retry_reports_its_own_status(self) -> None:
        result, _calls = self.run_block("retry-fails")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.labels(result)["ATTACHMENT_RETRY"], "true")
        self.assertIn("GraphQL error", result.stdout)

    def test_without_attachments_the_block_creates_once(self) -> None:
        result, calls = self.run_block("success", attachments=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.labels(result)["ATTACHMENTS_PASSED"], "0")
        self.assertNotIn("--attach", calls[0])


if __name__ == "__main__":
    unittest.main()
