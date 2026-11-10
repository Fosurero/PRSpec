#!/usr/bin/env python3
"""Build an offline HTML report from the recorded PR #5786 results."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
E = ROOT / 'docs/evidence/2026-11-10/besu-pr5786'
esc = lambda x: html.escape(str(x))  # noqa: E731


def main():
    before = json.loads((E / 'before.json').read_text())
    after = json.loads((E / 'after.json').read_text())
    m = json.loads((E / 'manifest-focused.json').read_text())
    issue = before['issues'][0]
    diff = (E / 'real-change.diff').read_text()
    result = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PRSpec · Besu PR #5786 historical replay</title><style>
:root{{color-scheme:light dark;--bg:#fff;--text:#2c2c2b;--muted:#62615e;--line:#e6e5e3;--panel:#f9f8f7;--accent:#165ea8;--soft:#e5f2fc}}
@media(prefers-color-scheme:dark){{:root{{--bg:#191919;--text:#fff;--muted:#c5c5c5;--line:#505050;--panel:#202020;--accent:#8bc3fa;--soft:#22313e}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;overflow-wrap:anywhere}}
main{{max-width:1020px;margin:auto;padding:44px 32px 80px}}a{{color:var(--accent)}}a:focus-visible{{outline:3px solid var(--accent);outline-offset:3px}}
h1{{font-size:clamp(30px,5vw,44px);line-height:1.15;margin:12px 0 14px;letter-spacing:-.025em}}h2{{font-size:24px;line-height:1.25;margin:42px 0 12px}}h3{{font-size:18px;margin:0 0 8px}}
p{{margin:0 0 16px;max-width:78ch}}.eyebrow{{color:var(--accent);font-size:14px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}}
.lead{{font-size:19px;max-width:70ch}}.notice{{background:var(--soft);padding:18px 20px;border-left:4px solid var(--accent);border-radius:8px;margin:24px 0}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:24px 0}}.card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:20px}}
.card p{{margin:4px 0}}.tag{{font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}}.metric{{font-size:25px;font-weight:700}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px;line-height:1.5;font:14px/1.5 ui-monospace,Consolas,monospace}}
code{{font:0.91em ui-monospace,Consolas,monospace;overflow-wrap:anywhere}}.meta{{color:var(--muted);font-size:14px}}.result{{border-left:4px solid var(--accent);padding:6px 0 6px 20px;margin:20px 0}}ul{{padding-left:22px}}li{{margin:7px 0}}
@media(max-width:600px){{main{{padding:26px 18px 56px}}.grid{{grid-template-columns:1fr}}pre{{font-size:13px}}}}
</style></head><body><main>
<div class="eyebrow">PRSpec / Besu · Historical replay</div>
<h1>One real Besu fix, replayed</h1>
<p class="lead">Can a focused PRSpec analysis surface a known EIP-4844 mismatch before the fix, and stop flagging it after?</p>
<div class="notice"><strong>What this is:</strong> a retrospective test on a public Besu change already found and fixed by its contributors. Not a new discovery, a CI run, or proof of full compliance.</div>
<div class="grid"><section class="card"><div class="tag">Before the fix · {esc(before['besu_commit'][:8])}</div><p class="metric">{esc(len(before['issues']))} candidate finding</p><p>Model status: {esc(before['status'])}</p></section>
<section class="card"><div class="tag">After the fix · {esc(after['besu_commit'][:8])}</div><p class="metric">{esc(len(after['issues']))} candidate findings</p><p>Model status: {esc(after['status'])}</p></section></div>
<p class="meta">Meta {esc(m['model'])} · 3 source files per version · selected EIP excerpt · no automated verification</p>
<h2>The rule and the finding</h2><p>EIP-4844 calculates the new header’s excess blob gas from the <strong>parent header</strong>, not the block being built.</p>
<pre>{esc(issue['spec_reference'])}</pre>
<div class="result"><h3>What the model flagged before the fix</h3><p><strong>Location:</strong> <code>{esc(issue['code_location'])}</code></p><p>{esc(issue['description'])}</p><p><strong>Suggested fix:</strong> {esc(issue['suggestion'])}</p></div>
<h2>The actual Besu change</h2><p>Besu replaced the current-block calculation with the parent-header helper. This patch is from the real published PR, not a mutation created for the demo.</p>
<pre>{esc(diff)}</pre>
<h2>Reproduce or inspect</h2><p>Run the saved-result walkthrough without an API key from the PRSpec repository root:</p><pre>python pilot/besu/replay_pr5786.py</pre>
<p>Use <code>--live</code> with pinned Besu and EIPs checkouts to repeat two billable Meta calls; see the <a href="https://github.com/Fosurero/PRSpec/blob/main/pilot/besu/DEMO.md">run instructions</a>. Model responses may differ.</p>
<p><a href="https://github.com/Fosurero/PRSpec/blob/main/docs/evidence/2026-11-10/besu-pr5786/before.json">Before: raw JSON</a> · <a href="https://github.com/Fosurero/PRSpec/blob/main/docs/evidence/2026-11-10/besu-pr5786/after.json">After: raw JSON</a> · <a href="https://github.com/Fosurero/PRSpec/blob/main/docs/evidence/2026-11-10/besu-pr5786/manifest-focused.json">Test inputs</a> · <a href="https://github.com/besu-eth/besu/pull/5786">Besu PR #5786</a></p>
<h2>Limitations and next step</h2><ul><li>One historical case, selected with knowledge of its fix; the model may have encountered public data during training.</li><li>The run compares a selected rule and combined file context; it is not the existing generic CI workflow. No Besu runtime, EELS or automated verification was run.</li><li>Real PR trials, human review of false positives, and client-team CI integration are future work that funding can support.</li></ul>
</main></body></html>'''
    (E / 'report.html').write_text(result, encoding='utf-8')
    print(E / 'report.html')


if __name__ == '__main__':
    main()
