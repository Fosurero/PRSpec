# Verification record

Every claim in README.md §"Verified results" maps to a command below. Environment of this record:
Linux, Python 3.13, google-genai 3.0.0, openai 3.48.0, ruff (from `.[dev]`), 2026-11-10 UTC.
No Docker daemon, no `GEMINI_API_KEY`, no GitHub write credentials were available.

## Pinned sources

| Source | Commit |
| --- | --- |
| ethereum/EIPs | `542e62eb129517130b7facc52bbb9a1f333c711e` |
| besu-eth/besu | `8f01c7a3200780b00163ab76d544e0ef6646da41` |
| ethereum/go-ethereum | `c863eecbddb2c9db2cd2f07bb1db80740d75a5b3` |
| NethermindEth/nethermind | `8ba0b6d05ea0b036524658f5ba1b6d14afd8f20e` |
| EIP-4844 change used for replay | `2511e0bc3eac7343ff306d246dee0f69d0862498` (parent `be27fce3a363685642daf1dbe8d294d69a31a063`) |

```bash
scripts/fetch_clients.sh /tmp/clients 8f01c7a3200780b00163ab76d544e0ef6646da41 \
  c863eecbddb2c9db2cd2f07bb1db80740d75a5b3 8ba0b6d05ea0b036524658f5ba1b6d14afd8f20e \
  542e62eb129517130b7facc52bbb9a1f333c711e
```

## Results

| # | Command | Result | Artifact |
| --- | --- | --- | --- |
| 1 | `ruff check .` | All checks passed | — |
| 2 | `python -m pytest -q` | 206 passed, 2 skipped (need a Gemini key) | — |
| 3 | clean venv, `pip install .`, `cd /tmp && prspec --version` | `PRSpec, version 2.0.0`; `prspec witness --eip 1559 --list` works (rulebooks shipped) | — |
| 4 | `prspec witness --eip 1559 -t besu=… -t go-ethereum=… -t nethermind=… --eips-dir …` | 9 ✅, exit 0 | `docs/evidence/2026-11-10/witness-1559.{md,json}` |
| 5 | same for `--eip 4844` | 25 ✅, 2 ⚪ (no anchor), exit 0 | `witness-4844.{md,json}` |
| 6 | `prspec witness --eip 4844 … --spec-ref 2511e0bc^` | 3 ❌ per client (UPDATE_FRACTION, TARGET, MAX), exit 10 | `witness-4844-at-2511e0bc-parent.{md,json}` |
| 7 | `prspec fork-watch --eip 4844 --from 2511e0bc^ --to 2511e0bc` | 3 changed constants → 3 rules → files in 3 clients | `fork-watch-4844-2511e0bc.{md,json}` |
| 8 | `python scripts/mutation_scoreboard.py --besu-dir /tmp/clients/besu --dry-run --eips-dir /tmp/clients/EIPs` | all 10 mutations apply exactly once; witness catches M1, M2, M7, M8 | `scoreboard-dry-run.txt`, `scoreboard-dry-run/` |
| 9 | `tests/test_v2_providers.py::test_local_provider_end_to_end_over_http` | real HTTP POST `/v1/chat/completions` via the openai SDK to a local server, parsed | — |
| 10 | `tests/test_v2_providers.py` Gemini tests | truncated (`MAX_TOKENS`), `SAFETY`, empty → `ERROR`; 503 retried; auth error not retried; temperature omitted; JSON mode on | — |
| 11 | `tests/test_v2_providers.py::test_no_cloud_guard` | Gemini refused; non-private local URL refused; 127.0.0.1 allowed | — |
| 12 | Action pins in workflows | resolved with `git ls-remote` against `actions/*` tags (checkout v7.0.1, setup-python v7.1.0, upload-artifact v7.0.2) | — |

## Meta Muse live smoke test (2026-11-10)

A real PRSpec `meta` analyzer call sent only a synthetic rule and a synthetic Python snippet to
`muse-spark-1.3`. The rule required rejecting nonces above 3; the code incorrectly accepted 4.
The structured response returned `PARTIAL_MATCH` with one issue and identified the off-by-one error.
Usage reported: 536 prompt tokens and 1,116 completion tokens; 12.59 s. This single example is
not a benchmark or evidence of production accuracy. A separate connectivity test returned `OK`
(12 prompt / 16 completion tokens). `pytest -q`: 210 passed, 2 skipped; `ruff check .` clean.

## Not verified here (and why)

| Item | Why | Where it gets verified |
| --- | --- | --- |
| Gemini live analysis / scoreboard numbers | live generation returned HTTP 503; scoreboard not run | `.github/workflows/gemini-live.yml` → `docs/evidence/<date>/gemini-live/` |
| Gemini model availability for the project key | listed by API, but generation returned HTTP 503 | `prspec models --probe` step in the same workflow |
| Docker build | no daemon | `ci.yml` job `docker` |
| Witness matrix on default branches | done locally at pinned commits only | `ci.yml` job `witness-live-clients` |
| Inference quality of any local model | no GPU/model here | ROADMAP C8 |
