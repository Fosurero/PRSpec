#!/usr/bin/env python3
"""Besu mutation scoreboard for PRSpec.

Injects the spec deviations listed in ``pilot/besu/mutations.yaml`` into a
pinned Besu checkout (in memory only; the checkout is never modified), runs
the normal PRSpec per-file analysis (+ adversarial verification) on the clean
and on each mutated file, and scores detection with the criteria that are
written down in the YAML *before* any run.

    # 1. validate the experiment without any LLM call (no API key needed)
    python scripts/mutation_scoreboard.py --besu-dir ../besu --dry-run

    # 2. real run (needs the provider key, e.g. GEMINI_API_KEY)
    python scripts/mutation_scoreboard.py --besu-dir ../besu --runs 2

Outputs (in --out): manifest.json, patches/*.diff, raw/*.json,
scoreboard.json, scoreboard.md. Exit code 20 if any analysis failed, so a
partial scoreboard can never be published as complete.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import witness as W  # noqa: E402
from src.code_fetcher import CodeFetcher  # noqa: E402

EXIT_INCOMPLETE = 20
MATCH_FIELDS = ("code_location", "description", "spec_reference",
                "suggestion", "potential_impact")


# ---------------------------------------------------------------- helpers

def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_head(path: Path, mark_dirty: bool = False) -> str:
    """Commit SHA of a checkout; "-dirty" if it has uncommitted changes."""
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
        if mark_dirty and subprocess.check_output(
                ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"],
                text=True).strip():
            sha += "-dirty"
        return sha
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def issue_matches(issue: dict, keywords) -> bool:
    text = " ".join(str(issue.get(f, "")) for f in MATCH_FIELDS).lower()
    return any(k.lower() in text for k in keywords)


def is_confirmed(issue: dict) -> bool:
    return issue.get("verification", {}).get("verdict") == "CONFIRMED"


def classify(mutated: dict, baseline: dict, keywords, verified: bool) -> dict:
    """Apply the pre-registered criteria from mutations.yaml."""
    if mutated.get("status") == "ERROR" or baseline.get("status") == "ERROR":
        return {"outcome": "error", "matching_issues": 0}
    base_hits = [i for i in baseline.get("issues", []) or [] if issue_matches(i, keywords)]
    hits = [i for i in mutated.get("issues", []) or [] if issue_matches(i, keywords)]
    if base_hits:
        outcome = "inconclusive"          # baseline already talks about it
    elif not hits:
        outcome = "missed"
    elif verified and any(is_confirmed(i) for i in hits):
        outcome = "confirmed"
    else:
        outcome = "flagged"
    return {"outcome": outcome, "matching_issues": len(hits),
            "baseline_matching_issues": len(base_hits)}


def load_experiment(path: Path, besu_dir: Path, allow_other_commit: bool):
    exp = yaml.safe_load(path.read_text())
    pinned = exp["besu"]["commit"]
    head = git_head(besu_dir)
    if head != pinned and not allow_other_commit:
        sys.exit(f"Besu checkout is at {head}, experiment is pinned to {pinned}. "
                 f"Run: git -C {besu_dir} checkout {pinned}")
    registry = CodeFetcher.CLIENTS["besu"]["eip_files"]
    problems, prepared = [], []
    for m in exp["mutations"]:
        if m["file"] not in registry.get(m["eip"], []):
            problems.append(f"{m['id']}: {m['file']} is not in the EIP-{m['eip']} registry")
            continue
        original = (besu_dir / m["file"]).read_text(encoding="utf-8")
        n = original.count(m["find"])
        if n != 1:
            problems.append(f"{m['id']}: 'find' occurs {n} times in {m['file']} (need exactly 1)")
            continue
        mutated = original.replace(m["find"], m["replace"], 1)
        diff = "".join(difflib.unified_diff(
            original.splitlines(keepends=True), mutated.splitlines(keepends=True),
            fromfile=f"a/{m['file']}", tofile=f"b/{m['file']}"))
        prepared.append({**m, "original": original, "mutated": mutated, "diff": diff})
    if problems:
        sys.exit("Experiment is invalid:\n  " + "\n  ".join(problems))
    return exp, head, prepared


# ---------------------------------------------------------------- analysis

class Runner:
    def __init__(self, provider: str | None, verify: bool, rounds: int, workers: int):
        from src.cli import _build_analyzer, _build_verify_analyzer
        from src.config import Config
        from src.verifier import VerificationEngine
        self.cfg = Config()
        self.provider = provider or self.cfg.llm_provider
        self.analyzer = _build_analyzer(self.provider, self.cfg)
        self.verify = verify
        self.engine = (VerificationEngine(
            _build_verify_analyzer(self.provider, self.cfg, self.analyzer), rounds=rounds)
            if verify else None)
        self.workers = workers
        self.specs = {}

    def spec(self, eip: int) -> str:
        if eip not in self.specs:
            from src.cli import build_spec_text
            from src.spec_fetcher import SpecFetcher
            data = SpecFetcher(github_token=self.cfg.github_token).fetch_eip_spec(eip, mode="diff")
            self.specs[eip] = (build_spec_text(data, eip), data.get("title", f"EIP-{eip}"))
        return self.specs[eip]

    def analyze_file(self, eip: int, file_path: str, code: str) -> dict:
        from src.cli import _analyze_one_file
        spec_text, title = self.spec(eip)
        context = {"eip_number": eip, "eip_title": title, "file_name": file_path,
                   "function_name": f"EIP-{eip} implementation", "language": "java",
                   "focus_areas": self.cfg.get_eip_focus_areas(eip)}
        t0 = time.monotonic()
        try:
            result = _analyze_one_file(self.analyzer, spec_text, file_path, code, context)
            if self.engine and result.get("status") != "ERROR":
                base = {k: context[k] for k in ("eip_number", "eip_title", "language", "focus_areas")}
                self.engine.verify_results([result], spec_text, {file_path: code}, base)
        except Exception as e:  # recorded, never swallowed into a clean result
            result = {"status": "ERROR", "issues": [], "file_name": file_path,
                      "summary": f"{type(e).__name__}: {e}"}
        result["seconds"] = round(time.monotonic() - t0, 1)
        result["code_sha256"] = sha256(code)
        return result


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--besu-dir", required=True, type=Path)
    ap.add_argument("--mutations", type=Path, default=ROOT / "pilot/besu/mutations.yaml")
    ap.add_argument("--out", type=Path, default=ROOT / "output/besu-scoreboard")
    ap.add_argument("--provider", default=None, help="gemini | openai | azure (default: config)")
    ap.add_argument("--runs", type=int, default=1, help="repeat everything N times")
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--verify-rounds", type=int, default=2)
    ap.add_argument("--only", default=None, help="comma-separated mutation ids")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true", help="validate only, no LLM calls")
    ap.add_argument("--allow-other-commit", action="store_true")
    ap.add_argument("--eips-dir", type=Path, default=None,
                    help="local ethereum/EIPs checkout for the witness spec text (else GitHub raw)")
    args = ap.parse_args()

    besu_dir = args.besu_dir.resolve()
    exp, head, muts = load_experiment(args.mutations, besu_dir, args.allow_other_commit)
    if args.only:
        wanted = set(args.only.split(","))
        muts = [m for m in muts if m["id"] in wanted]

    out = args.out
    (out / "patches").mkdir(parents=True, exist_ok=True)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    for m in muts:
        (out / "patches" / f"{m['id']}.diff").write_text(m["diff"])

    registry = CodeFetcher.CLIENTS["besu"]["eip_files"]
    eips = sorted({m["eip"] for m in muts})
    baseline_files = {e: registry[e] for e in eips}
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prspec_commit": git_head(ROOT, mark_dirty=True),
        "besu_commit": head,
        "mutations_file_sha256": sha256(args.mutations.read_text()),
        "mutations": [{k: m[k] for k in ("id", "eip", "title", "file", "spec_rule", "keywords")}
                      for m in muts],
        "baseline_files": baseline_files,
        "runs": args.runs, "verify": not args.no_verify, "verify_rounds": args.verify_rounds,
        "dry_run": args.dry_run,
    }
    # Deterministic witness column (no LLM): does a rulebook constant check
    # catch the mutation? Runs in --dry-run too.
    wit = witness_column(muts, besu_dir, args.eips_dir)
    (out / "witness.json").write_text(json.dumps(wit, indent=2))
    manifest["witness"] = {k: v["outcome"] for k, v in wit.items()}
    if args.dry_run:
        print(render_witness_column(wit))
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
        print(f"OK: {len(muts)} mutations apply exactly once at {head}; "
              f"all target registered files. Baseline = "
              f"{sum(len(v) for v in baseline_files.values())} files. Patches in {out/'patches'}")
        return 0

    runner = Runner(args.provider, not args.no_verify, args.verify_rounds, args.workers)
    manifest.update({"provider": runner.provider,
                     "model": runner.analyzer.get_model_info().get("model")})
    rows, baselines_all, incomplete = [], [], False
    t_start = time.monotonic()
    for run in range(1, args.runs + 1):
        jobs = [("baseline", e, f, (besu_dir / f).read_text(encoding="utf-8"))
                for e, files in baseline_files.items() for f in files]
        jobs += [(m["id"], m["eip"], m["file"], m["mutated"]) for m in muts]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(lambda j: runner.analyze_file(j[1], j[2], j[3]), jobs))
        base = {}
        for (kind, eip, f, _), res in zip(jobs, results):
            res.update({"run": run, "kind": kind, "eip": eip})
            name = f"run{run}-{kind}-{Path(f).stem}.json"
            (out / "raw" / name).write_text(json.dumps(res, indent=2))
            incomplete |= res.get("status") == "ERROR"
            if kind == "baseline":
                base[f] = res
                baselines_all.append(res)
        for (kind, eip, f, _), res in zip(jobs, results):
            if kind == "baseline":
                continue
            m = next(x for x in muts if x["id"] == kind)
            verdict = classify(res, base[f], m["keywords"], not args.no_verify)
            rows.append({"run": run, "id": kind, "eip": eip, "title": m["title"],
                         "file": Path(f).name, **verdict, "seconds": res.get("seconds"),
                         "witness": wit.get(kind, {}).get("outcome")})

    # False-positive candidates: issues on clean code (CONFIRMED if verified)
    fp = [{"run": b["run"], "file": Path(b["file_name"]).name,
           "description": i.get("description", "")[:300],
           "verdict": i.get("verification", {}).get("verdict")}
          for b in baselines_all for i in b.get("issues", []) or []
          if args.no_verify or is_confirmed(i)]
    counts = {}
    for r in rows:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    tokens = {}
    for f in (out / "raw").glob("run*.json"):
        meta = json.loads(f.read_text()).get("meta") or {}
        for k in ("prompt_token_count", "candidates_token_count", "thoughts_token_count",
                  "total_token_count"):
            if isinstance(meta.get(k), int):
                tokens[k] = tokens.get(k, 0) + meta[k]
    score = {"manifest": manifest, "rows": rows, "counts": counts, "tokens_primary_pass": tokens,
             "baseline_issue_candidates": fp, "incomplete": incomplete,
             "wall_seconds": round(time.monotonic() - t_start, 1)}
    (out / "scoreboard.json").write_text(json.dumps(score, indent=2))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "scoreboard.md").write_text(render_md(score))
    print(render_md(score))
    return EXIT_INCOMPLETE if incomplete else 0


def witness_column(muts, besu_dir: Path, eips_dir) -> dict:
    """Per mutation: 'caught' if a witness rule passes on clean code and fails
    on the mutated file; 'not-applicable' if no rule covers it; 'error' if the
    rulebook could not be evaluated (never silently 'missed')."""
    out, books, specs, base = {}, {}, {}, {}
    for m in muts:
        eip = m["eip"]
        try:
            if eip not in books:
                books[eip] = W.load_rulebook(eip)
                specs[eip] = W.load_spec_text(eip, books[eip]["spec"]["pinned_ref"],
                                              eips_dir=eips_dir)
                base[eip] = {r.rule_id: r.status for r in W.check_rules(
                    books[eip], specs[eip], "besu", W.dir_reader(besu_dir))}
            res = W.check_rules(books[eip], specs[eip], "besu",
                                W.dir_reader(besu_dir, {m["file"]: m["mutated"]}))
        except Exception as e:  # noqa: BLE001
            out[m["id"]] = {"outcome": "error", "note": f"{type(e).__name__}: {e}"}
            continue
        caught = [r for r in res if r.status == W.FAIL and base[eip].get(r.rule_id) == W.PASS]
        if caught:
            out[m["id"]] = {"outcome": "caught", "rules": [r.to_dict() for r in caught]}
        else:
            out[m["id"]] = {"outcome": "not-applicable",
                            "note": "no constant rule covers this mutation; needs semantic (LLM) analysis"}
    return out


def render_witness_column(wit: dict) -> str:
    lines = ["Deterministic witness (no LLM, no API key):"]
    for mid, w in wit.items():
        extra = ""
        if w["outcome"] == "caught":
            extra = "; ".join(f"{r['rule_id']}: spec {r['expected']} vs code {r['actual']} "
                              f"({Path(r['code_file']).name}:{r['code_line']})" for r in w["rules"])
        lines.append(f"  {mid:4} {w['outcome']:15} {extra}")
    return "\n".join(lines)


def render_md(score: dict) -> str:
    m = score["manifest"]
    lines = [
        "# PRSpec x Besu mutation scoreboard", "",
        f"- Besu commit: `{m['besu_commit']}`",
        f"- PRSpec commit: `{m['prspec_commit']}`",
        f"- Model: `{m.get('provider')}` / `{m.get('model')}`; verify: {m['verify']} "
        f"({m['verify_rounds']} rounds); runs: {m['runs']}",
        f"- mutations.yaml sha256: `{m['mutations_file_sha256'][:16]}...` (criteria fixed before the run)",
        "",
    ]
    if score["incomplete"]:
        lines += ["> **INCOMPLETE RUN**: at least one analysis failed. Do not publish these numbers.", ""]
    lines += ["| Run | ID | EIP | Mutation | File | LLM outcome | Matching issues | Witness (no LLM) | Seconds |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in score["rows"]:
        lines.append(f"| {r['run']} | {r['id']} | {r['eip']} | {r['title']} | `{r['file']}` | "
                     f"**{r['outcome']}** | {r.get('matching_issues', 0)} | {r.get('witness')} | "
                     f"{r.get('seconds')} |")
    lines += ["", "Totals: " + ", ".join(f"{k} = {v}" for k, v in sorted(score["counts"].items())),
              "", f"Baseline (clean HEAD) issue candidates for hand triage: "
              f"{len(score['baseline_issue_candidates'])}", ""]
    for c in score["baseline_issue_candidates"]:
        lines.append(f"- run {c['run']} `{c['file']}` ({c['verdict']}): {c['description']}")
    if score.get("tokens_primary_pass"):
        lines.append("Tokens (primary analysis calls, from API usage metadata): " + ", ".join(
            f"{k} = {v}" for k, v in score["tokens_primary_pass"].items()))
    lines += ["", f"Wall time: {score['wall_seconds']} s", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
