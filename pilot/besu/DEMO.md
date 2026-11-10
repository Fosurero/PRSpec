# Besu pilot: real historical PR replay

**A real, published Besu fix—not an injected bug and not a new discovery.** Besu [PR #5786](https://github.com/besu-eth/besu/pull/5786) corrected how a block producer calculates excess blob gas. PRSpec was run on the actual code before and after the fix, against the relevant historical EIP-4844 paragraph.

- **Before:** Meta Muse Wonder returned one candidate identifying the use of current-block blob usage instead of the parent's blob gas used.
- **After:** zero candidates for the selected requirement; the model labelled the supplied context `FULL_MATCH`.
- **Scope:** one retrospective case, three supplied files, one selected rule. No model verification rounds, execution of Besu, EELS test, independent assessment, or CI run. A model match does not prove compliance. The case is public and may have appeared in model training.
- [Complete methodology, failed broader attempt and raw outputs](../../docs/evidence/2026-11-10/besu-pr5786/README.md) · [actual Besu change](../../docs/evidence/2026-11-10/besu-pr5786/real-change.diff).

## Replay the recorded demo — no API key

From a cloned PRSpec repository root:

```bash
python3 pilot/besu/replay_pr5786.py
```

The command prints the real patch and the recorded before/after PRSpec outputs. It does **not** make a model call. The case HTML report is `docs/evidence/2026-11-10/besu-pr5786/report.html`; open it in a browser. Both the report and raw JSON are generated from the actual results, not from a fabricated run.

## Repeat the analysis live — Meta key required

This opt-in performs two paid calls and sends the three public source files and the selected public EIP text to Meta. Responses may differ. The Git checkouts must contain the pinned commits in the [manifest](../../docs/evidence/2026-11-10/besu-pr5786/manifest-focused.json); a shallow clone may not. From the PRSpec root:

```bash
python -m venv .venv && . .venv/bin/activate
pip install .
git clone --filter=blob:none https://github.com/besu-eth/besu.git ../besu
git clone --filter=blob:none https://github.com/ethereum/EIPs.git ../EIPs
# Set MODEL_API_KEY securely in your environment, never in a file committed to Git.
META_MODEL=muse-wonder-1.0 python pilot/besu/replay_pr5786.py --live --besu-dir ../besu --eips-dir ../EIPs
```

Outputs go to `output/besu-pr5786-rerun/`. This targeted harness supplies the related files as context; the generic PR workflow currently analyzes registry files separately and is **not shown to detect this cross-file case**.

## What Besu requested

The [pilot kit](README.md) includes a draft minimal GitHub Actions pair and baseline config for a non-blocking run with an artifact report. It has not been run in Besu CI or independently reviewed. Real PR trials, human false-positive review, EELS/runtime validation, and client-team integration are future work that funding can support; funding does not itself validate this retrospective result.
