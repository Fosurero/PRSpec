"""Deterministic spec witnesses and Fork Watch for PRSpec.

A *witness* is a small, machine-checkable rule extracted from a pinned EIP
revision (for example ``ELASTICITY_MULTIPLIER = 2``) together with an anchor
that locates the same value in a client's source code. Checking a witness is
deterministic: no LLM call, no network access if the spec text and the client
checkout are local, and the result carries the evidence needed to reproduce it
(spec revision + sha256 + line, client commit + file + line).

Fork Watch compares the parameters of two revisions of an EIP and reports which
rules (and therefore which client files) a spec change touches.

Scope, stated plainly: witnesses check *constants and simple derived values*.
They do not prove behavioural compliance; that remains the job of the LLM
analysis, EEST/hive and human review. Executable EEST-format witnesses are a
roadmap item, not part of this module.
"""

from __future__ import annotations

import ast
import hashlib
import operator
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

import yaml

RULES_DIR = Path(__file__).resolve().parent / "rules"

PASS, FAIL, INCOMPLETE, UNMAPPED = "PASS", "FAIL", "INCOMPLETE", "UNMAPPED"


# ------------------------------------------------------------------ values

_NAMED = {
    "BigInteger.ZERO": "0", "BigInteger.ONE": "1", "BigInteger.TWO": "2",
    "BigInteger.TEN": "10", "UInt256.Zero": "0", "UInt256.One": "1",
}
_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Pow: operator.pow, ast.LShift: operator.lshift, ast.FloorDiv: operator.floordiv}


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        left, right = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, (ast.Pow, ast.LShift)) and right > 512:
            raise ValueError("exponent too large")
        return _BIN[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_node(node.operand)
    raise ValueError(f"unsupported expression: {ast.dump(node)}")


def eval_literal(raw: str) -> Optional[int]:
    """Evaluate a numeric literal as written in a spec or in Java/Go/C# code.

    Supports ``2**17``, ``1 << 17``, ``8L``, ``1_000_000_000L``, ``0x0A``,
    ``Bytes1(0x03)``, ``Wei.of(1_000_000_000L)``, ``1.GWei``,
    ``BigInteger.ONE`` and ``BigInteger.valueOf(3)``. Returns None if the text
    is not a constant integer expression (fail-closed: never guess).
    """
    text = raw.strip().strip("`").strip()
    if text in _NAMED:
        text = _NAMED[text]
    m = re.fullmatch(r"(\d+)\.GWei", text)
    if m:
        return int(m.group(1)) * 10**9
    for _ in range(3):  # unwrap Bytes1(..), Wei.of(..), BigInteger.valueOf(..), (ulong)..
        m = re.fullmatch(r"(?:Bytes\d+|Wei\.of|BigInteger\.valueOf|UInt256|uint64|big\.NewInt)\((.*)\)", text)
        if not m:
            break
        text = m.group(1).strip()
    text = re.sub(r"^\((?:ulong|long|int|uint)\)\s*", "", text)
    text = re.sub(r"(?<=[0-9a-fA-F])[lLuU]+\b", "", text)
    text = re.sub(r"\b(0[xX][0-9a-fA-F_]+|\d[\d_]*)", lambda mm: mm.group(1).replace("_", ""), text)
    try:
        value = _eval_node(ast.parse(text, mode="eval"))
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError):
        return None
    return value if isinstance(value, int) else None


# ------------------------------------------------------------------ spec

_TABLE_ROW = re.compile(r"^\|\s*`([A-Z][A-Z0-9_]+)`\s*\|\s*`?([^|`]+?)`?\s*\|")
_ASSIGN = re.compile(r"^([A-Z][A-Z0-9_]{2,})\s*=\s*([^#\n]+?)\s*(?:#.*)?$")


@dataclass
class SpecConstant:
    name: str
    raw: str
    value: Optional[int]
    line: int


