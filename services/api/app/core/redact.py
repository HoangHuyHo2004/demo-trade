"""Redactor for logs and agent traces. Simple pattern-based scrubber."""
from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[^\s,;\"']+"), r"\1=***"),
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "sk-***"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "***@***"),
]


def redact(value: str) -> str:
    out = value
    for pat, repl in _PATTERNS:
        out = pat.sub(repl, out)
    return out
