"""Cross-client differential analysis.

Compares how multiple Ethereum clients implement the *same* EIP and reports
where their implementations agree and where they diverge.

The core :class:`DifferentialEngine.build` method is deterministic and requires
no API keys — it consumes per-client analysis results (the same dicts produced
by the standard ``analyze`` pipeline) and produces a structured comparison
matrix.  An optional LLM synthesis pass (:meth:`DifferentialEngine.synthesize`)
adds a natural-language narrative of the divergences.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .verifier import confirmed_issues

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result summarisation (kept standalone so the engine has no dependency on the
# report generator).
# ---------------------------------------------------------------------------


def summarize_results(results: List[Dict[str, Any]],
                      confirmed_only: bool = False) -> Dict[str, Any]:
    """Aggregate per-file analysis dicts into client-level summary stats.

    When *confirmed_only* is set and the results carry verification verdicts,
    only CONFIRMED findings are counted, so cross-client stats reflect what
    survived adversarial verification rather than raw candidates.
    """
    total_issues = 0
    high = med = low = 0
    confidences: List[int] = []
    statuses: List[str] = []
    type_counts: Dict[str, int] = {}

    for result in results:
        issues = confirmed_issues(result) if confirmed_only else (result.get("issues", []) or [])
        total_issues += len(issues)
        for issue in issues:
            severity = str(issue.get("severity", "")).upper()
            if severity == "HIGH":
                high += 1
            elif severity == "MEDIUM":
                med += 1
            elif severity == "LOW":
                low += 1
            itype = str(issue.get("type", "")).upper()
            if itype:
                type_counts[itype] = type_counts.get(itype, 0) + 1
        confidences.append(int(result.get("confidence", 0) or 0))
        statuses.append(str(result.get("status", "UNKNOWN")))

    failed = sum(1 for s in statuses if s == "ERROR")

    if statuses and failed == len(statuses):
        # Nothing was actually analyzed; reporting that as UNCERTAIN would
        # present a failed run as an inconclusive one.
        overall = "ANALYSIS FAILED"
    elif "MISSING" in statuses or high > 0:
        overall = "ISSUES FOUND"
    elif "PARTIAL_MATCH" in statuses or med > 0:
        overall = "PARTIAL"
    elif statuses and all(s == "FULL_MATCH" for s in statuses):
        overall = "COMPLIANT"
    else:
        overall = "UNCERTAIN"

    return {
        "overall_status": overall,
        "failed_files": failed,
        "average_confidence": round(sum(confidences) / len(confidences)) if confidences else 0,
        "files_analyzed": len(results),
        "total_issues": total_issues,
        "high_severity": high,
        "medium_severity": med,
        "low_severity": low,
        "issue_types": type_counts,
    }


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ClientAnalysis:
    """One client's analysis output for a single EIP."""

    client: str
    language: str
    results: List[Dict[str, Any]] = field(default_factory=list)

    def summary(self, confirmed_only: bool = False) -> Dict[str, Any]:
        """Return aggregate summary stats for this client."""
        return summarize_results(self.results, confirmed_only=confirmed_only)

    def all_issue_text(self) -> str:
        """Concatenate all issue/summary text (lowercased) for keyword matching."""
        parts: List[str] = []
        for result in self.results:
            parts.append(str(result.get("summary", "")))
            for issue in result.get("issues", []) or []:
                for key in (
                    "type", "description", "spec_reference",
                    "code_location", "potential_impact", "suggestion",
                ):
                    parts.append(str(issue.get(key, "")))
        return " ".join(parts).lower()


@dataclass
class DiffRow:
    """A single comparison dimension across all clients."""

    dimension: str                 # human-readable label
    category: str                  # "status" | "issue_type" | "focus_area"
    per_client: Dict[str, str]     # client -> displayed value
    verdict: str                   # "AGREE" | "DIVERGE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "category": self.category,
            "per_client": self.per_client,
            "verdict": self.verdict,
        }


