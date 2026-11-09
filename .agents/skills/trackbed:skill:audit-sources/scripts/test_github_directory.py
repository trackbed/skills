#!/usr/bin/env python3

from __future__ import annotations

import base64
import io
import json
import subprocess
import tempfile
import unittest
from collections.abc import Mapping
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

from github_directory import MAX_FILE_BYTES, main, skip_reason

Key = tuple[str, tuple[tuple[str, str], ...]]

HEAD = f"{99:040x}"
DIRECTORY = "skills/review"
URL = f"https://github.com/o/r/tree/{HEAD}/{DIRECTORY}"
TREE_KEY: Key = (f"repos/o/r/git/trees/{HEAD}", (("recursive", "1"),))


def blob_sha(number: int) -> str:
    return f"{number:040x}"


def blob_key(number: int) -> Key:
    return f"repos/o/r/git/blobs/{blob_sha(number)}", ()


def blob(data: bytes) -> dict[str, Any]:
    encoded = base64.encodebytes(data).decode("ascii")
    return {"sha": "ignored", "encoding": "base64", "content": encoded, "size": len(data)}


def tree_entry(path: str, number: int, *, size: int = 10, mode: str = "100644", kind: str = "blob") -> dict[str, Any]:
    return {"path": path, "mode": mode, "type": kind, "sha": blob_sha(number), "size": size}


class FakeGh:
    """Serve canned `gh api` results and record every call; unexpected calls fail the test."""

    def __init__(self, responses: Mapping[Key, Any]) -> None:
        self.responses = responses
        self.calls: list[Key] = []

    def __call__(self, endpoint: str, params: Mapping[str, str]) -> subprocess.CompletedProcess[str]:
        call = (endpoint, tuple(sorted(params.items())))
        self.calls.append(call)
        if call not in self.responses:
            raise AssertionError(f"unexpected gh api call: {call}")
        return subprocess.CompletedProcess(["gh"], 0, json.dumps(self.responses[call]), "")


def run_cli(responses: Mapping[Key, Any], url: str = URL) -> tuple[int, dict[str, Any] | None, str, str, FakeGh]:
    fake = FakeGh(responses)
    stdout, stderr = io.StringIO(), io.StringIO()
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "body"
        with patch("github_changes.run_gh_api", fake), redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["--url", url, "--output", str(output)])
        body = output.read_text(encoding="utf-8") if output.exists() else ""
    summary = json.loads(stdout.getvalue()) if stdout.getvalue() else None
    return code, summary, body, stderr.getvalue(), fake


def mixed_directory() -> dict[Key, Any]:
    entries = [
        tree_entry(DIRECTORY, 0, kind="tree"),
        tree_entry(f"{DIRECTORY}/references", 0, kind="tree"),
        tree_entry(f"{DIRECTORY}/references/guide.md", 2),
        tree_entry(f"{DIRECTORY}/SKILL.md", 1),
        tree_entry(f"{DIRECTORY}/scripts/run.py", 3),
        tree_entry(f"{DIRECTORY}/references/sources.yaml", 10),
        tree_entry(f"{DIRECTORY}/LICENSE.md", 11),
        tree_entry(f"{DIRECTORY}/assets/app.min.js", 12),
        tree_entry(f"{DIRECTORY}/vendor/lib.py", 13),
        tree_entry(f"{DIRECTORY}/link.md", 14, mode="120000"),
        tree_entry(f"{DIRECTORY}/scripts/huge.py", 15, size=MAX_FILE_BYTES + 1),
        tree_entry(f"{DIRECTORY}/assets/logo.png", 4),
        tree_entry(f"{DIRECTORY}/assets/latin1.txt", 5),
        tree_entry("skills/review-extra/SKILL.md", 20),
        tree_entry("skills/other/SKILL.md", 21),
    ]
    return {
        TREE_KEY: {"truncated": False, "tree": entries},
        blob_key(1): blob(b"# Review\n"),
        blob_key(2): blob(b"Guide body"),
        blob_key(3): blob(b"print('hi')\n"),
        blob_key(4): blob(b"\x89PNG\r\n\x1a\n\0\0"),
        blob_key(5): blob("café\n".encode("latin-1")),
    }


class SkipRuleTests(unittest.TestCase):
    def test_matches_the_skill_directory_rules(self) -> None:
        cases = {
            "references/sources.yaml": "source manifest",
            "LICENSE": "license or notice",
            "LICENSE-MIT": "license or notice",
            "references/EveryInc-LICENSE": "license or notice",
            "references/THIRD_PARTY_NOTICES.md": "license or notice",
            "licence.txt": "license or notice",
            "NOTICE.md": "license or notice",
            "COPYING": "license or notice",
            "assets/app.min.css": "minified or vendored",
            "third_party/x/y.md": "minified or vendored",
            "node_modules/pkg/index.js": "minified or vendored",
            "SKILL.md": None,
            "sources.yaml": None,
            "references/license-review.md": None,
            "references/licensing.md": None,
            "vendor.md": None,
        }
        for path, reason in cases.items():
            with self.subTest(path=path):
                self.assertEqual(skip_reason(path, "100644", 10), reason)
        self.assertEqual(skip_reason("link.md", "120000", 10), "symlink")
        self.assertIsNone(skip_reason("big.md", "100644", MAX_FILE_BYTES))
        self.assertEqual(skip_reason("big.md", "100644", MAX_FILE_BYTES + 1), "larger than 100 KB")


