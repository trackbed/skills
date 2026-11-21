#!/usr/bin/env python3
"""Run the test suites mapped to the files a change touches.

  python3 changed-tests.py [--base REF]

The changed files are those that differ from the merge base with REF (default
origin/main), plus staged, unstaged, and untracked files, with deleted and
renamed-away paths kept. When REF does not resolve, only uncommitted and
untracked files count, as in the format check. The rules that map a changed file
to suites are described in docs/development.md under Running Tests.

The script prints each selected suite with the files and rules that selected it,
lists the changed files no rule maps so the user can choose a suite, then runs
the Node, Python, and Bats suites from the plugin directory. It exits 0 when
nothing ran or every runner passed, and 1 when a runner failed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PLUGIN_ROOT.parent
INVENTORY = Path("config") / "coverage-production-sources.json"
RUNNERS = ("node", "python", "bats")

Run = Callable[..., subprocess.CompletedProcess[Any]]


def git_paths(repo_root: Path, *args: str) -> list[str]:
    result = subprocess.run(["git", "-C", str(repo_root), *args], check=True, stdout=subprocess.PIPE, text=True)
    return [path for path in result.stdout.split("\0") if path]


def changed_files(base: str, repo_root: Path) -> tuple[list[str], bool]:
    """Return the repository paths changed against base and whether base resolved."""
    probe = ["git", "-C", str(repo_root), "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"]
    has_base = subprocess.run(probe, capture_output=True).returncode == 0
    paths: set[str] = set()
    if has_base:
        paths.update(git_paths(repo_root, "diff", "--name-only", "-z", "--no-renames", f"{base}...HEAD"))
    paths.update(git_paths(repo_root, "diff", "--name-only", "-z", "--no-renames", "HEAD"))
    paths.update(git_paths(repo_root, "ls-files", "-z", "--others", "--exclude-standard"))
    return sorted(paths), has_base


def runner_for(path: str, plugin: str) -> str | None:
    """Name the runner for a test file, or None when path is not a runnable test."""
    file = PurePosixPath(path)
    tests = PurePosixPath(plugin, "tests")
    if file.parent == tests and file.suffix == ".bats":
        return "bats"
    if file.parent == tests / "node" and file.name.endswith(".test.js"):
        return "node"
    if file.name.startswith("test_") and file.suffix == ".py":
        maintenance = file.parts[:2] == (".agents", "skills") and file.parent.name == "scripts"
        if file.parent == tests / "python" or maintenance:
            return "python"
    return None


def name_matches(path: str, plugin: str) -> list[str]:
    """Return the unit tests a source would be paired with by name."""
    file = PurePosixPath(path)
    if file.parts[0] not in (plugin, ".agents"):
        return []
    if file.suffix == ".js":
        return [f"{plugin}/tests/node/{file.stem}.test.js"]
    if file.suffix == ".py":
        name = f"test_{file.stem.replace('-', '_')}.py"
        return [f"{plugin}/tests/python/{name}", str(file.parent / name)]
    return []


def skill_of(path: str, plugin: str) -> str | None:
    parts = PurePosixPath(path).parts
    if len(parts) >= 4 and parts[0] == plugin and parts[1] == "skills":
        return f"{plugin}/skills/{parts[2]}/SKILL.md"
    return None


def select_suites(
    paths: Sequence[str], inventory: dict[str, Any], repo_root: Path, plugin: str
) -> tuple[dict[str, list[str]], list[str]]:
    """Map changed paths to existing suites with their reasons, plus the paths nothing maps."""
    skill_suites: dict[str, list[str]] = {}
    for entry in inventory["skill_contracts"]:
        for skill in entry["skills"]:
            skill_suites.setdefault(skill, []).append(entry["suite"])
    source_suites: dict[str, list[str]] = {}
    for language in ("javascript", "python", "shell"):
        for source, suites in inventory[language]["contract_only"].items():
            source_suites.setdefault(source, []).extend(suites)

    selected: dict[str, list[str]] = {}
    unmapped: list[str] = []
    for path in paths:
        is_test = runner_for(path, plugin) is not None
        if is_test:
            candidates = [(path, "changed test")]
        else:
            skill = skill_of(path, plugin)
            candidates = [(suite, "skill contract") for suite in skill_suites.get(skill or "", [])]
            candidates += [(suite, "contract_only") for suite in source_suites.get(path, [])]
            candidates += [(suite, "name match") for suite in name_matches(path, plugin)]
        found = [
            (suite, rule) for suite, rule in candidates if runner_for(suite, plugin) and (repo_root / suite).is_file()
        ]
        # A deleted test file selects nothing, but it is not an unmapped change.
        if not found and not is_test:
            unmapped.append(path)
        for suite, rule in found:
            selected.setdefault(suite, []).append(f"{path} ({rule})")
    return dict(sorted(selected.items())), unmapped


def runner_commands(suites: Sequence[str], repo_root: Path, plugin_root: Path) -> list[tuple[str, list[str]]]:
    """Build the runner commands, run from the plugin directory.

    Node and Bats get one command each. Python gets one `unittest discover` per file,
    because maintenance-skill tests outside the plugin directory cannot be imported
    through `python3 -m unittest <path>`.
    """
    plugin = plugin_root.name
    grouped: dict[str, list[str]] = {runner: [] for runner in RUNNERS}
    for suite in sorted(suites):
        runner = runner_for(suite, plugin)
        if runner:
            grouped[runner].append(os.path.relpath(repo_root / suite, plugin_root))
    commands: list[tuple[str, list[str]]] = []
    if grouped["node"]:
        commands.append(("node", ["node", "--test", *grouped["node"]]))
    for test in grouped["python"]:
        directory, name = os.path.split(test)
        commands.append(("python", ["python3", "-m", "unittest", "discover", "-s", directory, "-p", name]))
    if grouped["bats"]:
        commands.append(("bats", ["bats", *grouped["bats"]]))
    return commands


def main(
    argv: Sequence[str],
    repo_root: Path = REPO_ROOT,
    plugin_root: Path = PLUGIN_ROOT,
    run: Run = subprocess.run,
) -> int:
    parser = argparse.ArgumentParser(description="Run the test suites mapped to changed files.")
    parser.add_argument("--base", default="origin/main", help="ref whose merge base the change is compared with")
    args = parser.parse_args(argv)

    paths, has_base = changed_files(args.base, repo_root)
    inventory = json.loads((plugin_root / INVENTORY).read_text(encoding="utf-8"))
    suites, unmapped = select_suites(paths, inventory, repo_root, plugin_root.name)

    if not has_base:
        print(f"test-changed: {args.base} not found; only uncommitted and untracked files count.", file=sys.stderr)
    if not paths:
        print(f"No files changed against {args.base}; no tests ran.")
        return 0

    print(f"Changed files against {args.base}: {len(paths)}")
    if suites:
        print(f"Selected suites: {len(suites)}")
        for suite, reasons in suites.items():
            print(f"  {os.path.relpath(repo_root / suite, plugin_root)}")
            for reason in reasons:
                print(f"    <- {reason}")
    if unmapped:
        print(f"Changed files with no mapped suite: {len(unmapped)}; choose a suite from docs/code-map.md")
        for path in unmapped:
            print(f"  {path}")
    if not suites:
        print("No tests ran.")
        return 0

    failed: list[str] = []
    for runner, command in runner_commands(list(suites), repo_root, plugin_root):
        print(f"\n$ {' '.join(command)}", flush=True)
        if run(command, cwd=plugin_root).returncode and runner not in failed:
            failed.append(runner)
    if failed:
        print(f"\ntest-changed: {', '.join(failed)} suites failed.", file=sys.stderr)
        return 1
    print(f"\ntest-changed: all {len(suites)} selected suites passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
