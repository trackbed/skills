#!/usr/bin/env python3
"""Outline and import graph for trackbed:code:refactor-opportunities scans.

Read the scan's resolved file list, keep each file's declarations without their
bodies, resolve imports between the listed files, and count each file's commits
that are reachable from the history ref and dated within the last twelve months
(``git log --since``, measured from now, the same window as the scan's
``CHANGE_COUNTS``). Write three files into the output directory and print one
JSON document with import cycles and ranked dependency-direction leads.

Cycles and direction leads are leads only: a scan still confirms each in the code
before reporting a finding.

Languages: TypeScript and JavaScript (regular expressions; top-level declarations
only) and Python (``ast``; classes and functions, including class members).
Files in other languages, including C#, Go, and Java, are skipped and counted.
Relative imports resolve only by path. Other imports resolve by exact
repository-relative module path, then by a unique path-suffix match of two or
more segments within the listed files, after a leading ``@/`` or ``~/`` is
dropped; a JavaScript specifier with one segment is a package and never resolves.
Package aliases from build configuration are not read.

Usage: code-outline.py --files LIST --out DIR [--root DIR] [--history-ref REF]
LIST is a file with one path per line, relative to --root; entries outside --root
count as missing.
Exit codes: 0 success (including an empty result), 1 input or output failure,
2 usage error.
"""

from __future__ import annotations

import argparse
import ast
import bisect
import json
import posixpath
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = "trackbed-code-outline/v1"
MAX_CYCLES = 20
MAX_CYCLE_FILES = 20
HISTORY_WINDOW = "12 months ago"
MAX_LEADS = 20
# A lead needs a widely imported stable side and a much more often changed volatile side.
MIN_STABLE_IMPORTERS = 5
MIN_VOLATILE_COMMITS = 10
MIN_CHURN_RATIO = 3
MAX_SIGNATURE = 160

JS_EXTENSIONS = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
PY_EXTENSIONS = (".py",)
# Imports of these files are not code and stay out of the resolution counts.
ASSET_EXTENSIONS = {".css", ".scss", ".sass", ".less", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".json", ".html"}

JS_DECLARATION = re.compile(
    r"^(?:export\s+(?:default\s+)?)?(?:declare\s+)?(?:abstract\s+)?(?:async\s+)?"
    r"(?:function\b|class\b|interface\b|type\b|enum\b|const\b|let\b|var\b|namespace\b)"
    r"|^export\b|^module\.exports\b"
)
JS_IMPORT = re.compile(r"""(?:\bfrom\s*|\bimport\s*(?:\(\s*)?|\brequire\s*\(\s*)(['"])([^'"\n]+)\1""")
TEST_SEGMENTS = {"test", "tests", "__tests__", "spec", "specs", "fixtures", "__fixtures__", "__mocks__", "testdata"}
TEST_NAME = re.compile(r"(^test_.*\.py$|_test\.py$|^conftest\.py$|\.(test|spec)\.[A-Za-z0-9]+$)")


class OutlineError(Exception):
    """An input or output failure the caller should report."""


@dataclass
class Declaration:
    line: int
    depth: int
    signature: str


@dataclass
class Import:
    """One import statement.

    Each group holds the module key for one imported name; ``fallback`` applies only
    when no group resolves.
    """

    kind: str  # "relative" or "absolute"
    line: int
    groups: list[list[str]]
    fallback: list[str] = field(default_factory=list)


@dataclass
class SourceFile:
    path: str
    language: str
    lines: int
    declarations: list[Declaration] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    parse_error: bool = False


def language_of(path: str) -> str | None:
    if path.endswith(PY_EXTENSIONS):
        return "python"
    if path.endswith(JS_EXTENSIONS):
        return "javascript"
    return None


def is_test_path(path: str) -> bool:
    parts = path.split("/")
    return any(part in TEST_SEGMENTS for part in parts[:-1]) or bool(TEST_NAME.search(parts[-1]))


def folder_of(path: str) -> str:
    return posixpath.dirname(path) or "."