def extract_spec_constants(spec_text: str) -> Dict[str, SpecConstant]:
    """Parameters from EIP markdown: ``| `NAME` | `value` |`` table rows and
    ``NAME = value`` lines (the style used inside EIP python blocks)."""
    out: Dict[str, SpecConstant] = {}
    for i, line in enumerate(spec_text.splitlines(), start=1):
        m = _TABLE_ROW.match(line.strip()) or _ASSIGN.match(line.strip())
        if m and m.group(1) not in out:
            raw = m.group(2).strip()
            out[m.group(1)] = SpecConstant(m.group(1), raw, eval_literal(raw), i)
    return out


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ rulebooks

def load_rulebook(eip: int, rules_dir: Path = RULES_DIR) -> dict:
    path = rules_dir / f"eip-{eip}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no witness rulebook for EIP-{eip} ({path})")
    with open(path, "r", encoding="utf-8") as fh:
        book = yaml.safe_load(fh)
    book.setdefault("rules", [])
    return book


def available_rulebooks(rules_dir: Path = RULES_DIR) -> List[int]:
    return sorted(int(p.stem.split("-")[1]) for p in rules_dir.glob("eip-*.yaml"))


@dataclass
class WitnessResult:
    rule_id: str
    eip: int
    client: str
    constant: str
    status: str
    expected: Optional[int] = None
    actual: Optional[int] = None
    spec_line: Optional[int] = None
    spec_raw: Optional[str] = None
    code_file: Optional[str] = None
    code_line: Optional[int] = None
    code_excerpt: Optional[str] = None
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


FileReader = Callable[[str], Optional[str]]


def dir_reader(root: Path, overrides: Optional[Dict[str, str]] = None) -> FileReader:
    """Read files from a local checkout; ``overrides`` replaces file contents
    in memory (used by the mutation scoreboard; the checkout is never edited)."""
    overrides = overrides or {}

    def read(rel: str) -> Optional[str]:
        if rel in overrides:
            return overrides[rel]
        p = root / rel
        try:
            return p.read_text(encoding="utf-8")
        except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError):
            return None
    return read


def _locate(text: str, pattern: str):
    m = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if not m:
        return None
    line = text.count("\n", 0, m.start(1)) + 1
    excerpt = text.splitlines()[line - 1].strip() if text else ""
    return m.group(1).strip(), line, excerpt


def check_rules(book: dict, spec_text: str, client: str, read: FileReader) -> List[WitnessResult]:
    """Check every rule of a rulebook against one client. Never returns PASS
    unless both the spec value and the code value were found and parsed."""
    spec = extract_spec_constants(spec_text)
    eip = int(book["eip"])
    code_values: Dict[str, int] = {}
    results: List[WitnessResult] = []

    # Two passes so rules can reference values found by other rules.
    rules = sorted(book["rules"], key=lambda r: 1 if (r.get("anchors", {}).get(client) or {}).get("multiply_by") else 0)
    for rule in rules:
        rid, const = rule["id"], rule["constant"]
        res = WitnessResult(rid, eip, client, const, INCOMPLETE)
        names = [const] + list(rule.get("aliases") or [])
        sc = next((spec[n] for n in names if n in spec), None)
        if sc is not None and sc.name != const:
            res.note = f"spec uses historical name {sc.name}; "
        if sc is None or sc.value is None:
            res.note = (f"constant {const} not found in this spec revision "
                        "(renamed or removed? see `prspec fork-watch`)") if sc is None else \
                       f"spec value {sc.raw!r} is not a constant integer expression"
            if sc:
                res.spec_line, res.spec_raw = sc.line, sc.raw
            results.append(res)
            continue
        res.expected, res.spec_line, res.spec_raw = sc.value, sc.line, sc.raw
        anchor = (rule.get("anchors") or {}).get(client)
        if not anchor:
            res.status, res.note = UNMAPPED, "no anchor for this client yet"
            results.append(res)
            continue
        res.code_file = anchor["file"]
        text = read(anchor["file"])
        if text is None:
            res.note = "anchor file missing from the checkout (sparse checkout or moved file)"
            results.append(res)
            continue
        found = _locate(text, anchor["pattern"])
        if not found:
            res.note = "anchor pattern not found (code moved or renamed): needs human review"
            results.append(res)
            continue
        raw, res.code_line, res.code_excerpt = found
        val = eval_literal(raw)
        if val is None:
            res.note = f"code value {raw!r} is not a constant integer expression"
            results.append(res)
            continue
        if anchor.get("multiply_by"):
            other = code_values.get(anchor["multiply_by"])
            if other is None:
                res.note = f"depends on {anchor['multiply_by']}, which was not resolved"
                results.append(res)
                continue
            val *= other
            res.note += f"code value = {raw} x {anchor['multiply_by']} ({other})"
        res.actual = val
        code_values[const] = val
        res.status = PASS if val == sc.value else FAIL
        results.append(res)
    order = {r["id"]: i for i, r in enumerate(book["rules"])}
    return sorted(results, key=lambda r: order[r.rule_id])


