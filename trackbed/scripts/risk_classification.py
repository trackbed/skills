"""Shared path classification and trusted-revision policy for risk and stack reviews.

Consumers use these functions rather than importing the risk-signals command or
its pattern tables. Classifiers accept repository-relative paths.
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import PurePosixPath

import risk_patterns as patterns

POLICY_PATH = ".github/pr-risk.json"
POLICY_LIST_KEYS = ("high_risk_paths", "medium_risk_paths", "generated_paths")

WORD_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=[0-9])")
WORD_RE = re.compile(r"[a-z0-9]+")


class TriageError(Exception):
    """Git or input state prevented a trustworthy signal report."""


@dataclass
class Policy:
    rev: str
    status: str = "absent"
    error: str | None = None
    high: tuple[str, ...] = ()
    medium: tuple[str, ...] = ()
    generated: tuple[str, ...] = ()


def git(root: str | None, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip() or f"exit {result.returncode}"
        raise TriageError(f"git {args[0]} failed: {detail}")
    return result.stdout


def path_words(path: str) -> set[str]:
    """Lowercase words of a path, both as written and split at camelCase and digit boundaries."""
    split = WORD_BOUNDARY_RE.sub(" ", path)
    return set(WORD_RE.findall(path.lower())) | set(WORD_RE.findall(split.lower()))


def matches_any(path: str, globs: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, glob + "*" if glob.endswith("/") else glob) for glob in globs)


def is_ci_path(path: str) -> bool:
    return path.startswith(patterns.CI_PREFIXES) or PurePosixPath(path).name in patterns.CI_NAMES


def is_manifest(name: str) -> bool:
    suffix = PurePosixPath(name).suffix.lower()
    return (
        name in patterns.MANIFESTS or suffix in patterns.MANIFEST_SUFFIXES or bool(patterns.REQUIREMENTS_RE.match(name))
    )


def classify_kind(path: str, policy: Policy) -> str:
    pure = PurePosixPath(path)
    name = pure.name
    lower = name.lower()
    dirs = {part.lower() for part in pure.parts[:-1]}
    if name in patterns.LOCKFILES:
        return "lockfile"
    # CI definitions run with repository secrets, so a test-like name or a policy glob cannot demote them.
    if is_ci_path(path):
        return "code"
    # Only the repository policy marks files generated; generated-looking names are author-chosen.
    if matches_any(path, policy.generated):
        return "generated"
    if is_manifest(name):
        return "code"
    if pure.suffix.lower() in patterns.DOCS_SUFFIXES or name in patterns.DOCS_NAMES:
        return "docs"
    if dirs & patterns.TEST_DIRS or patterns.TEST_FILE_RE.search(lower) or patterns.TEST_CLASS_FILE_RE.search(name):
        return "test"
    return "code"


def code_path_signals(path: str) -> list[str]:
    """Built-in path categories that apply to code-kind files."""
    pure = PurePosixPath(path)
    name = pure.name
    lower = name.lower()
    suffix = pure.suffix.lower()
    words = path_words(path)
    found = []
    if words & patterns.AUTH_WORDS:
        found.append("path:auth")
    is_env_file = lower == ".env" or (lower.startswith(".env.") and not lower.endswith(patterns.ENV_EXAMPLE_SUFFIXES))
    if is_env_file or lower in patterns.SECRET_FILE_NAMES or suffix in patterns.SECRET_FILE_SUFFIXES:
        found.append("path:secrets-config")
    if words & patterns.DATABASE_WORDS or suffix == ".sql" or lower in patterns.DATABASE_NAMES:
        found.append("path:database")
    if is_ci_path(path):
        found.append("path:ci")
    is_dockerfile = lower == "dockerfile" or lower.startswith("dockerfile.") or lower.endswith(".dockerfile")
    if (
        words & patterns.INFRA_WORDS
        or suffix in patterns.INFRA_SUFFIXES
        or lower in patterns.INFRA_NAMES
        or is_dockerfile
    ):
        found.append("path:infra")
    is_openapi = lower.startswith(("openapi", "swagger")) and suffix in (".json", ".yaml", ".yml")
    if suffix in patterns.API_CONTRACT_SUFFIXES or is_openapi:
        found.append("path:api-contract")
    if lower in patterns.PUBLIC_INTERFACE_NAMES or patterns.PUBLIC_INTERFACE_RE.match(lower):
        found.append("path:public-interface")
    return found


def load_policy(root: str, rev: str) -> Policy:
    policy = Policy(rev=rev)
    listing = git(root, "ls-tree", "-z", "--full-tree", rev, "--", POLICY_PATH)
    if not listing:
        return policy

    def invalid(message: str) -> Policy:
        policy.status = "invalid"
        policy.error = message
        return policy

    meta = listing.split(b"\0", 1)[0].decode("utf-8", "replace").partition("\t")[0].split(" ")
    if len(meta) != 3 or meta[1] != "blob" or meta[0] not in ("100644", "100755"):
        return invalid("policy path is not a regular file")
    try:
        data = json.loads(git(root, "cat-file", "blob", meta[2]).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return invalid(f"policy file is not valid JSON: {error}")
    if not isinstance(data, dict):
        return invalid("policy file must contain a JSON object")
    unknown = sorted(set(data) - {"version", *POLICY_LIST_KEYS})
    if unknown:
        return invalid(f"unknown policy keys: {', '.join(unknown)}")
    if data.get("version") != 1:
        return invalid("policy version must be 1")
    lists: dict[str, tuple[str, ...]] = {}
    for key in POLICY_LIST_KEYS:
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            return invalid(f"{key} must be an array of non-empty strings")
        if any(item.startswith(("/", "./", "../")) or "\\" in item for item in value):
            return invalid(f"{key} patterns must be repository-relative, without a leading /, ./, ../, or backslash")
        lists[key] = tuple(value)
    policy.status = "loaded"
    policy.high = lists["high_risk_paths"]
    policy.medium = lists["medium_risk_paths"]
    policy.generated = lists["generated_paths"]
    return policy


def is_source_path(path: str) -> bool:
    """Whether a path has a supported source-code suffix, independent of its kind."""
    return PurePosixPath(path).suffix.lower() in patterns.SOURCE_SUFFIXES
