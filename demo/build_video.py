#!/usr/bin/env python3
"""Build the PRSpec 2.0 demo video from raw evidence files.

Every number and table on screen is read from an artifact under docs/evidence/
(nothing is typed in by hand). Without --live, the Gemini frame says the live run
has not happened and the output is named *-preliminary.mp4.

    python demo/build_video.py                                   # preliminary cut
    python demo/build_video.py --live docs/evidence/<date>/gemini-live   # final cut

Needs: playwright (python) + a Chromium binary, ffmpeg.
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / "docs/evidence/2026-11-10"
W, H = 1920, 1080

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:1920px;height:1080px;background:#191919;color:#fff;font-family:'Noto Sans','Liberation Sans',Arial,sans-serif;
 padding:96px 128px;display:flex;flex-direction:column;gap:40px;overflow:hidden}
.kicker{font-size:28px;letter-spacing:.08em;text-transform:uppercase;color:#5E9FE8;font-weight:600}
h1{font-size:76px;line-height:1.1;font-weight:700;max-width:1500px}
h2{font-size:56px;line-height:1.15;font-weight:700;max-width:1600px}
p,li{font-size:34px;line-height:1.45;color:rgba(255,255,255,.80);max-width:1550px}
ul{padding-left:40px;display:flex;flex-direction:column;gap:14px}
.mono{font-family:'Liberation Mono',Menlo,Consolas,monospace}
.small{font-size:24px;color:rgba(255,255,255,.62)}
.foot{margin-top:auto;font-size:22px;color:rgba(255,255,255,.55)}
table{border-collapse:collapse;font-size:27px;width:100%}
th,td{border-bottom:1px solid rgba(255,255,255,.16);padding:12px 16px;text-align:left;vertical-align:top}
th{color:rgba(255,255,255,.65);font-weight:600;font-size:23px;text-transform:uppercase;letter-spacing:.04em}
td.c{text-align:center}
.ok{color:#72BC8F;font-weight:700}.bad{color:#E97366;font-weight:700}.warn{color:#DE9255;font-weight:700}.na{color:rgba(255,255,255,.45)}
.cards{display:flex;gap:32px}.card{flex:1;background:#202020;border:1px solid rgba(255,255,255,.14);border-radius:12px;padding:36px}
.big{font-size:96px;font-weight:700;line-height:1}.lbl{font-size:26px;color:rgba(255,255,255,.65);margin-top:12px}
.term{background:#0f0f0f;border:1px solid rgba(255,255,255,.14);border-radius:12px;padding:32px 36px;font-size:25px;line-height:1.5;
 font-family:'Liberation Mono',Menlo,monospace;color:#e6e6e6;white-space:pre-wrap}
table.dense{font-size:24px}table.dense th,table.dense td{padding:7px 16px}table.dense th{font-size:20px}
.tag{display:inline-block;border:1px solid rgba(255,255,255,.3);border-radius:8px;padding:4px 14px;font-size:22px;margin-right:10px}
"""

ICON = {"PASS": ('<span class="ok">✓ match</span>'), "FAIL": None,
        "INCOMPLETE": '<span class="warn">⚠ incomplete</span>', "UNMAPPED": '<span class="na">○ no anchor</span>'}


def esc(x):
    return html.escape(str(x))


def page(body: str, foot: str = "") -> str:
    f = f'<div class="foot">{foot}</div>' if foot else ""
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}{f}</body></html>"


def load(p: Path):
    return json.loads(p.read_text())


def cell(r):
    if r["status"] == "FAIL":
        return f'<span class="bad">✗ {esc(r["actual"])}</span>'
    return ICON[r["status"]]