def summarize(results: List[WitnessResult]) -> Dict[str, int]:
    out = {PASS: 0, FAIL: 0, INCOMPLETE: 0, UNMAPPED: 0}
    for r in results:
        out[r.status] += 1
    return out


def git_head(path: Path) -> Optional[str]:
    try:
        sha = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"],
                                      text=True, stderr=subprocess.DEVNULL).strip()
        dirty = subprocess.check_output(["git", "-C", str(path), "status", "--porcelain",
                                         "--untracked-files=no"], text=True,
                                        stderr=subprocess.DEVNULL).strip()
        return sha + ("-dirty" if dirty else "")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


# ------------------------------------------------------------------ spec I/O

def load_spec_text(eip: int, ref: str, eips_dir: Optional[Path] = None,
                   spec_file: Optional[Path] = None, timeout: int = 30) -> str:
    """EIP markdown at an exact revision: a file, a local ethereum/EIPs checkout
    (``git show ref:EIPS/eip-N.md``) or raw.githubusercontent.com."""
    if spec_file:
        return Path(spec_file).read_text(encoding="utf-8")
    rel = f"EIPS/eip-{eip}.md"
    if eips_dir:
        return subprocess.check_output(["git", "-C", str(eips_dir), "show", f"{ref}:{rel}"], text=True)
    import requests
    url = f"https://raw.githubusercontent.com/ethereum/EIPs/{ref}/{rel}"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


# ------------------------------------------------------------------ Fork Watch

@dataclass
class ConstantChange:
    kind: str            # changed | added | removed | renamed
    name: str
    old: Optional[str] = None
    new: Optional[str] = None
    new_name: Optional[str] = None
    rules: List[str] = field(default_factory=list)
    impacted_files: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def fork_watch(old_text: str, new_text: str, book: Optional[dict] = None) -> List[ConstantChange]:
    """Parameter-level diff of two EIP revisions, mapped to witness rules.

    A removed + added pair with the same value is reported as ``renamed``
    (a rename silently breaks any tooling keyed on the old name)."""
    old, new = extract_spec_constants(old_text), extract_spec_constants(new_text)
    changes: List[ConstantChange] = []
    removed = [n for n in old if n not in new]
    added = [n for n in new if n not in old]
    for n in old:
        if n in new and old[n].raw != new[n].raw and old[n].value != new[n].value:
            changes.append(ConstantChange("changed", n, old[n].raw, new[n].raw))
    used_added = set()
    for n in removed:
        same = [a for a in added if a not in used_added and new[a].value is not None
                and new[a].value == old[n].value]
        if len(same) == 1:
            used_added.add(same[0])
            changes.append(ConstantChange("renamed", n, old[n].raw, new[same[0]].raw, new_name=same[0]))
        else:
            changes.append(ConstantChange("removed", n, old[n].raw))
    for a in added:
        if a not in used_added:
            changes.append(ConstantChange("added", a, None, new[a].raw))
    if book:
        for ch in changes:
            for rule in book.get("rules", []):
                names = [rule["constant"]] + list(rule.get("aliases") or [])
                if ch.name in names or (ch.new_name and ch.new_name in names):
                    ch.rules.append(rule["id"])
                    for client, anchor in (rule.get("anchors") or {}).items():
                        ch.impacted_files[client] = anchor["file"]
    return changes


# ------------------------------------------------------------------ reports

_ICON = {PASS: "✅", FAIL: "❌", INCOMPLETE: "⚠️", UNMAPPED: "⚪"}


