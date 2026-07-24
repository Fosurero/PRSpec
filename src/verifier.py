"""Finding verification — adversarial cross-examination and spec grounding.

A single LLM pass produces *candidate* findings.  Some are real deviations;
some are plausible-sounding hallucinations.  This module separates the two:

* :class:`SpecGrounding` is a deterministic, API-free check that the text a
  finding quotes as its ``spec_reference`` actually appears in the fetched
  specification.  A quote that cannot be located in the spec is almost always
  invented.

* :class:`VerificationEngine` runs each finding back through the analyzer a few
  times with a skeptical, refutation-oriented prompt and tallies the verdicts.
  A finding that survives independent re-examination *and* is grounded in the
  spec is reported as CONFIRMED; the rest are downgraded.

The engine depends only on an analyzer exposing ``analyze_compliance`` (the
:class:`~src.analyzer.BaseAnalyzer` contract), so it works unchanged with the
Gemini and OpenAI backends and is trivial to drive with a stub in tests.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Spec grounding (deterministic, no API)
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z0-9_]+")
# Common words that carry no grounding signal; a quote sharing only these with
# the spec is not actually grounded.
_GROUNDING_STOPWORDS = {
    "the", "and", "for", "this", "that", "with", "from", "must", "shall",
    "should", "when", "then", "than", "into", "are", "not", "but", "any",
    "all", "can", "may", "will", "each", "such", "which", "where", "value",
}


@dataclass
class GroundingResult:
    """Whether a finding's spec_reference can be located in the spec text."""

    grounded: bool
    score: float                       # 0.0 - 1.0
    matched_excerpt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grounded": self.grounded,
            "score": round(self.score, 3),
            "matched_excerpt": self.matched_excerpt,
        }


class SpecGrounding:
    """Locate a finding's quoted spec reference inside the real spec."""

    DEFAULT_THRESHOLD = 0.6

    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        self.threshold = threshold

    def check(self, finding: Dict[str, Any], spec_text: str) -> GroundingResult:
        """Return how strongly *finding*'s spec_reference matches *spec_text*."""
        reference = str(finding.get("spec_reference", "") or "").strip()
        if not reference or not spec_text:
            return GroundingResult(False, 0.0)

        hay = self._normalize(spec_text)
        ref = self._normalize(reference)
        if not ref:
            return GroundingResult(False, 0.0)

        # Exact (normalized) substring is the strongest possible signal.
        if ref in hay:
            return GroundingResult(True, 1.0, reference[:240])

        # Otherwise fall back to two cheap fuzzy signals and take the better:
        #   1. how many of the quote's significant words occur in the spec
        #   2. the closest-matching line/sentence by character similarity
        containment = self._word_containment(reference, hay)
        line_score, excerpt = self._best_line(ref, spec_text)
        score = max(containment, line_score)
        return GroundingResult(score >= self.threshold, score, excerpt)

    # ---- helpers ----

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower().replace("`", " ").replace('"', " ").replace("'", " ")
        return " ".join(text.split())

    def _word_containment(self, reference: str, normalized_hay: str) -> float:
        words = [
            w for w in _WORD_RE.findall(reference.lower())
            if len(w) >= 3 and w not in _GROUNDING_STOPWORDS
        ]
        if not words:
            return 0.0
        hits = sum(1 for w in set(words) if w in normalized_hay)
        return hits / len(set(words))

    def _best_line(self, normalized_ref: str, spec_text: str):
        """Best character-similarity of the reference against any spec line."""
        ref_words = set(_WORD_RE.findall(normalized_ref))
        best = 0.0
        best_line: Optional[str] = None
        for raw_line in spec_text.splitlines():
            line = raw_line.strip()
            if len(line) < 8:
                continue
            norm = self._normalize(line)
            # Only score lines that share at least one word — keeps this cheap
            # on large specs and avoids matching on punctuation alone.
            if ref_words and not (ref_words & set(_WORD_RE.findall(norm))):
                continue
            ratio = SequenceMatcher(None, normalized_ref, norm).ratio()
            if ratio > best:
                best, best_line = ratio, line
        return best, (best_line[:240] if best_line else None)


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------

CONFIRMED = "CONFIRMED"
DISPUTED = "DISPUTED"
REFUTED = "REFUTED"


@dataclass
class FindingVerdict:
    """Outcome of verifying one candidate finding."""

    verdict: str                       # CONFIRMED | DISPUTED | REFUTED
    verification_score: int            # 0-100, share of decisive votes that confirmed
    grounded: bool
    grounding_score: float
    rounds: int
    votes: Dict[str, int] = field(default_factory=dict)
    matched_excerpt: Optional[str] = None

    @property
    def is_confirmed(self) -> bool:
        return self.verdict == CONFIRMED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "verification_score": self.verification_score,
            "grounded": self.grounded,
            "grounding_score": round(self.grounding_score, 3),
            "rounds": self.rounds,
            "votes": self.votes,
            "matched_excerpt": self.matched_excerpt,
        }


# ---------------------------------------------------------------------------
# Verification engine
# ---------------------------------------------------------------------------


