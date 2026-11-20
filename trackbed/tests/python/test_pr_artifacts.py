from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pr-artifacts.py"
SPEC = importlib.util.spec_from_file_location("pr_artifacts", SCRIPT)
assert SPEC is not None
assert SPEC.loader is not None
pr_artifacts = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pr_artifacts
SPEC.loader.exec_module(pr_artifacts)
PR_URL = "https://github.com/acme/app/pull/7"

# Answers each POST the way `gh api --include` does: a status line, headers, a blank line, the body.
STUB_GH = r"""#!/usr/bin/env bash
if [ "$1" = repo ]; then
  printf '%s\n' "$*" >> "$GH_REPO_LOG"
  if [ "$VISIBILITY" = unknown ]; then
    echo "could not read visibility" >&2
    exit 1
  fi
  printf '%s\n' "$VISIBILITY"
  exit 0
fi
printf '%s\n' "$*" >> "$GH_LOG"
calls=$(wc -l < "$GH_LOG" | tr -d ' ')
cat > "$GH_REQUESTS/$calls.json"
respond() {
  printf 'HTTP/2.0 %s\r\nContent-Type: application/json\r\n\r\n%s' "$1" "$2"
}
refuse() {
  respond "$1" "{\"message\":\"$2\"}"
  echo "gh: $2 (HTTP ${1%% *})" >&2
  exit 1
}
case "$SCENARIO" in
  refuse-first) [ "$calls" = 1 ] && refuse "422 Unprocessable Entity" "name is invalid" ;;
  missing) refuse "404 Not Found" "Not Found" ;;
  response-lost) echo "unexpected EOF" >&2; exit 1 ;;
  gateway-error) refuse "502 Bad Gateway" "Bad Gateway" ;;
  no-number) respond "201 Created" "{}"; exit 0 ;;
esac
if [ -z "${NO_COLOR+x}" ] && [ "${CLICOLOR_FORCE:-0}" != 0 ]; then
  colored=$(printf '\033[32m{"number":%s,"html_url":"%s/artifacts/%s"}\033[0m' "$calls" "$PR_URL" "$calls")
  respond "201 Created" "$colored"
  exit 0
fi
respond "201 Created" "{\"number\":$calls,\"html_url\":\"$PR_URL/artifacts/$calls\"}"
"""


def run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the helper in-process so coverage measures it, returning a subprocess-shaped result."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = pr_artifacts.main(list(args))
    return subprocess.CompletedProcess(list(args), code, stdout.getvalue(), stderr.getvalue())


class PrArtifactsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.repo = base / "repo"
        self.outside = base / "outside"
        self.bin = base / "bin"
        self.requests = base / "requests"
        for directory in (self.repo, self.outside, self.bin, self.requests):
            directory.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.bin / "gh").write_text(STUB_GH, encoding="utf-8")
        (self.bin / "gh").chmod(0o755)
        self.log = base / "gh.log"
        self.repo_log = base / "gh-repo.log"
        init = run("init", "--repo-root", str(self.repo))
        self.assertEqual(init.returncode, 0, init.stderr)
        self.manifest = json.loads(init.stdout)["manifest"]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def document(self, name: str, content: str = "# Plan\n\nShip the list.\n", directory: Path | None = None) -> Path:
        path = (directory or self.outside) / name
        path.write_text(content, encoding="utf-8")
        return path

    def add(
        self, spec: str, *args: str, source: str = "workflow", public_ok: bool = True
    ) -> subprocess.CompletedProcess[str]:
        flags = []
        path = Path(spec.partition("#")[0])
        if source == "workflow":
            if public_ok:
                flags.append("--public-ok")
            if path.is_file():
                flags.extend(("--reviewed-sha256", hashlib.sha256(path.read_bytes()).hexdigest()))
        return run(
            "add",
            "--repo-root",
            str(self.repo),
            "--manifest",
            self.manifest,
            "--spec",
            spec,
            "--source",
            source,
            *flags,
            *args,
        )

    def upload(
        self, scenario: str = "created", pr_url: str = PR_URL, visibility: str = "PUBLIC"
    ) -> tuple[subprocess.CompletedProcess[str], list[str]]:
        env = {
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "GH_LOG": str(self.log),
            "GH_REPO": "other/repo",
            "GH_REPO_LOG": str(self.repo_log),
            "GH_REQUESTS": str(self.requests),
            "SCENARIO": scenario,
            "PR_URL": PR_URL,
            "VISIBILITY": visibility,
        }
        with mock.patch.dict(os.environ, env):
            result = run("upload", "--repo-root", str(self.repo), "--manifest", self.manifest, "--pr-url", pr_url)
        calls = self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []
        return result, calls

    def test_init_hides_the_artifact_directory_from_git(self) -> None:
        exclude = (self.repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
        self.assertIn("/.trackbed/", exclude.splitlines())
        nested = self.repo / "component" / ".trackbed"
        nested.mkdir(parents=True)
        self.document("policy.md", directory=nested)
        status = subprocess.run(
            ["git", "-C", str(self.repo), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(status.stdout, "?? component/.trackbed/policy.md\n")

    def test_staging_keeps_private_source_private_with_umask_022(self) -> None:
        source = self.document("plan.md")
        source.chmod(0o600)
        previous_umask = os.umask(0o022)
        try:
            self.manifest = json.loads(run("init", "--repo-root", str(self.repo)).stdout)["manifest"]
            added = self.add(str(source))
        finally:
            os.umask(previous_umask)
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertEqual(stat.S_IMODE(Path(self.manifest).parent.stat().st_mode), 0o700)

    def test_inspect_blocks_unignored_reports_before_reading_content(self) -> None:
        source = self.document("QA_REPORT.md", "", self.repo)
        result = run("inspect", "--repo-root", str(self.repo), "--file", str(source))
        self.assertEqual(result.returncode, 3)
        self.assertIn("untracked file inside the repository", result.stderr)
        self.assertEqual(result.stdout, "")
        (self.repo / ".gitignore").write_text("QA_REPORT.md\n", encoding="utf-8")
        result = run("inspect", "--repo-root", str(self.repo), "--file", str(source))
        self.assertEqual(result.returncode, 1)
        self.assertIn("is empty", result.stderr)

    def test_inspect_checks_report_symlinks_for_git_inclusion(self) -> None:
        source = self.repo / "QA_REPORT.md"
        target = self.document("local-report.md")
        source.symlink_to(target)
        inspect = ("inspect", "--repo-root", str(self.repo), "--file", str(source))
        result = run(*inspect)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("QA_REPORT.md is an untracked file", result.stderr)
        self.assertNotIn(str(target), result.stderr)

        git = ["git", "-C", str(self.repo)]
        subprocess.run([*git, "add", source.name], check=True)
        subprocess.run(
            [*git, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Track report link"],
            check=True,
        )
        source.unlink()
        source.symlink_to(target.with_name("missing-report.md"))
        result = run(*inspect)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("QA_REPORT.md has local changes", result.stderr)

    def test_workflow_blocks_staged_and_unstaged_report_changes(self) -> None:
        source = self.document("QA_REPORT.md", "# Local report\n", self.repo)
        git = ["git", "-C", str(self.repo)]
        inspect = ("inspect", "--repo-root", str(self.repo), "--file", str(source))

        def assert_blocked() -> None:
            for result in (run(*inspect), self.add(str(source))):
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("has local changes that the PR workflow could commit", result.stderr)
                self.assertEqual(result.stdout, "")

        subprocess.run([*git, "add", source.name], check=True)
        assert_blocked()
        subprocess.run(
            [*git, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Add report"],
            check=True,
        )
        unchanged = run(*inspect)
        self.assertEqual(unchanged.returncode, 1, unchanged.stderr)
        self.assertIn("is tracked by Git", unchanged.stderr)

        source.write_text("# Unpublished revision\n", encoding="utf-8")
        assert_blocked()
        subprocess.run([*git, "add", source.name], check=True)
        assert_blocked()

    def test_workflow_excludes_archived_review_reports_but_keeps_plans(self) -> None:
        (self.repo / ".gitignore").write_text(".context/\n", encoding="utf-8")
        archive = self.repo / ".context/code-plan-to-pr"
        review_dir = archive / "reviews" / "round-1"
        review_dir.mkdir(parents=True)
        report = self.document("REVIEW_OVERVIEW.md", "# Local review\n", review_dir)
        alias = self.outside / "review-alias"
        alias.symlink_to(review_dir, target_is_directory=True)
        other_dir = self.repo / ".context/pr-review-convergence/reviews"
        other_dir.mkdir(parents=True)
        other = self.document("CONVENTION_REVIEW_OVERVIEW.md", "# Another workflow's review\n", other_dir)
        inspect = ("inspect", "--repo-root", str(self.repo), "--file")
        for source in (report, alias / report.name, other):
            with self.subTest(source=source):
                inspection = run(*inspect, str(source))
                self.assertEqual(inspection.returncode, 1)
                self.assertEqual(inspection.stdout, "")
                for result in (inspection, self.add(str(source))):
                    self.assertIn("archived review reports stay local", result.stderr)

        plan = self.document("PR_PLAN.md", "# Eligible plan\n", archive)
        self.assertEqual(run(*inspect, str(plan)).returncode, 0)
        added = self.add(str(plan), "--type", "plan")
        self.assertEqual(added.returncode, 0, added.stderr)
        manifest = json.loads(Path(self.manifest).read_text())
        self.assertEqual([entry["name"] for entry in manifest["entries"]], [plan.name])

        explicit = self.add(str(other), source="user")
        self.assertEqual(explicit.returncode, 0, explicit.stderr)

    def test_workflow_excludes_case_alias_of_review_archive(self) -> None:
        (self.repo / ".gitignore").write_text("/.context/\n", encoding="utf-8")
        archive = self.repo / ".context/code-plan-to-pr/reviews"
        archive.mkdir(parents=True)
        report = self.document("REVIEW_OVERVIEW.md", "# Local review\n", archive)
        alias = archive.with_name("Reviews") / report.name
        if not alias.exists():
            self.skipTest("requires a case-insensitive filesystem")

        inspect = run("inspect", "--repo-root", str(self.repo), "--file", str(alias))
        for result in (inspect, self.add(str(alias))):
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("archived review reports stay local", result.stderr)

    def test_workflow_add_requires_exact_inspected_bytes_for_both_visibility_policies(self) -> None:
        original = b"# Plan\r\n\r\nApproved copy.\r\n"
        source = self.outside / "plan.md"
        source.write_bytes(original)
        source_args = ("--repo-root", str(self.repo), "--file", str(source))
        scanned = run("inspect", *source_args)
        inspection = json.loads(scanned.stdout)
        self.assertEqual(inspection, {"text": original.decode(), "sha256": hashlib.sha256(original).hexdigest()})
        add_args = ("add", *source_args, "--manifest", self.manifest, "--source", "workflow")
        digest_args = ("--reviewed-sha256", inspection["sha256"])
        self.assertEqual(run(*add_args).returncode, 1)

        source.write_text("# Replacement\n", encoding="utf-8")
        for public in ((), ("--public-ok",)):
            with self.subTest(public=public):
                changed = run(*add_args, *digest_args, *public)
                self.assertEqual(changed.returncode, 1)
                self.assertIn("SHA-256 of the inspected document", changed.stderr)
        self.assertEqual(json.loads(Path(self.manifest).read_text())["entries"], [])

        source.write_bytes(original)
        staged = run(*add_args, *digest_args, "--public-ok")
        self.assertEqual(staged.returncode, 0, staged.stderr)
        self.assertEqual((Path(self.manifest).parent / json.loads(staged.stdout)["file"]).read_bytes(), original)

    def test_ignore_override_blocks_new_runs_and_existing_staging(self) -> None:
        runs = Path(self.manifest).parent.parent
        existing_runs = list(runs.iterdir())
        (self.repo / ".gitignore").write_text("!/.trackbed/\n", encoding="utf-8")
        init = run("init", "--repo-root", str(self.repo))
        self.assertEqual(init.returncode, 1)
        self.assertIn("must be ignored by Git", init.stderr)
        self.assertEqual(list(runs.iterdir()), existing_runs)

        add = self.add(str(self.document("plan.md")))
        self.assertEqual(add.returncode, 1)
        self.assertIn("must be ignored by Git", add.stderr)
        self.assertIn(
            "must be ignored by Git", run("show", "--repo-root", str(self.repo), "--manifest", self.manifest).stderr
        )

    def test_add_copies_the_document_and_picks_its_type_and_name(self) -> None:
        plan = self.add(f"{self.document('plan (1).md')}", "--type", "plan")
        page = self.add(f"{self.document('walkthrough.html', '<h1>Walkthrough</h1>')}#Walkthrough: the list!")
        notes = self.add(f"{self.document('notes.txt', 'Root cause: stale cache.')}", source="user")
        for result in (plan, page, notes):
            self.assertEqual(result.returncode, 0, result.stderr)
        entries = [json.loads(result.stdout) for result in (plan, page, notes)]
        self.assertEqual([entry["type"] for entry in entries], ["plan", "embedded_html", "generic"])
        self.assertEqual([entry["name"] for entry in entries], ["plan 1.md", "Walkthrough the list", "notes.txt"])
        self.assertEqual(entries[1]["file"], "02-walkthrough-the-list.html")
        staged = Path(self.manifest).parent / entries[1]["file"]
        self.assertEqual(staged.read_text(encoding="utf-8"), "<h1>Walkthrough</h1>")

    def test_add_rejects_documents_github_cannot_show(self) -> None:
        cases = {
            "unsupported file type": self.document("state.json", "{}"),
            "is empty": self.document("empty.md", " \n"),
            "KB artifact limit": self.document("huge.md", "x" * (pr_artifacts.MAX_BYTES + 1)),
        }
        binary = self.outside / "binary.md"
        binary.write_bytes(b"\xff\xfe\x00plan")
        cases["not UTF-8 text"] = binary
        link = self.outside / "link.md"
        link.symlink_to(self.document("target.md"))
        cases["symlink"] = link
        for message, path in cases.items():
            with self.subTest(message=message):
                result = self.add(str(path))
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
        self.assertIn("not HTML pages", self.add(str(self.document("page.html", "<p>Hi</p>")), "--type", "plan").stderr)

    def test_read_rejects_document_larger_than_its_checked_metadata(self) -> None:
        source = self.document("plan.md")
        original_stat = source.stat()
        source.write_bytes(b"x" * (pr_artifacts.MAX_BYTES + 1))
        with mock.patch.object(Path, "stat", return_value=original_stat):
            with self.assertRaisesRegex(pr_artifacts.StagingError, "artifact limit"):
                pr_artifacts.read_document(source)

    def test_add_preserves_parent_traversal_after_a_symlinked_directory(self) -> None:
        target = self.outside / "target"
        target.mkdir()
        (target / "nested").mkdir()
        link = self.outside / "link"
        link.symlink_to(target / "nested", target_is_directory=True)
        source = self.document("plan.md", "# Intended plan\n", target)
        self.document("plan.md", "# Different plan\n")

        result = self.add(str(link / ".." / source.name), source="user")
        self.assertEqual(result.returncode, 0, result.stderr)
        staged = Path(self.manifest).parent / json.loads(result.stdout)["file"]
        self.assertEqual(staged.read_bytes(), source.read_bytes())

    def test_add_rejects_a_secret_without_printing_it(self) -> None:
        token = "ghp_" + "a1B2" * 9
        result = self.add(str(self.document("notes.md", f"# Notes\n\nToken: {token}\n")), source="user")
        self.assertEqual(result.returncode, 1)
        self.assertIn("notes.md line 3 looks like a secret (github-token)", result.stderr)
        self.assertNotIn(token, result.stderr)

    def test_add_and_upload_reject_credentials_in_artifact_names(self) -> None:
        token = "ghp_" + "a1B2" * 9
        source = self.document("notes.md")
        default_name = self.document(f"{token}.md")
        for spec in (str(default_name), f"{source}#{token}"):
            result = self.add(spec, source="user")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("artifact name line 1 looks like a secret (github-token)", result.stderr)
            self.assertNotIn(token, result.stderr)
        self.assertEqual(self.add(str(source)).returncode, 0)
        manifest = Path(self.manifest)
        payload = json.loads(manifest.read_text())
        payload["entries"][0]["name"] = token
        manifest.write_text(json.dumps(payload))
        result, calls = self.upload()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("artifact name line 1 looks like a secret (github-token)", result.stderr)
        self.assertNotIn(token, result.stderr)
        self.assertEqual(calls, [])

    def test_add_rejects_credentials_the_shared_patterns_miss(self) -> None:
        # Built from pieces so no scanner mistakes a sample for a real credential.
        jwt = ".".join(
            ("eyJ" + "hbGciOiJIUzI1NiJ9", "eyJ" + "zdWIiOiIxMjM0NTY3ODkwIn0", "dBjftJeZ4CVPmB92K27uhbUJU1p1r")
        )
        samples = {
            "url-credentials": "DATABASE_URL=postgres://app:" + "hunter2pw" + "@db.internal:5432/app",
            "authorization-header": "curl -H 'Authorization: Bearer "
            + "abcDEF123456ghiJKL"
            + "' https://api.example.com",
            "json-web-token": jwt,
            "token-prefix": "lin_api_" + "a1B2c3D4" * 4,
            "assigned-secret": "aws_secret_access_key = " + "wJalrXUtn" + "FEMI7K7MDENG",
            "private-key-block": "-----BEGIN PGP " + "PRIVATE KEY BLOCK-----",
        }
        for index, (label, line) in enumerate(samples.items()):
            with self.subTest(label=label):
                result = self.add(str(self.document(f"report-{index}.md", f"# QA\n\n{line}\n")))
                self.assertEqual(result.returncode, 1)
                self.assertIn(f"line 3 looks like a secret ({label})", result.stderr)
        self.assertIn("(assigned-secret)", self.add(str(self.document("env.md", "password: hunter2\n"))).stderr)
        plain = "# Plan\n\nThe token: field stays optional. Limit max_tokens to 4096. See https://example.com/a@b.\n"
        self.assertEqual(self.add(str(self.document("plain.md", plain))).returncode, 0)

    def test_add_keeps_repository_files_out_unless_git_ignores_them(self) -> None:
        untracked = self.add(str(self.document("PLAN.md", directory=self.repo)))
        self.assertIn("untracked file inside the repository", untracked.stderr)
        (self.repo / ".gitignore").write_text("QA_REPORT.md\n", encoding="utf-8")
        ignored = self.add(str(self.document("QA_REPORT.md", "# QA\n\nAll flows pass.\n", directory=self.repo)))
        self.assertEqual(ignored.returncode, 0, ignored.stderr)

        tracked = self.document("DESIGN.md", "# Design\n", directory=self.repo)
        git = ["git", "-C", str(self.repo)]
        subprocess.run([*git, "add", "DESIGN.md"], check=True)
        self.assertEqual(self.add(str(tracked)).returncode, 3)
        added = self.add(str(tracked), source="user")
        self.assertEqual(added.returncode, 1, added.stderr)
        self.assertIn("has local changes", added.stderr)
        subprocess.run(
            [*git, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Add design"],
            check=True,
        )
        self.assertEqual(self.add(str(tracked), source="user").returncode, 0)
        tracked.write_text("# Updated design\n", encoding="utf-8")
        self.assertIn("has local changes", self.add(str(tracked), source="user").stderr)
        show = ("show", "--repo-root", str(self.repo), "--manifest", self.manifest, "--check-source", str(tracked))
        result = run(*show)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("has local changes", result.stderr)

    def test_repository_case_aliases_preserve_source_checks(self) -> None:
        source = self.document("Notes.md", directory=self.repo)
        checkout_alias = self.repo.with_name("Repo") / source.name
        if not checkout_alias.exists():
            self.skipTest("requires a case-insensitive filesystem")

        added = self.add(str(checkout_alias), source="user")
        self.assertEqual(added.returncode, 1, added.stderr)
        self.assertIn("untracked file inside the repository", added.stderr)

        ignore = self.repo / ".gitignore"
        ignore.write_text("/Notes.md\n", encoding="utf-8")
        staged = self.add(str(checkout_alias), source="user")
        self.assertEqual(staged.returncode, 0, staged.stderr)
        ignore.write_text("", encoding="utf-8")
        show = ("show", "--repo-root", str(self.repo), "--manifest", self.manifest)
        rechecked = run(*show, "--check-source", str(checkout_alias))
        self.assertEqual(rechecked.returncode, 1, rechecked.stderr)
        self.assertIn("untracked file inside the repository", rechecked.stderr)

        ignore.write_text("/Notes.md\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "-f", source.name], check=True)
        file_alias = checkout_alias.with_name("notes.md")
        inspect = run("inspect", "--repo-root", str(self.repo), "--file", str(file_alias))
        self.assertEqual(inspect.returncode, 3, inspect.stderr)
        self.assertIn("has local changes that the PR workflow could commit", inspect.stderr)

    def test_tracked_lookup_treats_brackets_in_paths_literally(self) -> None:
        self.document("a.md", "# Tracked\n", self.repo)
        subprocess.run(["git", "-C", str(self.repo), "add", "a.md"], check=True)
        untracked = self.document("[a].md", directory=self.repo)
        result = self.add(str(untracked), source="user")
        self.assertEqual(result.returncode, 1)
        self.assertIn("untracked file inside the repository", result.stderr)

    def test_tracked_lookup_does_not_confuse_distinct_hard_links_with_case_aliases(self) -> None:
        tracked = self.document("Notes.md", directory=self.repo)
        untracked = self.repo / "notes.md"
        if untracked.exists():
            self.skipTest("requires a case-sensitive filesystem")
        untracked.hardlink_to(tracked)
        subprocess.run(["git", "-C", str(self.repo), "add", tracked.name], check=True)
        result = self.add(str(untracked), source="user")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("untracked file inside the repository", result.stderr)

    def test_ignore_lookup_treats_a_leading_colon_literally(self) -> None:
        (self.repo / ".gitignore").write_text("/draft.md\n", encoding="utf-8")
        source = self.document(":draft.md", directory=self.repo)
        result = run("inspect", "--repo-root", str(self.repo), "--file", str(source))
        self.assertEqual(result.returncode, 3)
        self.assertIn("untracked file inside the repository", result.stderr)

    def test_explicit_source_in_staging_root_must_itself_be_ignored(self) -> None:
        (self.repo / ".gitignore").write_text("!/.trackbed/\n/.trackbed/pr-artifacts/*/\n", encoding="utf-8")
        source = self.document("plan.md", directory=self.repo / ".trackbed" / "pr-artifacts")
        result = self.add(str(source), source="user")
        self.assertEqual(result.returncode, 1)
        self.assertIn("untracked file inside the repository", result.stderr)

    def test_show_can_recheck_explicit_originals_after_ignore_rules_change(self) -> None:
        ignore = self.repo / ".gitignore"
        ignore.write_text("/notes.md\n", encoding="utf-8")
        source = self.document("notes.md", directory=self.repo)
        spec = f"{source}#Local notes"
        self.assertEqual(self.add(spec, source="user").returncode, 0)
        show = ("show", "--repo-root", str(self.repo), "--manifest", self.manifest)
        check = (*show, "--check-source", spec)
        self.assertEqual(run(*check).returncode, 0)

        ignore.write_text("", encoding="utf-8")
        result = run(*check)
        self.assertEqual(result.returncode, 1)
        self.assertIn("notes.md is an untracked file", result.stderr)
        self.assertEqual(run(*show).returncode, 0)

        source.unlink()
        result = run(*check)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["entries"][0]["name"], "Local notes")

    def test_add_rejects_repeats_and_too_many_documents(self) -> None:
        first = self.document("plan.md")
        self.assertEqual(self.add(f"{first}#Plan").returncode, 0)
        self.assertIn("already staged", self.add(f"{first}#Plan again").stderr)
        self.assertIn("named 'Plan' is already staged", self.add(f"{self.document('other.md', '# Other')}#Plan").stderr)
        self.assertIn("at least one letter or number", self.add(f"{self.document('symbols.md', '# S')}#(!)").stderr)
        for index in range(pr_artifacts.MAX_ARTIFACTS - 1):
            self.assertEqual(self.add(str(self.document(f"note-{index}.md", f"# Note {index}"))).returncode, 0)
        self.assertIn("at most 10 artifacts", self.add(str(self.document("extra.md", "# Extra"))).stderr)

    def test_add_takes_a_path_with_a_hash_through_file_and_name(self) -> None:
        source = self.document("plan #2.md")
        self.assertIn("must be a regular file", self.add(str(source)).stderr)
        common = ("add", "--repo-root", str(self.repo), "--manifest", self.manifest, "--source", "workflow")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        result = run(*common, "--file", str(source), "--name", "Plan two", "--reviewed-sha256", digest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["name"], "Plan two")
        self.assertIn("pass either --spec", run(*common, "--spec", str(source), "--name", "Plan").stderr)
        self.assertIn("pass --spec or --file", run(*common).stderr)

    def test_remove_drops_a_staged_document_and_keeps_numbering_unique(self) -> None:
        first = json.loads(self.add(f"{self.document('plan.md')}#Plan").stdout)
        self.add(f"{self.document('qa.md', '# QA')}#QA report")
        common = ("--repo-root", str(self.repo), "--manifest", self.manifest)
        removed = run("remove", *common, "--name", "Plan")
        self.assertEqual(json.loads(removed.stdout), {"remaining": 1, "removed": "Plan"})
        self.assertFalse((Path(self.manifest).parent / first["file"]).exists())
        self.assertIn("no staged artifact is named 'Plan'", run("remove", *common, "--name", "Plan").stderr)
        again = json.loads(self.add(f"{self.document('notes.md', '# Notes')}#Notes").stdout)
        self.assertEqual(again["file"], "03-notes.md")
        self.upload()
        self.assertIn("already sent to the Pull Request", run("remove", *common, "--name", "Notes").stderr)

    def test_manifest_write_failures_leave_add_and_remove_retryable(self) -> None:
        source = self.document("plan.md")
        common = ("--repo-root", str(self.repo), "--manifest", self.manifest)
        with mock.patch.object(pr_artifacts, "write_manifest", side_effect=OSError("disk full")):
            self.assertEqual(self.add(str(source)).returncode, 1)
        self.assertEqual(list(Path(self.manifest).parent.glob("*.md")), [])
        self.assertEqual(self.add(str(source)).returncode, 0)

        with mock.patch.object(pr_artifacts, "write_manifest", side_effect=OSError("disk full")):
            self.assertEqual(run("remove", *common, "--name", "plan.md").returncode, 1)
        self.assertEqual(run("show", *common).returncode, 0)
        self.assertEqual(run("remove", *common, "--name", "plan.md").returncode, 0)

    def test_sequence_numbers_above_99_round_trip(self) -> None:
        result = self.add(str(self.document("qa.md", "# QA")))
        run_dir = Path(self.manifest).parent
        entry = json.loads(result.stdout)
        (run_dir / entry["file"]).rename(run_dir / "99-qa-md.md")
        payload = json.loads(Path(self.manifest).read_text())
        payload["entries"][0]["file"] = "99-qa-md.md"
        Path(self.manifest).write_text(json.dumps(payload))
        added = self.add(str(self.document("plan.md")))
        self.assertEqual(json.loads(added.stdout)["file"], "100-plan-md.md")
        common = ("--repo-root", str(self.repo), "--manifest", self.manifest)
        self.assertEqual(run("show", *common).returncode, 0)
        self.assertEqual(run("remove", *common, "--name", "plan.md").returncode, 0)

    def test_show_rejects_a_document_changed_after_staging(self) -> None:
        entry = json.loads(self.add(str(self.document("plan.md"))).stdout)
        shown = run("show", "--repo-root", str(self.repo), "--manifest", self.manifest)
        self.assertEqual(json.loads(shown.stdout)["entries"], [entry])
        (Path(self.manifest).parent / entry["file"]).write_text("# Changed\n", encoding="utf-8")
        result = run("show", "--repo-root", str(self.repo), "--manifest", self.manifest)
        self.assertEqual(result.returncode, 1)
        self.assertIn("changed after it was staged", result.stderr)

    def test_manifest_outside_the_artifact_directory_is_rejected(self) -> None:
        other = self.outside / "manifest.json"
        other.write_text('{"schema_version": 1, "entries": []}', encoding="utf-8")
        result = run("show", "--repo-root", str(self.repo), "--manifest", str(other))
        self.assertEqual(result.returncode, 1)
        self.assertIn("manifest must be below", result.stderr)

    def test_upload_creates_each_artifact_once(self) -> None:
        self.add(f"{self.document('plan.md')}#Plan", "--type", "plan")
        self.add(str(self.document("walkthrough.html", "<h1>Walkthrough</h1>")))
        result, calls = self.upload()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(
            report["uploaded"],
            [
                {"name": "Plan", "number": 1, "url": f"{PR_URL}/artifacts/1"},
                {"name": "walkthrough.html", "number": 2, "url": f"{PR_URL}/artifacts/2"},
            ],
        )
        self.assertEqual((report["failed"], report["not_attempted"], report["stopped"]), ([], [], None))
        self.assertEqual(len(calls), 2)
        self.assertIn("api --hostname github.com --include --method POST", calls[0])
        self.assertIn("repos/acme/app/issues/7/artifacts --input -", calls[0])
        self.assertEqual(
            json.loads((self.requests / "1.json").read_text(encoding="utf-8")),
            {"type": "plan", "name": "Plan", "body": "# Plan\n\nShip the list.\n"},
        )
        self.assertEqual(json.loads((self.requests / "2.json").read_text(encoding="utf-8"))["type"], "embedded_html")

        again, calls = self.upload()
        self.assertEqual(json.loads(again.stdout)["already_uploaded"], 2)
        self.assertEqual(json.loads(again.stdout)["uploaded"], [])
        self.assertEqual(len(calls), 2)
        other = self.upload(pr_url="https://github.com/acme/app/pull/8")[0]
        self.assertIn(f"already belongs to {PR_URL}", other.stderr)

    def test_upload_preserves_artifact_link_when_cli_color_is_forced(self) -> None:
        self.assertEqual(self.add(str(self.document("notes.md"))).returncode, 0)
        with mock.patch.dict(os.environ, {"CLICOLOR_FORCE": "1"}):
            os.environ.pop("NO_COLOR", None)
            result, _calls = self.upload()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout)["uploaded"], [{"name": "notes.md", "number": 1, "url": f"{PR_URL}/artifacts/1"}]
        )

    def test_upload_scans_again_what_it_sends(self) -> None:
        entry = json.loads(self.add(f"{self.document('plan.md')}#Plan").stdout)
        edited = "# Plan\n\nToken: ghp_" + "a1B2" * 9 + "\n"
        (Path(self.manifest).parent / entry["file"]).write_text(edited, encoding="utf-8")
        manifest = json.loads(Path(self.manifest).read_text(encoding="utf-8"))
        manifest["entries"][0]["sha256"] = hashlib.sha256(edited.encode("utf-8")).hexdigest()
        Path(self.manifest).write_text(json.dumps(manifest), encoding="utf-8")
        result, calls = self.upload()
        self.assertEqual(result.returncode, 1)
        self.assertIn("looks like a secret (github-token)", result.stderr)
        self.assertEqual(calls, [])

    def test_upload_counts_any_success_answer_as_uploaded(self) -> None:
        self.add(f"{self.document('plan.md')}#Plan")
        result, calls = self.upload("no-number")
        self.assertEqual(json.loads(result.stdout)["uploaded"], [{"name": "Plan", "number": None, "url": ""}])
        self.assertEqual(json.loads(self.upload()[0].stdout)["already_uploaded"], 1)
        self.assertEqual(len(calls), 1)

    def test_upload_continues_after_github_refuses_one_document(self) -> None:
        self.add(f"{self.document('plan.md')}#Plan")
        self.add(f"{self.document('qa.md', '# QA')}#QA report")
        result, calls = self.upload("refuse-first")
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["failed"], [{"name": "Plan", "error": "HTTP 422: name is invalid"}])
        self.assertEqual([item["name"] for item in report["uploaded"]], ["QA report"])
        self.assertIsNone(report["stopped"])
        self.assertEqual(len(calls), 2)

        retry, calls = self.upload()
        self.assertEqual([item["name"] for item in json.loads(retry.stdout)["uploaded"]], ["Plan"])
        self.assertEqual(len(calls), 3)

    def test_upload_stops_when_the_answer_would_repeat(self) -> None:
        self.add(f"{self.document('plan.md')}#Plan")
        self.add(f"{self.document('qa.md', '# QA')}#QA report")
        result, calls = self.upload("missing")
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["failed"], [{"name": "Plan", "error": "HTTP 404: Not Found"}])
        self.assertEqual(report["not_attempted"], ["QA report"])
        self.assertEqual(report["stopped"], "HTTP 404: Not Found")
        self.assertEqual(report["uploaded"], [])
        self.assertEqual(len(calls), 1)
        other = self.upload(pr_url="https://github.com/acme/app/pull/8")[0]
        self.assertIn(f"already belongs to {PR_URL}", other.stderr)

    def test_upload_never_retries_a_lost_response_or_gateway_error(self) -> None:
        for scenario, diagnostic in (("response-lost", "unexpected EOF"), ("gateway-error", "HTTP 502: Bad Gateway")):
            with self.subTest(scenario=scenario):
                self.manifest = json.loads(run("init", "--repo-root", str(self.repo)).stdout)["manifest"]
                self.log.unlink(missing_ok=True)
                self.add(f"{self.document('plan.md')}#Plan")
                self.add(f"{self.document('qa.md', '# QA')}#QA report")
                result, calls = self.upload(scenario)
                report = json.loads(result.stdout)
                self.assertEqual((report["unconfirmed"], report["not_attempted"]), (["Plan"], ["QA report"]))
                self.assertEqual(report["stopped"], diagnostic)
                self.assertEqual(report["failed"], [])
                self.assertEqual(len(calls), 1)

                retry, calls = self.upload()
                report = json.loads(retry.stdout)
                self.assertEqual(report["unconfirmed"], ["Plan"])
                self.assertEqual([entry["name"] for entry in report["uploaded"]], ["QA report"])
                self.assertEqual(len(calls), 2)

    def test_upload_records_an_attempt_before_calling_gh_and_excludes_concurrent_writes(self) -> None:
        self.add(f"{self.document('plan.md')}#Plan")
        args = ("upload", "--repo-root", str(self.repo), "--manifest", self.manifest, "--pr-url", PR_URL)

        def interrupt(*_args: object, **_kwargs: object) -> None:
            entry = json.loads(Path(self.manifest).read_text(encoding="utf-8"))["entries"][0]
            self.assertTrue(entry["unconfirmed"])
            competing = run(*args)
            self.assertIn("another command is using this artifact run", competing.stderr)
            raise KeyboardInterrupt

        with (
            mock.patch.object(pr_artifacts, "run_bounded", side_effect=interrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            run(*args)
        result, calls = self.upload()
        self.assertEqual(json.loads(result.stdout)["unconfirmed"], ["Plan"])
        self.assertEqual(calls, [])

    def test_workflow_documents_require_visibility_of_the_exact_pr_repository(self) -> None:
        pr_url = "https://github.example.com/destination/target/pull/9"
        for visibility in ("PUBLIC", "unknown", "PRIVATE", "INTERNAL"):
            with self.subTest(visibility=visibility):
                self.manifest = json.loads(run("init", "--repo-root", str(self.repo)).stdout)["manifest"]
                self.log.unlink(missing_ok=True)
                self.repo_log.unlink(missing_ok=True)
                self.add(str(self.document("plan.md")), public_ok=False)
                self.add(str(self.document("qa.md", "# QA")))
                self.add(str(self.document("notes.md", "# Notes")), source="user")
                result, calls = self.upload(pr_url=pr_url, visibility=visibility)
                report = json.loads(result.stdout)
                expected_skips = ["plan.md"] if visibility in ("PUBLIC", "unknown") else []
                self.assertEqual(report["skipped_visibility"], expected_skips)
                self.assertEqual(len(calls), 3 - len(expected_skips))
                expected_bodies = [("qa.md", "# QA"), ("notes.md", "# Notes")]
                if not expected_skips:
                    expected_bodies.insert(0, ("plan.md", "# Plan\n\nShip the list.\n"))
                sent = [json.loads((self.requests / f"{i}.json").read_text()) for i in range(1, len(calls) + 1)]
                self.assertEqual([(request["name"], request["body"]) for request in sent], expected_bodies)
                self.assertEqual(
                    self.repo_log.read_text(encoding="utf-8").splitlines(),
                    ["repo view github.example.com/destination/target --json visibility --jq .visibility"],
                )

    def test_stopped_public_upload_does_not_offer_private_documents_for_manual_upload(self) -> None:
        self.add(str(self.document("qa.md", "# Public QA")))
        self.add(str(self.document("plan.md")), public_ok=False)
        result, calls = self.upload(scenario="missing")
        report = json.loads(result.stdout)
        self.assertEqual(len(calls), 1)
        self.assertEqual(report["not_attempted"], [])
        self.assertEqual(report["skipped_visibility"], ["plan.md"])

    def test_show_recovers_unconfirmed_outcome_after_success_response_and_write_failure(self) -> None:
        self.add(str(self.document("plan.md")))
        write_manifest = pr_artifacts.write_manifest

        def fail_after_success(path, payload):
            if payload["entries"][0].get("uploaded"):
                raise OSError("disk full")
            write_manifest(path, payload)

        with mock.patch.object(pr_artifacts, "write_manifest", side_effect=fail_after_success):
            result, calls = self.upload()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(calls), 1)
        shown = run("show", "--repo-root", str(self.repo), "--manifest", self.manifest)
        entry = json.loads(shown.stdout)["entries"][0]
        self.assertTrue(entry["unconfirmed"])
        self.assertNotIn("uploaded", entry)

    def test_upload_never_sends_a_timed_out_document_again(self) -> None:
        self.add(f"{self.document('plan.md')}#Plan")
        self.add(f"{self.document('qa.md', '# QA')}#QA report")
        timeout = subprocess.TimeoutExpired(cmd="gh", timeout=pr_artifacts.UPLOAD_TIMEOUT)
        with mock.patch.object(pr_artifacts, "run_bounded", side_effect=timeout):
            result = run("upload", "--repo-root", str(self.repo), "--manifest", self.manifest, "--pr-url", PR_URL)
        report = json.loads(result.stdout)
        self.assertEqual((report["unconfirmed"], report["not_attempted"]), (["Plan"], ["QA report"]))
        self.assertIn("timed out", report["stopped"])
        self.assertEqual((report["uploaded"], report["failed"]), ([], []))

        retry, calls = self.upload()
        report = json.loads(retry.stdout)
        self.assertEqual(report["unconfirmed"], ["Plan"])
        self.assertEqual([item["name"] for item in report["uploaded"]], ["QA report"])
        self.assertEqual(len(calls), 1)

    def test_upload_can_retry_after_gh_is_missing(self) -> None:
        self.add(str(self.document("plan.md")), source="user")
        git_only = self.bin.parent / "git-only"
        git_only.mkdir()
        git = shutil.which("git")
        assert git is not None
        (git_only / "git").symlink_to(git)
        with mock.patch.dict(os.environ, {"PATH": str(git_only)}):
            result = run("upload", "--repo-root", str(self.repo), "--manifest", self.manifest, "--pr-url", PR_URL)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["unconfirmed"], [])
        self.assertEqual(report["failed"][0]["name"], "plan.md")
        self.assertIn("could not start gh", report["stopped"])

        retry, calls = self.upload()
        self.assertEqual([item["name"] for item in json.loads(retry.stdout)["uploaded"]], ["plan.md"])
        self.assertEqual(len(calls), 1)

    def test_upload_accepts_a_dot_github_repository(self) -> None:
        self.add(str(self.document("plan.md")), source="user")
        result, calls = self.upload(pr_url="https://github.com/acme/.github/pull/7")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("repos/acme/.github/issues/7/artifacts --input -", calls[0])

    def test_upload_rejects_anything_but_a_pull_request_url(self) -> None:
        self.add(str(self.document("plan.md")))
        for url in (
            "https://github.com/acme/app/issues/7",
            "https://github.com/acme/app/pull/7/files",
            "https://github.com/../app/pull/7",
            "https://github.com/acme/./pull/7",
            "https://github.com/acme/../pull/7",
            "acme/app#7",
        ):
            with self.subTest(url=url):
                result, calls = self.upload(pr_url=url)
                self.assertEqual(result.returncode, 1)
                self.assertIn("--pr-url must be", result.stderr)
                self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