def frames(live: Path | None):
    w1559, w4844 = load(EV / "witness-1559.json"), load(EV / "witness-4844.json")
    old = load(EV / "witness-4844-at-2511e0bc-parent.json")
    fw = load(EV / "fork-watch-4844-2511e0bc.json")
    hist = load(EV / "eip-4844-history.json")
    wit = load(EV / "scoreboard-dry-run/witness.json")
    clients = list(w4844["results"])
    short = {c: (w4844["commits"][c] or "")[:8] for c in clients}
    out = []

    out.append((page(
        '<div class="kicker">PRSpec 2.0 · Ethereum execution clients</div>'
        '<h1>Does the client code match the EIP text it implements?</h1>'
        '<p>Reproducible spec-to-code evidence for Besu, go-ethereum and Nethermind: '
        'deterministic checks, Fork Watch, and provider-flexible LLM-assisted analysis.</p>',
        "Every table in this video is rendered from raw output files in docs/evidence/. Nothing is typed in by hand."), 6))

    out.append((page(
        '<div class="kicker">The problem</div><h2>Specs keep moving after clients implement them</h2>'
        f'<div class="cards"><div class="card"><div class="big">{hist["commits_touching_text"]}</div>'
        f'<div class="lbl">commits to the EIP-4844 text ({esc(hist["first"][:7])} → {esc(hist["last"][:7])})</div></div>'
        f'<div class="card"><div class="big">{hist["commits_changing_parameter_table"]}</div>'
        '<div class="lbl">of them changed the parameter table: values, names, types</div></div>'
        '<div class="card"><div class="big">3</div><div class="lbl">clients, 3 languages, '
        'each change has to be found in each codebase</div></div></div>'
        '<p>A client can be correct against last month\'s spec and wrong against today\'s. '
        'Reviewers need to know <b>which rules changed</b> and <b>where in their code</b> to look.</p>',
        "Source: git log -- EIPS/eip-4844.md in ethereum/EIPs (eip-4844-history.json)"), 8))

    rows = ""
    for book in (w1559, w4844):
        rids = [r["rule_id"] for r in book["results"][clients[0]]]
        for i, rid in enumerate(rids):
            r0 = book["results"][clients[0]][i]
            cells = "".join(f'<td class="c">{cell(book["results"][c][i])}</td>' for c in clients)
            rows += f'<tr><td class="mono">{esc(r0["constant"])}</td><td class="mono">{esc(r0["spec_raw"])}</td>{cells}</tr>'
    tot = {k: sum(b["summary"][c][k] for b in (w1559, w4844) for c in clients) for k in ("PASS", "FAIL", "INCOMPLETE", "UNMAPPED")}
    out.append((page(
        '<div class="kicker">Layer 1 · Deterministic witness · no LLM, no API key</div>'
        f'<h2>{tot["PASS"]} checks match, {tot["FAIL"]} mismatch, {tot["INCOMPLETE"]} incomplete, '
        f'{tot["UNMAPPED"]} without an anchor</h2>'
        '<table class="dense"><tr><th>Spec constant (EIP-1559, EIP-4844)</th><th>Spec value</th>'
        + "".join(f"<th>{esc(c)} {esc(short[c])}</th>" for c in clients) + f"</tr>{rows}</table>",
        f"prspec witness · spec ethereum/EIPs@{w4844['spec_ref'][:8]} · values read from client source at the anchored file:line · "
        "a moved constant shows ⚠, never ✓"), 11))

    ch_rows = "".join(
        f'<tr><td>{esc(c["kind"])}</td><td class="mono">{esc(c["name"])}</td><td class="mono">{esc(c["old"])}</td>'
        f'<td class="mono">{esc(c["new"])}</td><td class="mono small">{"<br>".join(esc(Path(f).name) for f in c["impacted_files"].values())}</td></tr>'
        for c in fw["changes"])
    out.append((page(
        '<div class="kicker">Layer 2 · Fork Watch</div>'
        '<h2>A real spec change → the rules and files to review</h2>'
        f'<p>EIPs commit <span class="mono">{esc(fw["to"])}</span> (June 2023, "Increase Blob Throughput"):</p>'
        '<table><tr><th>Change</th><th>Constant</th><th>Old</th><th>New</th><th>Files (Besu · Geth · Nethermind)</th></tr>'
        f'{ch_rows}</table>',
        "prspec fork-watch --eip 4844 --from 2511e0bc^ --to 2511e0bc · parameter-level only; prose changes are not detected by this layer"), 10))

    fails = []
    for c in clients:
        for r in old["results"][c]:
            if r["status"] == "FAIL":
                fails.append((c, r))
    frows = "".join(
        f'<tr><td>{esc(c)}</td><td class="mono">{esc(r["constant"])}</td><td class="mono">{esc(r["expected"])}</td>'
        f'<td class="mono bad">{esc(r["actual"])}</td><td class="mono small">{esc(Path(r["code_file"]).name)}:{esc(r["code_line"])}</td></tr>'
        for c, r in fails)
    out.append((page(
        '<div class="kicker">Spec-drift replay</div>'
        f'<h2>Today\'s clients vs. the spec before that commit: exactly {len({r["constant"] for _, r in fails})} constants fail, in all {len(clients)} clients</h2>'
        '<table><tr><th>Client</th><th>Constant</th><th>Old spec</th><th>Code</th><th>Where</th></tr>' + frows + '</table>',
        "Direction matters: this shows the mechanism pinpoints a spec change. It is not a claim that PRSpec caught a historical client bug."), 11))

    caught = [k for k, v in wit.items() if v["outcome"] == "caught"]
    rest = [k for k, v in wit.items() if v["outcome"] != "caught"]
    out.append((page(
        '<div class="kicker">Besu pilot · pre-registered mutation scoreboard</div>'
        f'<h2>10 realistic deviations injected into Besu {esc(short.get("besu", ""))}: witnesses catch {len(caught)}</h2>'
        f'<div class="cards"><div class="card"><div class="big ok">{len(caught)}/10</div>'
        f'<div class="lbl">caught deterministically, with file:line<br><span class="mono">{" ".join(caught)}</span>: constant changes</div></div>'
        f'<div class="card"><div class="big warn">{len(rest)}/10</div>'
        f'<div class="lbl">invisible to constant checks<br><span class="mono">{" ".join(rest)}</span>: removed max(1,…), rounding, '
        'off-by-one in fake_exponential, flipped sign, fork-block base fee</div></div></div>'
        '<p>The second group is what the semantic layer is for, and what the LLM layer is measured on.</p>',
        "Criteria fixed in pilot/besu/mutations.yaml before any run · mutated in memory; the Besu checkout is never edited"), 10))

    out.append((live_frame(live), 12))

    out.append((page(
        '<div class="kicker">Limits, stated plainly</div><h2>What this does not show</h2><ul>'
        '<li>Witnesses check constants and simple derived values. A ✓ is not proof of behavioural compliance.</li>'
        '<li>EIP-4844 witnesses check Cancun values; Prague/BPO blob schedules are not modelled yet.</li>'
        '<li>LLM findings are candidates for human review; the verification score is an internal vote, not a probability.</li>'
        '<li>Executable EEST witnesses verified on EELS are on the roadmap, not built.</li>'
        '<li>Not yet run inside a client team\'s CI.</li></ul>'), 10))

    out.append((page(
        '<div class="kicker">Try it · MIT licensed</div><h2>One command, no key, your own checkout</h2>'
        '<div class="term">$ pip install git+https://github.com/Fosurero/PRSpec\n'
        '$ prspec witness --eip 4844 -t besu=../besu -t nethermind=../nethermind\n'
        '$ prspec fork-watch --eip 4844 --from &lt;old&gt; --to &lt;new&gt; --check besu=../besu\n'
        '$ prspec --no-cloud analyze --provider local --eip 1559 --client besu --source-dir ../besu</div>'
        '<p>Useful next step for a client team: run it on one PR and tell us whether it saved review time or added noise.</p>'
        '<p class="small">github.com/Fosurero/PRSpec · roadmap and funding milestones in ROADMAP.md</p>'), 10))
    return out


