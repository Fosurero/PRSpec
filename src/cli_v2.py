"""PRSpec 2.0 commands: witness, fork-watch, models.

Registered on the main ``cli`` group by ``src.cli``.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Optional

import click

from . import witness as W
from .cli import EXIT_FINDINGS, EXIT_INCOMPLETE, EXIT_OK, cli


def _targets(values) -> Dict[str, Path]:
    out = {}
    for v in values:
        if "=" not in v:
            raise click.BadParameter(f"expected CLIENT=DIR, got {v!r}")
        client, d = v.split("=", 1)
        p = Path(d).expanduser()
        if not p.is_dir():
            raise click.BadParameter(f"{d} is not a directory")
        out[client.strip()] = p
    return out


def _spec(eip, ref, eips_dir, spec_file):
    try:
        return W.load_spec_text(eip, ref, eips_dir=Path(eips_dir) if eips_dir else None,
                                spec_file=Path(spec_file) if spec_file else None)
    except Exception as e:  # noqa: BLE001
        raise click.ClickException(f"could not load EIP-{eip} at {ref}: {e}")


def _write(path: Optional[str], text: str):
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text, encoding="utf-8")
        click.echo(f"wrote {path}", err=True)


@cli.command()
@click.option('--eip', '-e', type=int, required=True, help='EIP with a rulebook (see --list)')
@click.option('--target', '-t', 'targets', multiple=True, metavar='CLIENT=DIR',
              help='Client checkout to check, e.g. besu=../besu (repeatable)')
@click.option('--spec-ref', default=None, help='ethereum/EIPs revision (default: rulebook pin)')
@click.option('--eips-dir', default=None, type=click.Path(exists=True, file_okay=False),
              help='Local ethereum/EIPs checkout (offline, uses git show)')
@click.option('--spec-file', default=None, type=click.Path(exists=True, dir_okay=False))
@click.option('--json', 'json_out', default=None, help='Write results as JSON')
@click.option('--markdown', 'md_out', default=None, help='Write the witness matrix as Markdown')
@click.option('--fail-on', type=click.Choice(["never", "incomplete", "findings"]),
              default='findings', show_default=True)
@click.option('--list', 'list_only', is_flag=True, help='List rules and exit')
def witness(eip, targets, spec_ref, eips_dir, spec_file, json_out, md_out, fail_on, list_only):
    """Deterministic spec witnesses: check EIP constants in client code (no LLM).

    Exit codes: 0 all mapped rules match, 10 a mismatch (❌), 20 a rule could
    not be checked (⚠️, fail-closed)."""
    book = W.load_rulebook(eip)
    if list_only:
        for r in book["rules"]:
            click.echo(f"{r['id']:28} {r['constant']:34} clients: {', '.join(r.get('anchors', {}))}")
        return
    tg = _targets(targets)
    if not tg:
        raise click.UsageError("give at least one --target CLIENT=DIR")
    ref = spec_ref or book["spec"]["pinned_ref"]
    text = _spec(eip, ref, eips_dir, spec_file)
    by_client, commits = {}, {}
    for client, d in tg.items():
        by_client[client] = W.check_rules(book, text, client, W.dir_reader(d))
        commits[client] = W.git_head(d)
    sha = W.sha256_text(text)
    md = W.render_witness_md(eip, ref, sha, by_client, commits)
    click.echo(md)
    payload = {"eip": eip, "spec_ref": ref, "spec_sha256": sha, "commits": commits,
               "results": {c: [r.to_dict() for r in rs] for c, rs in by_client.items()},
               "summary": {c: W.summarize(rs) for c, rs in by_client.items()}}
    _write(json_out, json.dumps(payload, indent=2))
    _write(md_out, md)
    fails = sum(s[W.FAIL] for s in payload["summary"].values())
    incomplete = sum(s[W.INCOMPLETE] for s in payload["summary"].values())
    if fail_on != "never" and incomplete:
        sys.exit(EXIT_INCOMPLETE)
    if fail_on == "findings" and fails:
        sys.exit(EXIT_FINDINGS)
    sys.exit(EXIT_OK)


@cli.command(name="fork-watch")
@click.option('--eip', '-e', type=int, required=True)
@click.option('--from', 'from_ref', required=True, help='Old ethereum/EIPs revision')
@click.option('--to', 'to_ref', required=True, help='New ethereum/EIPs revision')
@click.option('--eips-dir', default=None, type=click.Path(exists=True, file_okay=False))
@click.option('--check', 'targets', multiple=True, metavar='CLIENT=DIR',
              help='Also run the witnesses at --to against these checkouts')
@click.option('--json', 'json_out', default=None)
@click.option('--markdown', 'md_out', default=None)
def fork_watch(eip, from_ref, to_ref, eips_dir, targets, json_out, md_out):
    """Impact card for a spec change: which constants changed, which witness
    rules and which client files it touches. Exit 10 if a checked client
    disagrees with the new revision, 20 if a check was incomplete."""
    try:
        book = W.load_rulebook(eip)
    except FileNotFoundError:
        book = None
    old = _spec(eip, from_ref, eips_dir, None)
    new = _spec(eip, to_ref, eips_dir, None)
    changes = W.fork_watch(old, new, book)
    checks = {}
    if book:
        for client, d in _targets(targets).items():
            checks[client] = W.check_rules(book, new, client, W.dir_reader(d))
    md = W.render_fork_watch_md(eip, from_ref, to_ref, changes, checks or None)
    click.echo(md)
    payload = {"eip": eip, "from": from_ref, "to": to_ref,
               "from_sha256": W.sha256_text(old), "to_sha256": W.sha256_text(new),
               "changes": [c.to_dict() for c in changes],
               "checks": {c: [r.to_dict() for r in rs] for c, rs in checks.items()}}
    _write(json_out, json.dumps(payload, indent=2))
    _write(md_out, md)
    statuses = [r.status for rs in checks.values() for r in rs]
    if W.INCOMPLETE in statuses:
        sys.exit(EXIT_INCOMPLETE)
    if W.FAIL in statuses:
        sys.exit(EXIT_FINDINGS)


@cli.command()
@click.option('--probe', default=None, metavar='MODEL',
              help='Send one tiny JSON request to MODEL and report latency/model version')
@click.option('--filter', 'name_filter', default='gemini', show_default=True)
def models(probe, name_filter):
    """List the Gemini models the configured GEMINI_API_KEY can call.

    Listing a model does not prove inference is allowed (quota, billing,
    free-tier eligibility); use --probe for that. The key is never printed."""
    import time

    from .analyzer import GeminiAnalyzer
    from .config import Config
    cfg = Config()
    try:
        key = cfg.gemini_api_key
    except ValueError as e:
        raise click.ClickException(str(e))
    an = GeminiAnalyzer(api_key=key, model=probe or cfg.gemini_config["model"], max_retries=1)
    try:
        names = [m for m in an.list_models() if name_filter in m]
    except Exception as e:  # noqa: BLE001
        raise click.ClickException(f"model listing failed: {type(e).__name__}: {e}")
    for n in names:
        click.echo(n)
    click.echo(f"{len(names)} model(s) matching '{name_filter}'", err=True)
    if probe:
        t = time.time()
        try:
            resp = an.generate('Return exactly this JSON: {"ok": true}')
        except Exception as e:  # noqa: BLE001
            raise click.ClickException(f"probe {probe} failed: {type(e).__name__}: {e}")
        meta = an._response_meta(resp, t)
        click.echo(json.dumps({"probe_model": probe, "text": (resp.text or "")[:80], **meta}))