@dataclass
class DifferentialResult:
    """Full cross-client differential for one EIP."""

    eip: int
    eip_title: str
    clients: List[str]
    client_summaries: Dict[str, Dict[str, Any]]
    rows: List[DiffRow]
    divergences: List[str]
    agreements: List[str]
    narrative: str
    llm_synthesis: Optional[str] = None

    @property
    def divergence_count(self) -> int:
        return sum(1 for r in self.rows if r.verdict == "DIVERGE")

    @property
    def agreement_count(self) -> int:
        return sum(1 for r in self.rows if r.verdict == "AGREE")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eip": self.eip,
            "eip_title": self.eip_title,
            "clients": self.clients,
            "client_summaries": self.client_summaries,
            "comparison": [r.to_dict() for r in self.rows],
            "divergences": self.divergences,
            "agreements": self.agreements,
            "narrative": self.narrative,
            "llm_synthesis": self.llm_synthesis,
            "stats": {
                "diverging_dimensions": self.divergence_count,
                "agreeing_dimensions": self.agreement_count,
            },
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class DifferentialEngine:
    """Builds a cross-client differential from per-client analysis results."""

    # Canonical issue types emitted by the analyzer prompt.
    ISSUE_TYPES = ["MISSING_CHECK", "INCORRECT_LOGIC", "EDGE_CASE", "DEVIATION"]

    # Generic tokens stripped from focus-area names before keyword matching.
    _STOPWORDS = {
        "the", "and", "for", "per", "of", "to", "a", "an",
        "check", "checks", "handling", "validation", "calculation",
        "update", "compliance", "implications",
    }

    def __init__(self, focus_areas: Optional[List[str]] = None):
        """*focus_areas* are EIP-specific dimension names from config."""
        self.focus_areas = focus_areas or []

    # ---- public API ----

    def build(self, per_client: Dict[str, ClientAnalysis],
              eip: int, eip_title: str = "",
              confirmed_only: bool = False) -> DifferentialResult:
        """Construct the differential comparison.

        *per_client* maps client name -> :class:`ClientAnalysis`.  At least two
        clients are required.  *confirmed_only* restricts the stats to findings
        that survived verification (no-op when results were not verified).
        """
        if len(per_client) < 2:
            raise ValueError(
                "Differential analysis requires at least 2 clients; "
                f"got {len(per_client)}."
            )

        clients = list(per_client.keys())
        summaries = {c: ca.summary(confirmed_only=confirmed_only)
                     for c, ca in per_client.items()}

        rows: List[DiffRow] = []
        rows.append(self._status_row(clients, summaries))
        rows.extend(self._issue_type_rows(clients, summaries))
        rows.extend(self._focus_area_rows(clients, per_client))

        divergences, agreements = self._collect_notes(rows, clients, summaries)
        narrative = self._build_narrative(eip, eip_title, clients, summaries, rows)

        return DifferentialResult(
            eip=eip,
            eip_title=eip_title or f"EIP-{eip}",
            clients=clients,
            client_summaries=summaries,
            rows=rows,
            divergences=divergences,
            agreements=agreements,
            narrative=narrative,
        )

    def synthesize(self, analyzer: Any, differential: DifferentialResult,
                   per_client: Dict[str, ClientAnalysis]) -> Optional[str]:
        """Best-effort LLM narrative of the divergences.

        Reuses any analyzer exposing ``analyze_compliance``.  Returns ``None``
        on failure so callers can treat it as purely additive.
        """
        try:
            spec_text = (
                f"You are comparing how multiple Ethereum clients implement "
                f"{differential.eip_title}. Summarise where the implementations "
                f"AGREE and where they DIVERGE, and flag any client whose "
                f"behaviour is unique or potentially consensus-breaking."
            )
            findings_blob = self._findings_blob(per_client)
            context = {
                "eip_number": differential.eip,
                "eip_title": differential.eip_title,
                "file_name": "cross-client-differential",
                "function_name": "differential synthesis",
                "language": "multiple",
                "focus_areas": self.focus_areas,
            }
            result = analyzer.analyze_compliance(spec_text, findings_blob, context)
            if getattr(result, "failed", False):
                logger.warning(
                    "Differential synthesis unavailable: %s",
                    getattr(result, "error", None) or result.summary,
                )
                return None
            return result.summary or None
        except Exception:
            logger.exception("Differential synthesis failed for EIP-%s", differential.eip)
            return None

    # ---- row builders ----

    def _status_row(self, clients: List[str],
                    summaries: Dict[str, Dict[str, Any]]) -> DiffRow:
        per_client = {c: summaries[c]["overall_status"] for c in clients}
        verdict = "AGREE" if len(set(per_client.values())) == 1 else "DIVERGE"
        return DiffRow(
            dimension="Overall status",
            category="status",
            per_client=per_client,
            verdict=verdict,
        )

    def _issue_type_rows(self, clients: List[str],
                         summaries: Dict[str, Dict[str, Any]]) -> List[DiffRow]:
        rows: List[DiffRow] = []
        # Only show types that at least one client reported.
        seen_types = [
            t for t in self.ISSUE_TYPES
            if any(summaries[c]["issue_types"].get(t, 0) > 0 for c in clients)
        ]
        for itype in seen_types:
            per_client = {
                c: str(summaries[c]["issue_types"].get(itype, 0)) for c in clients
            }
            # Agree when every client has the same presence/absence pattern.
            presence = {(v != "0") for v in per_client.values()}
            verdict = "AGREE" if len(presence) == 1 else "DIVERGE"
            rows.append(DiffRow(
                dimension=f"{itype.replace('_', ' ').title()} issues",
                category="issue_type",
                per_client=per_client,
                verdict=verdict,
            ))
        return rows

    def _focus_area_rows(self, clients: List[str],
                         per_client: Dict[str, ClientAnalysis]) -> List[DiffRow]:
        rows: List[DiffRow] = []
        texts = {c: per_client[c].all_issue_text() for c in clients}
        for area in self.focus_areas:
            tokens = self._focus_tokens(area)
            if not tokens:
                continue
            flags = {
                c: ("flagged" if self._text_matches(texts[c], tokens) else "clean")
                for c in clients
            }
            verdict = "AGREE" if len(set(flags.values())) == 1 else "DIVERGE"
            rows.append(DiffRow(
                dimension=area.replace("_", " ").title(),
                category="focus_area",
                per_client=flags,
                verdict=verdict,
            ))
        return rows

    # ---- notes & narrative ----

    def _collect_notes(self, rows: List[DiffRow], clients: List[str],
                       summaries: Dict[str, Dict[str, Any]]):
        divergences: List[str] = []
        agreements: List[str] = []

        for row in rows:
            if row.verdict == "DIVERGE":
                detail = ", ".join(f"{c}={row.per_client[c]}" for c in clients)
                divergences.append(f"{row.dimension}: {detail}")
            else:
                # Record a concise agreement note (one shared value).
                shared = next(iter(row.per_client.values()))
                agreements.append(f"{row.dimension}: all clients = {shared}")

        # Highlight clients carrying unique HIGH-severity load.
        high_loads = {c: summaries[c]["high_severity"] for c in clients}
        max_high = max(high_loads.values()) if high_loads else 0
        if max_high > 0:
            worst = [c for c, n in high_loads.items() if n == max_high]
            if len(worst) < len(clients):
                divergences.append(
                    f"Highest high-severity load: {', '.join(worst)} "
                    f"({max_high} high-severity issue(s))."
                )

        return divergences, agreements

    def _build_narrative(self, eip: int, eip_title: str, clients: List[str],
                         summaries: Dict[str, Dict[str, Any]],
                         rows: List[DiffRow]) -> str:
        n_div = sum(1 for r in rows if r.verdict == "DIVERGE")
        n_agree = sum(1 for r in rows if r.verdict == "AGREE")

        parts = [
            f"PRSpec performed a cross-client differential analysis of "
            f"{eip_title} across {len(clients)} clients "
            f"({', '.join(clients)}).",
            f"Of {len(rows)} compared dimensions, {n_agree} agree and "
            f"{n_div} diverge.",
        ]

        statuses = {c: summaries[c]["overall_status"] for c in clients}
        if len(set(statuses.values())) == 1:
            parts.append(
                f"All clients share the overall verdict "
                f"'{next(iter(statuses.values()))}'."
            )
        else:
            status_bits = ", ".join(f"{c}: {s}" for c, s in statuses.items())
            parts.append(f"Overall verdicts differ — {status_bits}.")

        return " ".join(parts)

    # ---- helpers ----

    def _focus_tokens(self, area: str) -> List[str]:
        """Significant tokens for a focus-area name (stopwords removed)."""
        return [
            tok for tok in area.lower().split("_")
            if len(tok) >= 3 and tok not in self._STOPWORDS
        ]

    @staticmethod
    def _text_matches(text: str, tokens: List[str]) -> bool:
        """True when every significant token appears in *text*."""
        return all(tok in text for tok in tokens)

    @staticmethod
    def _findings_blob(per_client: Dict[str, ClientAnalysis]) -> str:
        """Compact, LLM-friendly rendering of every client's findings."""
        sections: List[str] = []
        for client, ca in per_client.items():
            s = ca.summary()
            lines = [
                f"=== CLIENT: {client} ({ca.language}) ===",
                f"Overall: {s['overall_status']} "
                f"@ {s['average_confidence']}% confidence, "
                f"{s['total_issues']} issue(s) "
                f"(H:{s['high_severity']} M:{s['medium_severity']} "
                f"L:{s['low_severity']})",
            ]
            for result in ca.results:
                for issue in result.get("issues", []) or []:
                    lines.append(
                        f"- [{issue.get('severity', '?')}] "
                        f"{issue.get('type', 'ISSUE')}: "
                        f"{issue.get('description', '')}"
                    )
            sections.append("\n".join(lines))
        return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Convenience orchestration (library use)