def render_witness_md(eip: int, spec_ref: str, spec_sha: str,
                      by_client: Dict[str, List[WitnessResult]],
                      commits: Dict[str, Optional[str]]) -> str:
    clients = list(by_client)
    lines = [f"# PRSpec witness matrix: EIP-{eip}", "",
             f"- Spec: `ethereum/EIPs@{spec_ref}` (`EIPS/eip-{eip}.md`, sha256 `{spec_sha[:16]}…`)"]
    for c in clients:
        lines.append(f"- {c}: `{commits.get(c) or 'unknown commit'}`")
    lines += ["", "Deterministic check (no LLM): spec constant vs. the value found at the "
              "client anchor. ✅ match · ❌ mismatch · ⚠️ could not check (fail-closed) · "
              "⚪ no anchor yet.", "",
              "| Rule | Spec constant | Spec value | " + " | ".join(clients) + " |",
              "| --- | --- | --- | " + " | ".join("---" for _ in clients) + " |"]
    rows = {r.rule_id: r for r in by_client[clients[0]]} if clients else {}
    for rid, first in rows.items():
        cells = []
        for c in clients:
            r = next(x for x in by_client[c] if x.rule_id == rid)
            cell = _ICON[r.status]
            if r.status == FAIL:
                cell += f" `{r.actual}`"
            cells.append(cell)
        lines.append(f"| `{rid}` | `{first.constant}` | `{first.spec_raw}` | " + " | ".join(cells) + " |")
    lines += ["", "## Evidence", ""]
    for c in clients:
        for r in by_client[c]:
            if r.status in (PASS, UNMAPPED):
                continue
            lines.append(f"- **{c} · {r.rule_id} · {r.status}**: spec line {r.spec_line} "
                         f"`{r.constant} = {r.spec_raw}` (= {r.expected}); code "
                         f"`{r.code_file}:{r.code_line}` → `{r.code_excerpt}` (= {r.actual}). {r.note}")
    if lines[-1] == "":
        lines.append("All mapped rules match.")
    lines += ["", "Limits: constants and simple derived values only; a ✅ is not a proof of "
              "behavioural compliance. Anchors are reviewed against the commits listed in the "
              "rulebook; a moved constant shows as ⚠️, never as ✅."]
    return "\n".join(lines) + "\n"


def render_fork_watch_md(eip: int, old_ref: str, new_ref: str,
                         changes: List[ConstantChange],
                         checks: Optional[Dict[str, List[WitnessResult]]] = None) -> str:
    lines = [f"# Fork Watch impact card: EIP-{eip}", "",
             f"Spec revisions: `{old_ref}` → `{new_ref}` (ethereum/EIPs)", ""]
    if not changes:
        lines.append("No parameter-level change between these revisions.")
    else:
        lines += ["| Change | Constant | Old | New | Witness rules | Client files to review |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for ch in changes:
            name = f"`{ch.name}`" + (f" → `{ch.new_name}`" if ch.new_name else "")
            files = "<br>".join(f"{c}: `{f}`" for c, f in ch.impacted_files.items()) or "— (no rule yet)"
            lines.append(f"| {ch.kind} | {name} | `{ch.old or ''}` | `{ch.new or ''}` | "
                         f"{', '.join(ch.rules) or '—'} | {files} |")
    if checks:
        lines += ["", "## Clients checked against the new revision", ""]
        for client, results in checks.items():
            s = summarize(results)
            lines.append(f"- **{client}**: {s[PASS]} ✅ · {s[FAIL]} ❌ · {s[INCOMPLETE]} ⚠️ · {s[UNMAPPED]} ⚪")
            for r in results:
                if r.status in (FAIL, INCOMPLETE):
                    lines.append(f"  - {_ICON[r.status]} `{r.rule_id}`: spec {r.expected}, code "
                                 f"{r.actual} at `{r.code_file}:{r.code_line}` {r.note}")
    lines += ["", "Parameter-level only: prose/algorithm changes in the EIP are not detected "
              "here; they are what the LLM analysis and human review are for."]
    return "\n".join(lines) + "\n"