def clip(signature: str) -> str:
    signature = " ".join(signature.split())
    if signature.endswith("{"):
        signature = signature[:-1].rstrip()
    return signature if len(signature) <= MAX_SIGNATURE else signature[: MAX_SIGNATURE - 3] + "..."


# --- JavaScript and TypeScript -------------------------------------------------


def js_import(importer: str, specifier: str, line: int) -> Import | None:
    """Map a specifier to module keys: "./a.js" may name a.ts, "./app.component" names app.component.ts."""
    ext = posixpath.splitext(specifier)[1]
    if ext in ASSET_EXTENSIONS:
        return None
    if specifier.startswith("."):
        base = posixpath.normpath(posixpath.join(posixpath.dirname(importer), specifier))
        if base.startswith(".."):
            return Import("relative", line, [])
        keys = [base[: -len(ext)]] if ext in JS_EXTENSIONS else [base]
        return Import("relative", line, [keys])
    segments = [segment for segment in specifier.split("/") if segment]
    if segments and segments[0] in ("@", "~"):
        segments = segments[1:]
    # A one-segment specifier such as "react" or "@/utils" is a package and never resolves to a local file.
    if len(segments) < 2:
        return Import("absolute", line, [])
    key = "/".join(segments)
    return Import("absolute", line, [[key[: -len(ext)] if ext in JS_EXTENSIONS else key]])


def parse_javascript(source: SourceFile, text: str) -> None:
    for number, line in enumerate(text.splitlines(), start=1):
        if JS_DECLARATION.match(line):
            source.declarations.append(Declaration(number, 0, clip(line)))
    line_starts = [0, *(newline.end() for newline in re.finditer("\n", text))]
    for match in JS_IMPORT.finditer(text):
        found = js_import(source.path, match.group(2), bisect.bisect_right(line_starts, match.start()))
        if found is not None:
            source.imports.append(found)


# --- Python --------------------------------------------------------------------


def python_signature(node: ast.AST) -> str | None:
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(ast.unparse(base) for base in node.bases)
        return f"class {node.name}({bases})" if bases else f"class {node.name}"
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        returns = f" -> {ast.unparse(node.returns)}" if node.returns is not None else ""
        return f"{prefix} {node.name}({ast.unparse(node.args)}){returns}"
    return None


def collect_python_declarations(body: list[ast.stmt], depth: int, out: list[Declaration]) -> None:
    for node in body:
        signature = python_signature(node)
        if signature is None:
            continue
        out.append(Declaration(node.lineno, depth, clip(signature)))
        if isinstance(node, ast.ClassDef):
            collect_python_declarations(node.body, depth + 1, out)


def python_imports(importer: str, node: ast.Import | ast.ImportFrom) -> list[Import]:
    if isinstance(node, ast.Import):
        return [Import("absolute", node.lineno, [[alias.name.replace(".", "/")]]) for alias in node.names]
    module = (node.module or "").replace(".", "/")
    names = [alias.name for alias in node.names if alias.name != "*"]
    if node.level == 0:
        # "from a.b import c" names either the submodule a/b/c or a member of a/b.
        return [Import("absolute", node.lineno, [[f"{module}/{name}"] for name in names], [module])]
    base = posixpath.dirname(importer)
    for _ in range(node.level - 1):
        if not base:
            return [Import("relative", node.lineno, [])]
        base = posixpath.dirname(base)
    package = posixpath.normpath(posixpath.join(base, module)) if base or module else "."
    groups = [[posixpath.normpath(posixpath.join(package, name))] for name in names]
    return [Import("relative", node.lineno, groups, [package])]


def parse_python(source: SourceFile, text: str) -> None:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        source.parse_error = True
        return
    collect_python_declarations(tree.body, 0, source.declarations)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            source.imports.extend(python_imports(source.path, node))


# --- Resolution ----------------------------------------------------------------


def module_keys(path: str, language: str) -> list[str]:
    stem = posixpath.splitext(path)[0]
    name = posixpath.basename(stem)
    package_marker = "__init__" if language == "python" else "index"
    keys = [stem]
    if name == package_marker:
        keys.append(posixpath.dirname(stem) or ".")
    return keys