# ---------------------------------------------------------------------------


def analyze_clients(eip: int, clients: List[str], config: Any,
                    provider: Optional[str] = None,
                    use_llm_synthesis: bool = False,
                    verify: bool = False,
                    verify_rounds: int = 2) -> DifferentialResult:
    """Run analysis for each client and build a differential.

    Thin wrapper over the standard analysis pipeline for programmatic use::

        from src.config import Config
        from src.differential import analyze_clients

        diff = analyze_clients(1559, ["go-ethereum", "nethermind"], Config())
        print(diff.narrative)
    """
    # Lazy import avoids a circular dependency with the CLI module.
    from .cli import _run_analysis
    from .code_fetcher import CodeFetcher
    from .spec_fetcher import SpecFetcher

    llm_provider = provider or config.llm_provider
    per_client: Dict[str, ClientAnalysis] = {}
    last_analyzer = None

    for client in clients:
        results, analyzer = _run_analysis(
            eip, client, config, llm_provider,
            verify=verify, verify_rounds=verify_rounds,
        )
        per_client[client] = ClientAnalysis(
            client=client,
            language=CodeFetcher.client_language(client),
            results=results,
        )
        last_analyzer = analyzer

    engine = DifferentialEngine(focus_areas=config.get_eip_focus_areas(eip))
    eip_title = SpecFetcher.get_eip_title(eip)
    differential = engine.build(per_client, eip, eip_title, confirmed_only=verify)

    if use_llm_synthesis and last_analyzer is not None:
        differential.llm_synthesis = engine.synthesize(
            last_analyzer, differential, per_client
        )

    return differential
