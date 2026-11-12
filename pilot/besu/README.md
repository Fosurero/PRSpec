# PRSpec pilot kit for Besu

This kit answers the two things asked for on
[besu-eth/besu#9850](https://github.com/besu-eth/besu/issues/9850): a minimal
GitHub Actions snippet and a reproducible baseline config. It is advisory only.
It never blocks a PR, and you can remove it by deleting two files.

## What happens on a PR

1. `prspec-pilot-trigger.yml` runs only when a PR touches one of the
   EIP-1559 / EIP-4844 files PRSpec maps for Besu (paths filter). It has no
   secrets and no permissions; it records the PR number and head SHA.
2. `prspec-pilot.yml` runs afterwards in the base-repo context
   (`workflow_run`). This draft rejects fork PRs and requires the triggering
   run to be associated with the PR; it:
   - checks out the PR's Java files **as text** (nothing from the PR is built or executed),
   - installs PRSpec from a pinned commit (not from the PR),
   - checks out the EIP text at a pinned commit and analyzes the mapped files
     jointly, one model call per touched EIP, with verification **off**,
   - writes JSON, Markdown and HTML reports to the `prspec-report` artifact and a summary,
   - does not comment on or modify the PR.

The job has `continue-on-error: true` and is not a required check.

## Data path

Only the mapped source files (listed in `src/code_fetcher.py`, Besu section) and the
pinned EIP text are sent to Meta. JSON records selected paths and SHA-256 hashes
of each source and specification; response token counts appear when returned.
The configured model and API endpoint are written in the workflow and
`prspec.besu.yaml`. The joint input is limited to 160,000 UTF-8 bytes of
source, but this is not a dollar or token budget. API calls may be billable,
and no billing dashboard has been checked. Standard GitHub Actions,
package installation and source retrieval also use network services.

## Exit codes (fail-closed)

| Code | Meaning |
|---|---|
| 0 | every mapped file was analysed |
| 10 | findings reported (only with `--fail-on findings`) |
| 20 | **incomplete**: a file could not be fetched or its LLM call failed. The summary says so explicitly. Treat it as no signal, never as clean |
| 1 | PRSpec itself failed (config, key, network) |

## Install (maintainers)

1. Only in a repository whose owner explicitly approves, copy
   `workflows/prspec-pilot-trigger.yml` and `workflows/prspec-pilot.yml` to
   `.github/workflows/` on its default branch. Do not install on Besu without
   maintainer approval.
2. Review the pinned `PRSPEC_COMMIT` and the model configuration in the workflow.
3. Add your own Meta API key as a repository secret `PRSPEC_META_API_KEY`.

Opt-out: delete the two files, or disable the workflow in the Actions tab.

## Evidence: mutation scoreboard

We inject 10 realistic EIP-1559/4844 deviations (`mutations.yaml`) into the Besu files
in memory, at a pinned commit, and measure what PRSpec catches. The detection criteria
are written in the YAML **before** any run, and the raw outputs are published:

```bash
git clone --filter=blob:none https://github.com/besu-eth/besu.git ../besu
git -C ../besu checkout 8f01c7a3200780b00163ab76d544e0ef6646da41
python scripts/mutation_scoreboard.py --besu-dir ../besu --dry-run   # no API key needed
python scripts/mutation_scoreboard.py --besu-dir ../besu --provider meta --runs 2  # needs MODEL_API_KEY; billable
```

Recorded Meta Muse Spark run: [scoreboard](../../docs/evidence/2026-11-10/meta-live/scoreboard/scoreboard.md),
[raw data](../../docs/evidence/2026-11-10/meta-live/scoreboard/scoreboard.json).
Six mutations were confirmed by automated verification, one flagged, and three inconclusive.
The clean baseline produced 33 raw issues; none survived automated verification. These results
are a single experiment, not an independently measured false-positive rate or proof of a real bug.

For the real historical Besu PR replay and its limits, see [Besu demo guide](DEMO.md).

## Known limitations (read before trusting a result)

- Findings are LLM output. Verification lowers noise but does not make them proofs.
- This draft disables verification to limit calls; all findings require human
  review. A joint result is one analysis unit, not a per-file result. If any
  selected source is missing or exceeds the joint size limit, no joint model
  call is made and the run is incomplete.
- Fork PRs are intentionally rejected; the triggering workflow run must have
  an association with the PR in the GitHub API. If that association is absent,
  the draft fails closed. Symlinked source paths are rejected. This mitigates
  some risks but does not make prompt-injection or untrusted inputs safe.
- PRSpec reads only the mapped files. Logic that lives elsewhere is invisible.
  Building this kit exposed exactly that: Besu's core EIP-4844 fee logic
  (`BlobFeeMarket.fakeExponential`, `CancunTargetingGasLimitCalculator.computeExcessBlobGas`)
  was not mapped before; it is now.
- Policy vs consensus: txpool / RPC policy choices (e.g. #10714, #10715) are not spec
  deviations. Please tell us when a finding falls in that bucket so we can suppress the class.
- Cost and latency per PR are reported by the scoreboard run; we will not quote numbers before then.

## Important status

The workflow remains a draft, not yet tested end-to-end in GitHub Actions or
Besu CI. The generic joint pass is not proven to detect historical PR #5786;
that focused experiment used a selected rule and three files. HTML/JSON/Markdown
reports and workflow behavior must be validated before trial. The HTML
confidence field is a model-reported value, **not** a calibrated probability.
