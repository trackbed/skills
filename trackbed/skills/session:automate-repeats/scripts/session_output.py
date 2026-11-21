"""Output handling for the session-search extractors."""

from __future__ import annotations

import atexit
import os
import re
import sys
import tempfile
from typing import Dict, List, Optional, Pattern, TextIO, cast


_SENSITIVE_PATTERNS: List[Pattern[str]] = [
    re.compile(r"(?i)\b(authorization\s*:\s*bearer\s+)[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)\b((?:api[_-]?key|token|secret|password|passwd|pwd)\s*[:=]\s*)[^\s'\"`;&|]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
]


def redact_sensitive(text: object) -> str:
    """Redact common credential shapes before writing extract files."""
    if not isinstance(text, str):
        return ""

    redacted = text
    for pattern in _SENSITIVE_PATTERNS:
        redacted = pattern.sub(
            lambda match: (match.group(1) if match.lastindex else "") + "[REDACTED]",
            redacted,
        )
    return redacted


class AtomicOutput:
    """Redirect stdout to a temporary file and atomically publish on success."""

    def __init__(self, output_path: Optional[str]) -> None:
        self.output_path = output_path or None
        self._original_stdout = sys.stdout
        self._stream: Optional[TextIO] = None
        self._temporary_path: Optional[str] = None
        if self.output_path is not None:
            output_dir = os.path.dirname(os.path.abspath(self.output_path))
            stream = cast(
                TextIO,
                tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=output_dir,
                    prefix=f".{os.path.basename(self.output_path)}.",
                    delete=False,
                ),
            )
            self._stream = stream
            self._temporary_path = stream.name
            sys.stdout = stream
        atexit.register(self.cleanup)

    @property
    def enabled(self) -> bool:
        """Whether extracted output will be published to a destination path."""
        return self.output_path is not None

    def commit(self) -> Dict[str, object]:
        """Publish redirected output and return fields for the status record."""
        if self.output_path is None:
            return {}
        if self._stream is None or self._temporary_path is None:
            raise RuntimeError("atomic output was not initialized")

        self._stream.flush()
        self._stream.close()
        sys.stdout = self._original_stdout
        bytes_written = os.path.getsize(self._temporary_path)
        os.replace(self._temporary_path, self.output_path)
        self._temporary_path = None
        return {
            "wrote": self.output_path,
            "bytes": bytes_written,
        }

    def cleanup(self) -> None:
        """Restore stdout and remove any unpublished temporary output."""
        if self._stream is not None and sys.stdout is self._stream:
            sys.stdout = self._original_stdout
        if self._stream is not None and not self._stream.closed:
            self._stream.close()
        if self._temporary_path is not None:
            try:
                os.unlink(self._temporary_path)
            except FileNotFoundError:
                pass