class Resolver:
    """Resolve module keys to listed files: exact key first, then a unique path suffix."""

    def __init__(self, sources: list[SourceFile]) -> None:
        self.exact: dict[tuple[str, str], set[str]] = defaultdict(set)
        self.suffix: dict[tuple[str, str], set[str]] = defaultdict(set)
        for source in sources:
            for key in module_keys(source.path, source.language):
                self.exact[(source.language, key)].add(source.path)
                segments = key.split("/")
                for start in range(len(segments)):
                    self.suffix[(source.language, "/".join(segments[start:]))].add(source.path)

    def targets(self, language: str, statement: Import) -> set[str]:
        found = {target for group in statement.groups if (target := self.resolve(language, statement.kind, group))}
        if not found and statement.fallback:
            target = self.resolve(language, statement.kind, statement.fallback)
            found = {target} if target else set()
        return found

    def resolve(self, language: str, kind: str, keys: list[str]) -> str | None:
        for key in keys:
            # Sorting puts a module file ("a.ts") before a folder index ("a/index.ts") of the same name.
            matches = sorted(self.exact.get((language, key), ()))
            if matches:
                return matches[0]
        if kind == "relative":
            return None
        for key in keys:
            # A single name such as "logging" or "celery" is a package, never a local file by suffix.
            if "/" not in key:
                continue
            candidates = self.suffix.get((language, key), set())
            if len(candidates) == 1:
                return next(iter(candidates))
        return None


# --- History -------------------------------------------------------------------


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # Unquoted paths, so non-ASCII file names match the listed paths.
    return subprocess.run(
        ["git", "-c", "core.quotePath=false", "-C", str(root), *args],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="surrogateescape",
    )


def commit_history(root: Path, ref: str, paths: set[str]) -> dict[str, Any]:
    """Count each listed file's commits; unavailable or shallow history is unknown, never zero."""
    history: dict[str, Any] = {"ref": ref, "since": HISTORY_WINDOW, "status": "unavailable", "commit": None}
    if not paths:
        history["reason"] = "no readable file in a supported language"
        return history
    history["convention"] = "commits whose diff names the file; the initial commit counts, merge commits name no files"
    resolved = git(root, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}")
    if resolved.returncode != 0:
        history["reason"] = "not a git repository or the history ref does not resolve"
        return history
    history["commit"] = resolved.stdout.strip()
    if git(root, "rev-parse", "--is-shallow-repository").stdout.strip() == "true":
        history["status"] = "shallow"
        history["reason"] = "shallow clone; commit counts are unknown"
        return history
    prefix = git(root, "rev-parse", "--show-prefix").stdout.strip()
    log = git(root, "log", f"--since={HISTORY_WINDOW}", "--format=>>> %H", "--name-only", "--end-of-options", ref, "--")
    if log.returncode != 0:
        history["reason"] = log.stderr.strip() or "git log failed"
        return history
    commits: dict[str, set[str]] = {path: set() for path in paths}
    current = ""
    for line in log.stdout.splitlines():
        if line.startswith(">>> "):
            current = line[4:]
        elif line and line.startswith(prefix):
            path = line[len(prefix) :]
            if path in commits:
                commits[path].add(current)
    history["status"] = "ok"
    history["commits"] = commits
    return history


# --- Graph ---------------------------------------------------------------------