PROVIDER_LABEL = {"gemini": "Gemini", "meta": "Meta Muse", "openai": "OpenAI", "local": "Local model"}


def live_frame(live: Path | None) -> str:
    if not live or not (live / "scoreboard" / "scoreboard.json").exists():
        return page('<div class="kicker">Layer 3 · Gemini semantic analysis</div>'
                    '<h2>Live run: not executed yet</h2>'
                    '<p>The live experiment runs in GitHub Actions with the repository secret '
                    '(<span class="mono">.github/workflows/gemini-live.yml</span>). This preliminary cut shows no Gemini numbers, '
                    'because none exist yet.</p>', "PRELIMINARY CUT · do not share")
    sb = load(live / "scoreboard" / "scoreboard.json")
    probe = {}
    if (live / "probe.json").exists():
        try:
            probe = json.loads((live / "probe.json").read_text().strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            probe = {}
    m = sb["manifest"]
    label = PROVIDER_LABEL.get(m.get("provider"), str(m.get("provider")))
    counts = sb.get("counts", {})
    rows = "".join(
        f'<tr><td class="mono">{esc(r["id"])}</td><td>{esc(r["title"])}</td>'
        f'<td class="{"ok" if r["outcome"] in ("confirmed", "flagged") else "bad" if r["outcome"] == "missed" else "warn"}">{esc(r["outcome"])}</td>'
        f'<td>{esc(r.get("witness"))}</td></tr>' for r in sb["rows"])
    tok = sb.get("tokens_primary_pass", {})
    warn = ('<p class="bad">INCOMPLETE RUN: at least one call failed. These numbers are partial.</p>'
            if sb.get("incomplete") else "")
    warn += ('<p class="small">Pre-registered rules: confirmed = matching issue upheld by verification; flagged = matching issue, '
             'not upheld; inconclusive = the clean baseline already raised a matching issue, so the hit is not counted.</p>')
    return page(
        f'<div class="kicker">Layer 3 · {esc(label)} semantic analysis · live run</div>'
        f'<h2>{esc(m.get("model"))}: ' + ", ".join(f"{esc(k)} {v}" for k, v in sorted(counts.items())) + '</h2>'
        + warn +
        f'<table class="dense"><tr><th>ID</th><th>Mutation</th><th>{esc(label)} outcome</th><th>Witness</th></tr>' + rows + '</table>',
        f"model_version {esc(probe.get('model_version', m.get('model')))} · tokens (primary pass) in {esc(tok.get('prompt_token_count', 'n/a'))} / out {esc(tok.get('candidates_token_count', 'n/a'))} · "
        f"wall {esc(sb.get('wall_seconds'))} s · baseline candidates for triage: {len(sb.get('baseline_issue_candidates', []))} · "
        f"raw JSON in {esc(live.relative_to(ROOT) if live.is_relative_to(ROOT) else live)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=ROOT / "demo/out")
    ap.add_argument("--fade", type=float, default=0.5)
    a = ap.parse_args()
    live = a.live.resolve() if a.live else None
    final = bool(live and (live / "scoreboard" / "scoreboard.json").exists())
    fdir = a.out / "frames"
    if fdir.exists():
        shutil.rmtree(fdir)
    fdir.mkdir(parents=True)
    fr = frames(live)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=shutil.which("chromium") or None, args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": W, "height": H})
        for i, (doc, _) in enumerate(fr):
            (fdir / f"{i:02d}.html").write_text(doc, encoding="utf-8")
            pg.set_content(doc, wait_until="load")
            pg.screenshot(path=str(fdir / f"{i:02d}.png"))
        b.close()
    provider = load(live / "scoreboard" / "scoreboard.json")["manifest"].get("provider") if final else None
    # Name each evidence-backed cut after its provider.
    name = ("prspec-2.0-demo.mp4" if provider == "gemini" else f"prspec-2.0-demo-{provider}.mp4") if final \
        else "prspec-2.0-demo-preliminary.mp4"
    dst = a.out / name
    inputs, filt, last = [], [], None
    offset = 0.0
    for i, (_, dur) in enumerate(fr):
        inputs += ["-loop", "1", "-t", str(dur), "-i", str(fdir / f"{i:02d}.png")]
    for i in range(len(fr)):
        filt.append(f"[{i}:v]format=yuv420p,fps=30,setsar=1[v{i}]")
    last = "v0"
    offset = fr[0][1] - a.fade
    for i in range(1, len(fr)):
        nxt = f"x{i}"
        filt.append(f"[{last}][v{i}]xfade=transition=fade:duration={a.fade}:offset={offset:.2f}[{nxt}]")
        last = nxt
        offset += fr[i][1] - a.fade
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
           "-map", f"[{last}]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-movflags", "+faststart", str(dst)]
    subprocess.run(cmd, check=True)
    print(f"{dst} ({('final' if provider == 'gemini' else f'{provider} results') if final else 'PRELIMINARY: no live LLM results'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
