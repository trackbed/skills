#!/usr/bin/env python3
"""Collect and check the coverage reports used by the Makefile."""

from __future__ import annotations

import argparse
import json
import os
import pickle
import re
import subprocess
import sys
import sysconfig
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Sources:
    measured: list[str]
    contracts: dict[str, list[str]]
    excluded: dict[str, str]
    floors: dict[str, float]

    @property
    def registered(self) -> set[str]:
        return set(self.measured) | self.contracts.keys() | self.excluded.keys()


def nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(map(nonempty_string, value))


def load_inventory(path: Path, stale_threshold: float) -> dict[str, Sources]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("expected an inventory object")

    inventory = {}
    for name in ("javascript", "python", "shell"):
        language = data.get(name)
        if not isinstance(language, dict):
            raise ValueError(f"expected a {name} inventory object")
        measured = language.get("measured") if name != "shell" else []
        contracts = language.get("contract_only")
        excluded = language.get("excluded", {}) if name == "javascript" else {}
        floors = language.get("measured_floors", {}) if name == "python" else {}
        if excluded is None or excluded is False:
            # The previous inventory check treated null and false as absent.
            excluded = {}

        if not isinstance(measured, list) or (name != "shell" and not string_list(measured)):
            raise ValueError(f"invalid {name} measured sources")
        if not isinstance(contracts, dict) or not all(
            nonempty_string(source) and string_list(suites) for source, suites in contracts.items()
        ):
            raise ValueError(f"invalid {name} contract mappings")
        if not isinstance(excluded, dict) or not all(
            nonempty_string(source) and nonempty_string(reason) for source, reason in excluded.items()
        ):
            raise ValueError(f"invalid {name} exclusions")
        if not isinstance(floors, dict) or not all(
            source in measured and type(floor) in (float, int) and 0 <= floor < stale_threshold
            for source, floor in floors.items()
        ):
            raise ValueError(f"invalid {name} measured floors")

        sources = Sources(measured, contracts, excluded, floors)
        if len(sources.registered) != len(measured) + len(contracts) + len(excluded):
            raise ValueError(f"duplicate {name} production sources")
        inventory[name] = sources

    return inventory


def report_paths(label: str, paths: Iterable[str]) -> bool:
    entries = list(paths)
    if not entries:
        return False
    sample = ", ".join(entries[:10])
    if len(entries) > 10:
        sample += f", ... (+{len(entries) - 10} more)"
    print(f"{label} ({len(entries)}): {sample}", file=sys.stderr)
    return True


def normalize_path(value: str, root: Path, plugin: str, *, trace: bool = False) -> str:
    path = value.strip().replace("\\", "/").removeprefix("./")
    if path.startswith(f"{root}/"):
        return path[len(str(root)) + 1 :]
    path = path.removeprefix("../") if path.startswith("../.agents/") else path
    for prefix in (".agents/", f"{plugin}/"):
        if path.startswith(prefix):
            return path
        if trace and f"/{prefix}" in path:
            return prefix + path.rsplit(f"/{prefix}", 1)[1]
    return path if path.startswith("/") else f"{plugin}/{path}"


def in_tests_directory(path: str) -> bool:
    return "/tests/" in f"/{path}"


def python_test_path(path: str) -> bool:
    filename = path.rsplit("/", 1)[-1]
    return in_tests_directory(path) or filename.startswith("test_") or filename == "__init__.py"


def discover_sources(root: Path, plugin: str, extension: str) -> set[str]:
    directories = [f"{plugin}/{name}" for name in ("evals", "hooks", "scripts", "skills")]
    directories.append(".agents/skills")
    if extension == "js":
        directories.append(f"{plugin}/shared")
    sources = set()
    for directory in directories:
        source_root = root / directory
        if source_root.is_symlink():
            continue
        for parent, _, files in os.walk(source_root):
            for filename in files:
                candidate = Path(parent) / filename
                relative = candidate.relative_to(root).as_posix()
                if not filename.endswith(f".{extension}") or candidate.is_symlink():
                    continue
                sections = relative[len(directory) + 1 :].split("/")[:-1]
                if directory in (f"{plugin}/skills", ".agents/skills"):
                    allowed: tuple[str, ...] = ("scripts",)
                    if directory == f"{plugin}/skills" and extension in ("js", "sh"):
                        allowed = ("scripts", "assets")
                    if not any(section in allowed for section in sections):
                        continue
                if directory == f"{plugin}/shared" and "assets" not in sections:
                    continue
                if extension == "py" and (filename.startswith("test_") or filename == "__init__.py"):
                    continue
                sources.add(relative)
    return sources


