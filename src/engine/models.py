"""Data structures returned by the PRSpec Engine API."""

from typing import Any, Dict, List, TypedDict


class Finding(TypedDict, total=False):
    """A single finding produced by the scanner."""

    id: str
    severity: str       # "high", "medium", "low", "info"
    title: str
    message: str
    file: str
    line: int
    hint: str


class Summary(TypedDict):
    """Aggregate counts for a scan run."""

    high: int
    med: int
    low: int
    info: int
    files_scanned: int


class ScanResult(TypedDict):
    """Top-level dict returned by :func:`scan_path`."""

    tool: str
    tool_version: str
    ruleset: str
    findings: List[Finding]
    summary: Summary