class FetchTests(unittest.TestCase):
    def test_writes_text_files_in_path_order_and_reports_skips(self) -> None:
        code, summary, body, stderr, fake = run_cli(mixed_directory())
        self.assertEqual(code, 0, stderr)
        self.assertEqual(
            body,
            "==> SKILL.md <==\n# Review\n\n"
            "==> references/guide.md <==\nGuide body\n\n"
            "==> scripts/run.py <==\nprint('hi')\n",
        )
        assert summary is not None
        self.assertEqual(summary["files"], ["SKILL.md", "references/guide.md", "scripts/run.py"])
        self.assertEqual(summary["file_count"], 3)
        self.assertEqual(
            summary["skipped"],
            [
                {"path": "LICENSE.md", "reason": "license or notice"},
                {"path": "assets/app.min.js", "reason": "minified or vendored"},
                {"path": "assets/latin1.txt", "reason": "binary"},
                {"path": "assets/logo.png", "reason": "binary"},
                {"path": "link.md", "reason": "symlink"},
                {"path": "references/sources.yaml", "reason": "source manifest"},
                {"path": "scripts/huge.py", "reason": "larger than 100 KB"},
                {"path": "vendor/lib.py", "reason": "minified or vendored"},
            ],
        )
        fetched = {call for call in fake.calls if "/git/blobs/" in call[0]}
        self.assertEqual(fetched, {blob_key(number) for number in (1, 2, 3, 4, 5)})

    def test_rejects_urls_that_are_not_a_directory_at_a_commit(self) -> None:
        for url in (
            f"https://github.com/o/r/tree/main/{DIRECTORY}",
            f"https://github.com/o/r/tree/{HEAD}",
            f"https://github.com/o/r/blob/{HEAD}/{DIRECTORY}/SKILL.md",
            f"https://raw.githubusercontent.com/o/r/{HEAD}/{DIRECTORY}/SKILL.md",
            "https://github.com/o/r",
            "https://example.com/x",
        ):
            with self.subTest(url=url):
                code, summary, body, stderr, fake = run_cli({}, url)
                self.assertEqual((code, summary, body, fake.calls), (2, None, "", []))
                self.assertTrue(stderr.startswith("github_directory.py: "))

    def test_exits_1_on_truncated_tree_or_empty_directory(self) -> None:
        cases = {
            "truncated": {TREE_KEY: {"truncated": True, "tree": [tree_entry(f"{DIRECTORY}/SKILL.md", 1)]}},
            "no files under": {TREE_KEY: {"truncated": False, "tree": [tree_entry("skills/other/SKILL.md", 1)]}},
        }
        for message, responses in cases.items():
            with self.subTest(message=message):
                code, summary, body, stderr, _ = run_cli(responses)
                self.assertEqual((code, summary, body), (1, None, ""))
                self.assertIn(message, stderr)

    def test_exits_1_on_malformed_blob(self) -> None:
        responses: dict[Key, Any] = {
            TREE_KEY: {"truncated": False, "tree": [tree_entry(f"{DIRECTORY}/SKILL.md", 1)]},
            blob_key(1): {"encoding": "utf-8", "content": "plain"},
        }
        code, summary, _, stderr, _ = run_cli(responses)
        self.assertEqual((code, summary), (1, None))
        self.assertIn("SKILL.md: malformed blob response: expected base64 encoding", stderr)

    def test_exits_1_on_invalid_base64_blob(self) -> None:
        responses: dict[Key, Any] = {
            TREE_KEY: {"truncated": False, "tree": [tree_entry(f"{DIRECTORY}/SKILL.md", 1)]},
            blob_key(1): {"encoding": "base64", "content": "abc"},
        }
        code, summary, _, stderr, _ = run_cli(responses)
        self.assertEqual((code, summary), (1, None))
        self.assertIn("SKILL.md: malformed blob response: invalid base64 content", stderr)

    def test_exits_1_when_every_file_is_skipped(self) -> None:
        responses: dict[Key, Any] = {
            TREE_KEY: {
                "truncated": False,
                "tree": [tree_entry(f"{DIRECTORY}/LICENSE", 1), tree_entry(f"{DIRECTORY}/logo.png", 2)],
            },
            blob_key(2): blob(b"\x89PNG\0"),
        }
        code, summary, body, stderr, _ = run_cli(responses)
        self.assertEqual((code, summary, body), (1, None, ""))
        self.assertIn("no comparable text files", stderr)

    def test_exits_1_on_malformed_tree_entry_without_fetching_blobs(self) -> None:
        bad_sha = dict(tree_entry(f"{DIRECTORY}/SKILL.md", 1), sha="../../contents/x")
        no_size = {key: value for key, value in tree_entry(f"{DIRECTORY}/SKILL.md", 1).items() if key != "size"}
        for entry in (bad_sha, no_size):
            with self.subTest(entry=entry):
                code, summary, _, stderr, fake = run_cli({TREE_KEY: {"truncated": False, "tree": [entry]}})
                self.assertEqual((code, summary), (1, None))
                self.assertIn("malformed tree entry", stderr)
                self.assertEqual(fake.calls, [TREE_KEY])


if __name__ == "__main__":
    unittest.main()
