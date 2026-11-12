# Live demo recorder (fork only)

Records PRSpec analysing real Besu code on a GitHub-hosted runner, as a real
screen capture: a virtual display (Xvfb) is captured in real time by `ffmpeg
x11grab` while `xterm` runs [`session.sh`](session.sh) and Chrome then opens the
generated HTML reports and the public GitHub pages of the pilot PR and its run.
Nothing is replayed: each command on screen runs during the recording and each
model request is made live. Waits are real.

What the session does, at pinned inputs:

- Besu just before and with the [PR #5786](https://github.com/besu-eth/besu/pull/5786)
  fix (`19c989a…` and `7605351…`), three files, read as data only;
- the full EIP-4844 text from `ethereum/EIPs@eb2e7a9…`;
- one joint `prspec analyze --multi-file` request per commit; models are tried
  in the order of `PRSPEC_MODELS` and every attempt is visible on screen.

This is a historical replay of a known, already fixed bug, not a new finding.

Safety: secrets reach only the record and scan steps; all terminal output goes
through [`scrubtty.py`](scrubtty.py), which redacts secret values before they are
drawn or logged; [`manifest.py`](manifest.py) hashes every evidence file and
refuses to publish if a secret value appears in any of them. Evidence goes to
the `prspec-evidence` branch of the fork, never to the PR.

Install on a fork: put [`record-live-demo.yml`](record-live-demo.yml) in
`.github/workflows/` and the other files in `.github/prspec-demo/` on a branch
named `prspec-demo-record`, set `PRSPEC_COMMIT`, add `GEMINI_API_KEY` and/or
`PRSPEC_META_API_KEY` as repository secrets, and push the branch.
