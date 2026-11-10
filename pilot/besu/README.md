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
   (`workflow_run`), so fork PRs never get the API key. It:
   - checks out the PR's Java files **as text** (nothing from the PR is built or executed),
   - installs PRSpec from a pinned commit (not from the PR),
   - analyses only the EIPs whose files changed, with adversarial verification on,
   - writes the report to the job summary and a `prspec-report` artifact,
   - posts **at most one** collapsed comment per PR, edited in place
     (`POST_COMMENT: "false"` turns comments off).

The job has `continue-on-error: true` and is not a required check.

## Data path

Only the mapped source files (listed in `src/code_fetcher.py`, Besu section) and the
EIP text go to the configured LLM provider (default: Google Gemini, model pinned in
`prspec.besu.yaml`). Nothing is sent anywhere else, and nothing is stored outside
the workflow run.

## Exit codes (fail-closed)

| Code | Meaning |
|---|---|
| 0 | every mapped file was analysed |
| 10 | findings reported (only with `--fail-on findings`) |
| 20 | **incomplete**: a file could not be fetched or its LLM call failed. The summary says so explicitly. Treat it as no signal, never as clean |
| 1 | PRSpec itself failed (config, key, network) |

## Install (maintainers)

1. Copy `workflows/prspec-pilot-trigger.yml` and `workflows/prspec-pilot.yml` to `.github/workflows/`.
2. Set `PRSPEC_COMMIT` in `prspec-pilot.yml` to a reviewed PRSpec commit.
3. Add a repository secret `PRSPEC_GEMINI_API_KEY`.

Opt-out: delete the two files, or disable the workflow in the Actions tab.

## Evidence: mutation scoreboard

We inject 10 realistic EIP-1559/4844 deviations (`mutations.yaml`) into the Besu files
in memory, at a pinned commit, and measure what PRSpec catches. The detection criteria
are written in the YAML **before** any run, and the raw outputs are published:

```bash
git clone --filter=blob:none https://github.com/besu-eth/besu.git ../besu
git -C ../besu checkout 8f01c7a3200780b00163ab76d544e0ef6646da41
python scripts/mutation_scoreboard.py --besu-dir ../besu --dry-run   # no API key needed
python scripts/mutation_scoreboard.py --besu-dir ../besu --runs 2    # needs GEMINI_API_KEY
```

Recorded Meta Muse Spark run: [scoreboard](../../docs/evidence/2026-11-10/meta-live/scoreboard/scoreboard.md),
[raw data](../../docs/evidence/2026-11-10/meta-live/scoreboard/scoreboard.json).
Six mutations were confirmed by automated verification, one flagged, and three inconclusive.
The clean baseline produced 33 raw issues; none survived automated verification. These results
are a single experiment, not an independently measured false-positive rate or proof of a real bug.

For a reproducible key-free walkthrough, see [Besu demo guide](DEMO.md).

## Known limitations (read before trusting a result)

- Findings are LLM output. Verification lowers noise but does not make them proofs.
- PRSpec reads only the mapped files. Logic that lives elsewhere is invisible.
  Building this kit exposed exactly that: Besu's core EIP-4844 fee logic
  (`BlobFeeMarket.fakeExponential`, `CancunTargetingGasLimitCalculator.computeExcessBlobGas`)
  was not mapped before; it is now.
- Policy vs consensus: txpool / RPC policy choices (e.g. #10714, #10715) are not spec
  deviations. Please tell us when a finding falls in that bucket so we can suppress the class.
- Cost and latency per PR are reported by the scoreboard run; we will not quote numbers before then.