def compare_sources(label: str, discovered: set[str], registered: set[str], inventory: str) -> bool:
    missing = report_paths(f"{label} production files missing {inventory} entries", sorted(discovered - registered))
    stale = report_paths(f"{label} {inventory} entries missing production files", sorted(registered - discovered))
    return not (missing or stale)


def check_python_inventory(root: Path, plugin: str, sources: Sources, list_paths: bool) -> bool:
    registered = sources.registered
    if not compare_sources("Python", discover_sources(root, plugin, "py"), registered, "static inventory"):
        return False
    noun = "file" if len(registered) == 1 else "files"
    if list_paths:
        print(*sorted(registered), sep="\n")
    print(
        f"Python static inventory: {len(registered)} production {noun} registered.",
        file=sys.stderr if list_paths else sys.stdout,
    )
    return True


def check_bats_contracts(root: Path, plugin: str, inventory: dict[str, Sources]) -> bool:
    if not check_python_inventory(root, plugin, inventory["python"], list_paths=False):
        return False
    valid = True
    for language, label, extension in (("javascript", "JavaScript", "js"), ("shell", "Shell", "sh")):
        if not compare_sources(
            label, discover_sources(root, plugin, extension), inventory[language].registered, "inventory"
        ):
            valid = False

    suites = {
        path.relative_to(root).as_posix(): sum(
            line.startswith("@test ") for line in path.read_text(encoding="utf-8").splitlines()
        )
        for path in (root / plugin / "tests").glob("*.bats")
        if not path.name.startswith(".") and path.is_file()
    }
    for sources in inventory.values():
        for source, contracts in sources.contracts.items():
            for contract in contracts:
                if not (root / source).is_file():
                    print(f"Production contract source not found: {source}", file=sys.stderr)
                    valid = False
                if not (root / contract).is_file():
                    print(f"Production contract file not found: {contract}", file=sys.stderr)
                elif contract not in suites:
                    print(
                        f"Production contract is not discovered by tests/run-tests.sh: {contract}",
                        file=sys.stderr,
                    )
                elif not suites[contract]:
                    print(f"Production contract has no Bats tests: {contract}", file=sys.stderr)
                else:
                    continue
                valid = False

    if not valid:
        return False
    test_count = sum(suites.values())
    if not test_count:
        print("Bats contract inventory is empty", file=sys.stderr)
        return False
    shell_count = len(inventory["shell"].contracts)
    noun = "file" if shell_count == 1 else "files"
    print(
        f"Shell source-to-contract inventory proxy: {shell_count} production {noun} mapped to "
        "Bats contracts (not measured execution coverage)."
    )
    print(
        f"Bats contract inventory: {len(suites)} files, {test_count} tests "
        "(all top-level tests/*.bats are discovered by tests/run-tests.sh)."
    )
    return True


LCOV_COUNTERS = (("lines", "LF", "LH"), ("branches", "BRF", "BRH"), ("functions", "FNF", "FNH"))
LCOV_KEYS = {key for _, total, hit in LCOV_COUNTERS for key in (total, hit)}