class VerificationEngine:
    """Re-examine findings adversarially and grade them by consensus."""

    # How a skeptic's returned status maps onto a vote on the original finding.
    _CONFIRM_STATUSES = {"MISSING", "PARTIAL_MATCH"}
    _REFUTE_STATUSES = {"FULL_MATCH"}

    def __init__(self, analyzer: Any, rounds: int = 2,
                 grounding: Optional[SpecGrounding] = None,
                 max_workers: int = 5):
        if rounds < 1:
            raise ValueError("rounds must be >= 1")
        self.analyzer = analyzer
        self.rounds = rounds
        self.grounding = grounding or SpecGrounding()
        self.max_workers = max_workers

    # ---- single finding ----

    def verify_finding(self, finding: Dict[str, Any], spec_text: str,
                       code_text: str, context: dict) -> FindingVerdict:
        """Run the refutation rounds for one finding and grade the result."""
        grounding = self.grounding.check(finding, spec_text)

        refutation_spec = self.analyzer._build_refutation_prompt(
            finding, spec_text, context
        )
        votes = {"confirm": 0, "refute": 0, "unsure": 0}
        for _ in range(self.rounds):
            votes[self._one_round(refutation_spec, code_text, context)] += 1

        return self._grade(votes, grounding)

    def _one_round(self, refutation_spec: str, code_text: str,
                   context: dict) -> str:
        """A single skeptic pass; returns 'confirm' | 'refute' | 'unsure'."""
        try:
            result = self.analyzer.analyze_compliance(
                refutation_spec, code_text, context
            )
        except Exception:
            # A failed round must not masquerade as a considered verdict, so
            # it votes 'unsure' — but it is never silent.
            logger.exception(
                "Skeptic round failed for %s; counting the vote as unsure",
                context.get("file_name", "<unknown>"),
            )
            return "unsure"

        if getattr(result, "failed", False):
            logger.warning(
                "Skeptic round for %s returned an ERROR result: %s",
                context.get("file_name", "<unknown>"),
                getattr(result, "error", None) or getattr(result, "summary", ""),
            )
            return "unsure"

        status = str(getattr(result, "status", "")).upper()
        if status in self._CONFIRM_STATUSES or getattr(result, "has_issues", False):
            return "confirm"
        if status in self._REFUTE_STATUSES:
            return "refute"
        return "unsure"

    def _grade(self, votes: Dict[str, int],
               grounding: GroundingResult) -> FindingVerdict:
        confirm, refute = votes["confirm"], votes["refute"]
        decisive = confirm + refute

        if decisive == 0:
            verdict, score = DISPUTED, 50
        else:
            score = round(100 * confirm / decisive)
            if confirm > refute:
                verdict = CONFIRMED
            elif refute > confirm:
                verdict = REFUTED
            else:
                verdict = DISPUTED

        # A finding we cannot even locate in the spec is never CONFIRMED,
        # however the skeptic rounds voted.
        if verdict == CONFIRMED and not grounding.grounded:
            verdict = DISPUTED

        return FindingVerdict(
            verdict=verdict,
            verification_score=score,
            grounded=grounding.grounded,
            grounding_score=grounding.score,
            rounds=self.rounds,
            votes=votes,
            matched_excerpt=grounding.matched_excerpt,
        )

    # ---- whole-result annotation ----

    def verify_results(self, results: List[Dict[str, Any]], spec_text: str,
                       code_files: Dict[str, str],
                       base_context: Optional[dict] = None
                       ) -> List[Dict[str, Any]]:
        """Annotate every issue in *results* with a verification verdict.

        *results* is the per-file list emitted by the analysis pipeline; each
        carries a ``file_name`` and an ``issues`` list.  *code_files* maps file
        paths to source so each issue is re-checked against its own file.  The
        input dicts are mutated in place (and also returned).
        """
        base_context = base_context or {}

        # Flatten to (result, issue) work items so independent findings verify
        # concurrently, mirroring the parallel analysis pipeline.
        tasks = []
        for result in results:
            file_name = result.get("file_name", "")
            code_text = code_files.get(file_name, "")
            for issue in result.get("issues", []) or []:
                ctx = dict(base_context)
                ctx["file_name"] = file_name
                tasks.append((issue, code_text, ctx))

        if not tasks:
            for result in results:
                result["verification"] = self._result_summary([])
            return results

        workers = min(len(tasks), self.max_workers)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self.verify_finding, issue, spec_text, code, ctx):
                issue
                for issue, code, ctx in tasks
            }
            for future in as_completed(futures):
                issue = futures[future]
                issue["verification"] = future.result().to_dict()

        # Per-file rollup so reports can show a verified count at a glance.
        for result in results:
            verdicts = [
                i.get("verification", {})
                for i in result.get("issues", []) or []
            ]
            result["verification"] = self._result_summary(verdicts)
        return results

    @staticmethod
    def _result_summary(verdicts: List[Dict[str, Any]]) -> Dict[str, int]:
        confirmed = sum(1 for v in verdicts if v.get("verdict") == CONFIRMED)
        disputed = sum(1 for v in verdicts if v.get("verdict") == DISPUTED)
        refuted = sum(1 for v in verdicts if v.get("verdict") == REFUTED)
        return {
            "confirmed": confirmed,
            "disputed": disputed,
            "refuted": refuted,
            "total": len(verdicts),
        }


# ---------------------------------------------------------------------------
# Helpers shared with reporting
# ---------------------------------------------------------------------------


def confirmed_issues(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Issues in a result that survived verification (CONFIRMED).

    Falls back to all issues when a result was never verified, so callers that
    run without ``--verify`` keep their previous behaviour.
    """
    issues = result.get("issues", []) or []
    if not any("verification" in i for i in issues):
        return issues
    return [i for i in issues if i.get("verification", {}).get("verdict") == CONFIRMED]
