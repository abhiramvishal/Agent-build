from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


DENY_FILENAME_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\.env$", re.IGNORECASE),
    re.compile(r"\.pem$", re.IGNORECASE),
    re.compile(r"\.key$", re.IGNORECASE),
    re.compile(r"id_rsa$", re.IGNORECASE),
    re.compile(r"\.p12$", re.IGNORECASE),
    re.compile(r"config.*\.json$", re.IGNORECASE),
]

DENY_CONTENT_PATTERNS: List[re.Pattern[str]] = [
    # AWS Access Key ID
    re.compile(r"AKIA[0-9A-Z]{16}"),
    # Generic Bearer / OAuth-like tokens
    re.compile(r"Bearer\s+[0-9A-Za-z\-._~+/]+=*"),
    # Private key headers
    re.compile(r"-----BEGIN (RSA )?PRIVATE KEY-----"),
    # GitHub Personal Access Token (classic heuristic)
    re.compile(r"ghp_[0-9A-Za-z]{36}"),
    # Simple JWT heuristic
    re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
]


@dataclass
class SafetyIssue:
    path: Path
    reason: str


class SafetyScanner:
    def __init__(self) -> None:
        ...

    def scan_paths(self, paths: Iterable[Path]) -> List[SafetyIssue]:
        issues: List[SafetyIssue] = []
        for p in paths:
            # Filenames
            for pat in DENY_FILENAME_PATTERNS:
                if pat.search(p.name):
                    issues.append(SafetyIssue(p, f"filename matches deny pattern: {pat.pattern}"))
                    break
            # Skip content scan if already flagged
            if any(i.path == p for i in issues):
                continue
            if not p.is_file():
                continue
            try:
                text = p.read_text(encoding="utf8", errors="ignore")
            except OSError:
                continue
            for pat in DENY_CONTENT_PATTERNS:
                if pat.search(text):
                    issues.append(SafetyIssue(p, f"content matches deny pattern: {pat.pattern}"))
                    break
        return issues

    @staticmethod
    def print_issues(issues: List[SafetyIssue]) -> None:
        for issue in issues:
            print(f"[SAFETY] {issue.path}: {issue.reason}")