def check_node_lcov(
    report: str, root: Path, plugin: str, sources: Sources, minimums: tuple[float, float, float]
) -> bool:
    measured = set(sources.measured)
    registered = measured | sources.contracts.keys()
    totals = dict.fromkeys(LCOV_KEYS, 0)
    seen: dict[str, None] = {}
    path = None
    counters: dict[str, int] = {}
    malformed = False
    for line in report.splitlines():
        if line.startswith("SF:"):
            if path is not None or not line[3:].strip():
                malformed = True
            path = normalize_path(line[3:], root, plugin)
        elif line == "end_of_record":
            if path is None:
                malformed = True
            elif not in_tests_directory(path):
                if (
                    path in seen
                    or counters.keys() != LCOV_KEYS
                    or any(counters[hit] > counters[total] for _, total, hit in LCOV_COUNTERS)
                ):
                    malformed = True
                elif path in measured:
                    if not counters["LF"]:
                        malformed = True
                    for key, count in counters.items():
                        totals[key] += count
                seen[path] = None
            path = None
            counters.clear()
        else:
            key, separator, value = line.partition(":")
            if separator and key in LCOV_KEYS:
                if path is None or key in counters or not re.fullmatch(r"[0-9]+", value):
                    malformed = True
                else:
                    counters[key] = int(value)

    missing = report_paths("Node coverage missing inventory files", (p for p in sources.measured if p not in seen))
    unexpected = report_paths(
        "Node coverage report has unregistered production files", (p for p in seen if p not in registered)
    )
    malformed = malformed or path is not None
    if malformed:
        print("Node LCOV coverage report is malformed", file=sys.stderr)

    percentages = []
    summaries = []
    for label, total, hit in LCOV_COUNTERS:
        percent = 100 * totals[hit] / totals[total] if totals[total] else 100.0
        percentages.append(percent)
        summaries.append(f"{label} {percent:.2f}% ({totals[hit]}/{totals[total]})")
    print("Node production coverage: " + ", ".join(summaries))
    below = any(percent < minimum for percent, minimum in zip(percentages, minimums, strict=True))
    if below:
        details = ", ".join(
            f"{label} {percent:.2f}/{minimum:.2f}"
            for (label, _, _), percent, minimum in zip(LCOV_COUNTERS, percentages, minimums, strict=True)
        )
        print(f"Node coverage below baseline: {details}", file=sys.stderr)
    return not (missing or unexpected or malformed or below)


TRACE_ROW = re.compile(r"^\s*([0-9]+)\s+([0-9]+(?:\.[0-9]+)?)%\s+[^\(]*\((.*\.py)\)\s*$")


def format_floor(floor: float) -> str:
    return str(int(floor)) if floor == int(floor) else f"{floor:.2f}"


def check_python_trace(
    report: str,
    root: Path,
    plugin: str,
    sources: Sources,
    minimum: float,
    file_minimum: float,
    stale_margin: float,
) -> bool:
    registered = sources.registered
    measured = set(sources.measured)
    seen: dict[str, None] = {}
    percentages: dict[str, float] = {}
    lines = 0
    weighted = 0.0
    for line in report.splitlines():
        match = TRACE_ROW.match(line)
        if not match:
            continue
        count, percentage, filename = match.groups()
        path = normalize_path(filename, root, plugin, trace=True)
        if path.startswith("/") or python_test_path(path):
            continue
        seen[path] = None
        if path in measured:
            percentages[path] = float(percentage)
            lines += int(count)
            weighted += int(count) * float(percentage)

    missing = report_paths("Python coverage missing inventory files", (p for p in sources.measured if p not in seen))
    unexpected = report_paths(
        "Python coverage report has unregistered production files", (p for p in seen if p not in registered)
    )
    below_paths = []
    stale_paths = []
    for path in sources.measured:
        if path not in percentages:
            continue
        percent = percentages[path]
        floor = sources.floors.get(path, file_minimum)
        if percent < floor:
            below_paths.append(f"{path} ({percent:.2f}% < {format_floor(floor)}%)")
        elif path in sources.floors and percent >= file_minimum + stale_margin:
            stale_paths.append(f"{path} ({percent:.2f}%)")
    below = report_paths(
        "Python files below the per-file coverage floor; add tests or seed python.measured_floors", below_paths
    )
    stale = report_paths("Python per-file floors are obsolete; delete them from python.measured_floors", stale_paths)
    if percentages:
        lowest = sorted(percentages.items(), key=lambda item: (item[1], item[0]))[:10]
        print(
            f"Python per-file coverage ({len(lowest)} lowest of {len(percentages)} measured files, "
            f"floor {format_floor(file_minimum)}%):"
        )
        for path, percent in lowest:
            displayed_floor = format_floor(sources.floors.get(path, file_minimum))
            print(f"  {percent:6.2f}% (floor {displayed_floor}%) {path}")

    if not lines:
        print("Python production coverage summary not found", file=sys.stderr)
        return False
    coverage = weighted / lines
    print(f"Python production aggregate: {coverage:.2f}% ({lines} executable lines)")
    if coverage < minimum:
        print(f"Python coverage below baseline: {coverage:.2f}/{minimum:.2f}", file=sys.stderr)
        return False
    return not (missing or unexpected or below or stale)