def strongly_connected(nodes: list[str], edges: dict[str, set[str]]) -> list[list[str]]:
    """Tarjan's algorithm without recursion; returns components with two or more files."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[list[str]] = []
    counter = 0
    for start in nodes:
        if start in index:
            continue
        work: list[tuple[str, list[str]]] = [(start, sorted(edges.get(start, ())))]
        index[start] = low[start] = counter
        counter += 1
        stack.append(start)
        on_stack.add(start)
        while work:
            node, pending = work[-1]
            if pending:
                target = pending.pop(0)
                if target not in index:
                    index[target] = low[target] = counter
                    counter += 1
                    stack.append(target)
                    on_stack.add(target)
                    work.append((target, sorted(edges.get(target, ()))))
                elif target in on_stack:
                    low[node] = min(low[node], index[target])
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    components.append(sorted(component))
    return components


def direction_leads(
    edges: dict[str, dict[str, int]], importers: dict[str, set[str]], commits: dict[str, set[str]]
) -> list[dict[str, Any]]:
    """Rank imports from a widely imported non-test file to a much more often changed one.

    The stable side needs MIN_STABLE_IMPORTERS importers; the volatile side needs
    MIN_VOLATILE_COMMITS commits and MIN_CHURN_RATIO times the stable side's. Leads are
    ordered by importer count, then by churn gap.
    """
    leads: list[dict[str, Any]] = []
    for stable, targets in edges.items():
        if is_test_path(stable) or len(importers[stable]) < MIN_STABLE_IMPORTERS:
            continue
        stable_commits = len(commits[stable])
        for volatile, line in targets.items():
            volatile_commits = len(commits[volatile])
            if volatile_commits >= MIN_VOLATILE_COMMITS and volatile_commits >= MIN_CHURN_RATIO * stable_commits:
                leads.append(
                    {
                        "stable": stable,
                        "stable_importers": len(importers[stable]),
                        "stable_commits": stable_commits,
                        "volatile": volatile,
                        "volatile_commits": volatile_commits,
                        "import_line": line,
                    }
                )
    leads.sort(
        key=lambda lead: (
            -lead["stable_importers"],
            lead["stable_commits"] - lead["volatile_commits"],
            lead["stable"],
            lead["volatile"],
        )
    )
    return leads


# --- Output --------------------------------------------------------------------


def write_outline(path: Path, by_folder: dict[str, list[SourceFile]]) -> dict[str, tuple[int, int]]:
    """Write folder sections in path order and return each folder's line range."""
    lines = [
        "# Code outline",
        "",
        "Declarations only; bodies are dropped. Each declaration line, indented by nesting, starts with its",
        "source line number.",
    ]
    ranges: dict[str, tuple[int, int]] = {}
    for folder in sorted(by_folder):
        lines.append("")
        start = len(lines) + 1
        lines.append(f"## {folder}")
        for source in by_folder[folder]:
            note = ", could not parse" if source.parse_error else ""
            lines.append(f"### {source.path} ({source.lines} lines{note})")
            lines.extend(f"{'  ' * item.depth}{item.line}: {item.signature}" for item in source.declarations)
        ranges[folder] = (start, len(lines))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ranges


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    out = Path(args.out)
    try:
        listed = Path(args.files).read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise OutlineError(f"cannot read the file list: {error}") from error

    sources: list[SourceFile] = []
    listed_count = skipped = missing = 0
    seen: set[str] = set()
    for entry in listed:
        entry = entry.strip()
        if not entry:
            continue
        listed_count += 1
        candidate = root / entry
        try:
            relative = candidate.resolve().relative_to(root).as_posix()
        except ValueError:
            missing += 1
            continue
        if relative in seen:
            continue
        seen.add(relative)
        language = language_of(relative)
        if language is None:
            skipped += 1
            continue
        try:
            text = (root / relative).read_text(encoding="utf-8", errors="replace")
        except OSError:
            missing += 1
            continue
        source = SourceFile(relative, language, text.count("\n") + (0 if text.endswith("\n") or not text else 1))
        (parse_python if language == "python" else parse_javascript)(source, text)
        sources.append(source)
    sources.sort(key=lambda source: source.path)

    resolver = Resolver(sources)
    edges: dict[str, dict[str, int]] = defaultdict(dict)
    stats = {"statements": 0, "resolved": 0, "relative": 0, "relative_resolved": 0}
    for source in sources:
        for statement in source.imports:
            resolved = resolver.targets(source.language, statement) - {source.path}
            is_relative = statement.kind == "relative"
            stats["statements"] += 1
            stats["relative"] += is_relative
            if not resolved:
                continue
            stats["resolved"] += 1
            stats["relative_resolved"] += is_relative
            for target in resolved:
                edges[source.path].setdefault(target, statement.line)
    importers: dict[str, set[str]] = defaultdict(set)
    for importer, imported in edges.items():
        for target in imported:
            importers[target].add(importer)

    paths = {source.path for source in sources}
    history = commit_history(root, args.history_ref, paths)
    commits: dict[str, set[str]] | None = history.pop("commits", None)

    by_folder: dict[str, list[SourceFile]] = defaultdict(list)
    for source in sources:
        by_folder[folder_of(source.path)].append(source)
    try:
        out.mkdir(parents=True, exist_ok=True)
        outline_path = out / "outline.md"
        ranges = write_outline(outline_path, by_folder)
        folders_path = out / "folders.tsv"
        folder_rows = ["folder\tfiles\tlines\timporters\timports\tcommits\toutline_lines"]
        for folder in sorted(by_folder):
            members = {source.path for source in by_folder[folder]}
            inbound = {i for path in members for i in importers[path] if folder_of(i) != folder}
            outbound = {t for path in members for t in edges.get(path, {}) if folder_of(t) != folder}
            folder_commits = (
                str(len({commit for path in members for commit in commits[path]})) if commits is not None else "unknown"
            )
            start, end = ranges[folder]
            folder_rows.append(
                f"{folder}\t{len(members)}\t{sum(source.lines for source in by_folder[folder])}\t"
                f"{len(inbound)}\t{len(outbound)}\t{folder_commits}\t{start}-{end}"
            )
        folders_path.write_text("\n".join(folder_rows) + "\n", encoding="utf-8")
        imports_path = out / "imports.tsv"
        rate = f"{round(100 * stats['relative_resolved'] / stats['relative'])}%" if stats["relative"] else "n/a"
        edge_rows = [
            f"# resolved {stats['relative_resolved']} of {stats['relative']} relative imports ({rate}); "
            f"{stats['resolved']} of {stats['statements']} import statements resolved to a listed file",
            "importer\timported\tline",
            *(
                f"{importer}\t{target}\t{line}"
                for importer in sorted(edges)
                for target, line in sorted(edges[importer].items())
            ),
        ]
        imports_path.write_text("\n".join(edge_rows) + "\n", encoding="utf-8")
    except OSError as error:
        raise OutlineError(f"cannot write to the output directory: {error}") from error

    edge_sets = {importer: set(targets) for importer, targets in edges.items()}
    cycles = sorted(strongly_connected(sorted(paths), edge_sets), key=lambda members: (-len(members), members))
    leads = direction_leads(edges, importers, commits) if commits is not None else []
    return {
        "schema": SCHEMA,
        "status": "ok",
        "files": {
            "listed": listed_count,
            "read": len(sources),
            "skipped_unsupported": skipped,
            "missing": missing,
            "parse_errors": sum(source.parse_error for source in sources),
        },
        "outputs": {"outline": str(outline_path), "folders": str(folders_path), "imports": str(imports_path)},
        "outline_tokens": outline_path.stat().st_size // 4,
        "imports": stats,
        "history": history,
        "cycles": [{"size": len(members), "files": members[:MAX_CYCLE_FILES]} for members in cycles[:MAX_CYCLES]],
        "cycles_total": len(cycles),
        "direction_leads": leads[:MAX_LEADS],
        "direction_leads_total": len(leads),
        "note": "Cycles and leads are leads only; confirm each in the code before reporting a finding.",
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Outline and import graph for refactor scans.")
    parser.add_argument("--files", required=True, help="file with one path per line")
    parser.add_argument("--out", required=True, help="output directory; nothing is written outside it")
    parser.add_argument("--root", default=".", help="repository root the listed paths are relative to")
    parser.add_argument("--history-ref", default="HEAD", help="ref whose last twelve months of commits are counted")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = run(args)
    except OutlineError as error:
        print(json.dumps({"schema": SCHEMA, "status": "error", "message": str(error)}))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
