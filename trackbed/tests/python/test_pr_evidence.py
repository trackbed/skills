from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tests.test_helper.script_loader import load_script

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pr-evidence.py"
pr_evidence = load_script("pr_evidence", SCRIPT)
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32


def run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the helper in-process so coverage measures it, returning a subprocess-shaped result."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = pr_evidence.main(list(args))
    return subprocess.CompletedProcess(list(args), code, stdout.getvalue(), stderr.getvalue())


class PrEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.repo = base / "repo"
        self.outside = base / "outside"
        self.repo.mkdir()
        self.outside.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        init = run("init", "--repo-root", str(self.repo))
        self.assertEqual(init.returncode, 0, init.stderr)
        self.manifest = json.loads(init.stdout)["manifest"]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def media(self, name: str, content: bytes = PNG, directory: Path | None = None) -> Path:
        path = (directory or self.outside) / name
        path.write_bytes(content + name.encode())
        return path

    def add(self, *args: str) -> subprocess.CompletedProcess[str]:
        return run("add", "--repo-root", str(self.repo), "--manifest", self.manifest, *args)

    def prepare(self, body: str) -> tuple[dict[str, object], Path]:
        out_dir = Path(self.tmp.name) / "out"
        out_dir.mkdir(exist_ok=True)
        body_file = out_dir / "input.md"
        body_file.write_text(body, encoding="utf-8")
        result = run(
            "prepare",
            "--repo-root",
            str(self.repo),
            "--manifest",
            self.manifest,
            "--body-file",
            str(body_file),
            "--out-dir",
            str(out_dir),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout), out_dir

    def test_init_hides_the_evidence_directory_from_git(self) -> None:
        exclude = (self.repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
        self.assertIn("/.trackbed/", exclude.splitlines())
        status = subprocess.run(
            ["git", "-C", str(self.repo), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(status.stdout, "")

    def test_add_spec_infers_role_and_copies_the_file(self) -> None:
        source = self.media("before-settings.png")
        result = self.add("--spec", f"{source}#Before: settings page without the toggle", "--source", "user")
        self.assertEqual(result.returncode, 0, result.stderr)
        entry = json.loads(result.stdout)
        self.assertEqual(entry["role"], "before")
        self.assertEqual(entry["kind"], "image")
        self.assertEqual(entry["alt"], "Before: settings page without the toggle")
        self.assertRegex(
            entry["ref"], r"^\./\.trackbed/pr-evidence/[^/]+/01-before-before-settings-page-without-the-toggle\.png$"
        )
        self.assertTrue((self.repo / entry["ref"]).is_file())

    def test_add_rejects_an_untracked_file_inside_the_repository(self) -> None:
        source = self.media("after.png", directory=self.repo)
        result = self.add("--spec", f"{source}#After", "--source", "user")
        self.assertEqual(result.returncode, 1)
        self.assertIn("untracked file inside the repository", result.stderr)

    def test_add_accepts_a_tracked_file_inside_the_repository(self) -> None:
        source = self.media("after.png", directory=self.repo)
        subprocess.run(["git", "-C", str(self.repo), "add", "after.png"], check=True)
        result = self.add("--spec", f"{source}#After", "--source", "user")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_add_rejects_mismatched_content_unsupported_types_and_symlinks(self) -> None:
        fake = self.media("after.png", content=b"API_KEY=secret\n")
        self.assertIn("does not match", self.add("--file", str(fake), "--alt", "After", "--source", "capture").stderr)
        svg = self.media("after.svg", content=b"<svg/>")
        self.assertIn(
            "unsupported file type", self.add("--file", str(svg), "--alt", "After", "--source", "capture").stderr
        )
        real = self.media("real.png")
        link = self.outside / "link.png"
        link.symlink_to(real)
        self.assertIn("symlink", self.add("--file", str(link), "--alt", "After", "--source", "capture").stderr)

    def test_add_rejects_alt_text_that_breaks_markdown(self) -> None:
        source = self.media("after.png")
        result = self.add("--file", str(source), "--alt", "After | [x](y)", "--source", "capture")
        self.assertEqual(result.returncode, 1)
        self.assertIn("alt text must not contain", result.stderr)

    def test_prepare_keeps_valid_references_and_strips_unknown_ones(self) -> None:
        before = json.loads(
            self.add(
                "--file",
                str(self.media("b.png")),
                "--alt",
                "Before: empty list",
                "--role",
                "before",
                "--source",
                "capture",
            ).stdout
        )
        after = json.loads(
            self.add(
                "--file",
                str(self.media("a.png")),
                "--alt",
                "After: list with items",
                "--role",
                "after",
                "--source",
                "capture",
            ).stdout
        )
        video = json.loads(
            self.add(
                "--file",
                str(self.media("flow.mp4", MP4)),
                "--alt",
                "Adding an item",
                "--role",
                "other",
                "--source",
                "capture",
            ).stdout
        )
        body = (
            "## Screenshots / Videos\n\n| Before | After |\n| --- | --- |\n"
            f"| ![Before: empty list]({before['ref']}) | ![After: list with items]({after['ref']}) |\n\n"
            "![Stale](./.trackbed/pr-evidence/20260101T000000Z-00000000/01-after-stale.png)\n"
        )
        summary, out_dir = self.prepare(body)
        published = (out_dir / "body.md").read_text(encoding="utf-8")
        self.assertIn(before["ref"], published)
        self.assertIn(after["ref"], published)
        self.assertNotIn("01-after-stale.png", published)
        self.assertIn("_Stale_", published)
        self.assertEqual(summary["appended_by_gh"], [video["ref"]])
        fallback = (out_dir / "fallback-body.md").read_text(encoding="utf-8")
        self.assertNotIn(".trackbed/pr-evidence", fallback)
        self.assertIn("_Before: empty list_", fallback)
        values = (out_dir / "attach.nul").read_bytes().split(b"\0")[:-1]
        self.assertEqual(
            [value.decode() for value in values],
            [f"{before['ref']}#Before: empty list", f"{after['ref']}#After: list with items", video["ref"]],
        )

    def test_add_rejects_the_same_file_twice(self) -> None:
        source = self.media("a.png")
        self.assertEqual(self.add("--file", str(source), "--alt", "After", "--source", "capture").returncode, 0)
        result = self.add("--file", str(source), "--alt", "After again", "--source", "capture")
        self.assertEqual(result.returncode, 1)
        self.assertIn("already staged", result.stderr)

    def test_prepare_keeps_only_the_canonical_form_and_drops_leftover_paths(self) -> None:
        entry = json.loads(
            self.add("--file", str(self.media("a.png")), "--alt", "After: list", "--source", "capture").stdout
        )
        body = (
            f"Keep ![After: list]({entry['ref']})\n"
            f"Link [the list]({entry['ref']})\n"
            f'Tag <img src="{entry["ref"]}" width="300">\n'
            f'Titled ![After: list]({entry["ref"]} "title")\n'
            f"Absolute {self.repo}/.trackbed/pr-evidence/x/01-after-y.png\n"
            "Plain text stays\n"
            "Mention of `.trackbed/pr-evidence/` stays\n"
        )
        summary, out_dir = self.prepare(body)
        published = (out_dir / "body.md").read_text(encoding="utf-8")
        self.assertIn(f"Keep ![After: list]({entry['ref']})\n", published)
        self.assertIn("Link _the list_\n", published)
        self.assertIn("Tag \n", published)
        self.assertIn("Plain text stays\n", published)
        self.assertIn("Mention of `.trackbed/pr-evidence/` stays\n", published)
        self.assertNotIn("Titled", published)
        self.assertNotIn("Absolute", published)
        self.assertEqual(published.count(".trackbed/pr-evidence"), 2)
        self.assertEqual(summary["dropped_lines"], 2)
        fallback = (out_dir / "fallback-body.md").read_text(encoding="utf-8")
        self.assertNotRegex(fallback, r"\.trackbed/pr-evidence/\w")
        self.assertIn("Mention of `.trackbed/pr-evidence/` stays\n", fallback)

    def test_prepare_rejects_a_file_changed_after_staging(self) -> None:
        entry = json.loads(self.add("--file", str(self.media("a.png")), "--alt", "After", "--source", "capture").stdout)
        (self.repo / entry["ref"]).write_bytes(PNG + b"tampered")
        out_dir = Path(self.tmp.name)
        body_file = out_dir / "body-in.md"
        body_file.write_text("body", encoding="utf-8")
        result = run(
            "prepare",
            "--repo-root",
            str(self.repo),
            "--manifest",
            self.manifest,
            "--body-file",
            str(body_file),
            "--out-dir",
            str(out_dir),
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("changed after it was staged", result.stderr)

    def test_strip_removes_every_evidence_reference(self) -> None:
        body_file = Path(self.tmp.name) / "strip-in.md"
        out_file = Path(self.tmp.name) / "strip-out.md"
        body_file.write_text(
            "Intro\n![After: list](./.trackbed/pr-evidence/x/01-after-list.png)\n"
            '<img src="./.trackbed/pr-evidence/x/02-other-y.png" width="400">\n',
            encoding="utf-8",
        )
        result = run("strip", "--body-file", str(body_file), "--out-file", str(out_file))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["stripped_references"], 2)
        self.assertEqual(out_file.read_text(encoding="utf-8"), "Intro\n_After: list_\n\n")

    def test_strip_keeps_lines_that_only_mention_the_evidence_directory(self) -> None:
        body_file = Path(self.tmp.name) / "mention-in.md"
        out_file = Path(self.tmp.name) / "mention-out.md"
        body = (
            "Stage evidence under `.trackbed/pr-evidence/` and upload it with gh.\n"
            "Each run lives in .trackbed/pr-evidence/<run-id>/.\n"
            "Leaked .trackbed/pr-evidence/x/01-after-y.png\n"
        )
        body_file.write_text(body, encoding="utf-8")
        result = run("strip", "--body-file", str(body_file), "--out-file", str(out_file))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["dropped_lines"], 1)
        self.assertEqual(
            out_file.read_text(encoding="utf-8"),
            "Stage evidence under `.trackbed/pr-evidence/` and upload it with gh.\n"
            "Each run lives in .trackbed/pr-evidence/<run-id>/.\n",
        )

    def test_manifest_outside_the_evidence_directory_is_rejected(self) -> None:
        rogue = self.outside / "manifest.json"
        rogue.write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")
        result = run("show", "--repo-root", str(self.repo), "--manifest", str(rogue))
        self.assertEqual(result.returncode, 1)
        self.assertIn("manifest must be below", result.stderr)


if __name__ == "__main__":
    unittest.main()