def collect_node_report(directory: Path, test_files: list[str]) -> str:
    output = directory / "node-tests.txt"
    lcov = directory / "node-coverage.lcov"
    command = [
        "node",
        "--test",
        "--experimental-test-coverage",
        "--test-reporter=spec",
        "--test-reporter=lcov",
        f"--test-reporter-destination={output}",
        f"--test-reporter-destination={lcov}",
    ]
    result = subprocess.run([*command, *test_files], check=False)
    if output.exists():
        print(output.read_text(encoding="utf-8"), end="")
    result.check_returncode()
    return lcov.read_text(encoding="utf-8")


def collect_python_report(directory: Path, test_dir: str, maintenance_dir: str, pattern: str) -> str:
    counts = directory / "counts"
    counts.write_bytes(pickle.dumps(({}, {}, {}), protocol=1))
    stdlib = {sysconfig.get_path(name) for name in ("stdlib", "platstdlib")}
    # Homebrew can report symlinked stdlib paths in sysconfig and resolved paths in trace.
    ignore = os.pathsep.join(sorted(stdlib | {os.path.realpath(path) for path in stdlib}))
    command = [
        sys.executable,
        "-m",
        "trace",
        "--count",
        "--file",
        str(counts),
        "--coverdir",
        str(directory / "report-files"),
        "--ignore-dir",
        ignore,
    ]
    discovery = ["--module", "unittest", "discover", "-p", pattern, "-s"]
    subprocess.run([*command, *discovery, test_dir], check=True)
    result = subprocess.run(
        [*command, "--missing", "--summary", *discovery, maintenance_dir],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        check=False,
    )
    print(result.stdout, end="")
    result.check_returncode()
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--file-minimum", type=float, required=True)
    parser.add_argument("--stale-margin", type=float, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inventory").add_argument("--list", action="store_true")
    commands.add_parser("bats-contracts")
    node = commands.add_parser("node-lcov")
    node.add_argument("--minimums", type=float, nargs=3, required=True)
    node.add_argument("test_files", nargs="+")
    python = commands.add_parser("python-trace")
    python.add_argument("--minimum", type=float, required=True)
    python.add_argument("--test-dir", required=True)
    python.add_argument("--maintenance-dir", required=True)
    python.add_argument("--test-pattern", required=True)
    args = parser.parse_args()

    try:
        inventory = load_inventory(args.inventory, args.file_minimum + args.stale_margin)
    except (OSError, ValueError) as error:
        print(f"Production coverage inventory is malformed: {args.inventory}: {error}", file=sys.stderr)
        return 1
    if args.command == "inventory":
        return int(not check_python_inventory(args.root, args.plugin, inventory["python"], args.list))
    if args.command == "bats-contracts":
        return int(not check_bats_contracts(args.root, args.plugin, inventory))

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            if args.command == "node-lcov":
                report = collect_node_report(directory, args.test_files)
                return int(not check_node_lcov(report, args.root, args.plugin, inventory["javascript"], args.minimums))
            report = collect_python_report(directory, args.test_dir, args.maintenance_dir, args.test_pattern)
            return int(
                not check_python_trace(
                    report,
                    args.root,
                    args.plugin,
                    inventory["python"],
                    args.minimum,
                    args.file_minimum,
                    args.stale_margin,
                )
            )
    except subprocess.CalledProcessError as error:
        return error.returncode if error.returncode > 0 else 128 - error.returncode
    except (OSError, ValueError) as error:
        print(f"Could not read coverage results: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
