# PRSpec roadmap

Legend: **A** = implemented and verified · **B** = partially implemented · **C** = proposed and worth funding.
Nothing in column C exists today.

## A. Implemented and verified (2.0.0)

| Capability | Evidence |
| --- | --- |
| Deterministic witnesses, EIP-1559 + EIP-4844, Besu/Geth/Nethermind | `docs/evidence/2026-11-10/witness-*.md`, `tests/test_witness.py` |
| Fork Watch parameter diff + impact card | `docs/evidence/2026-11-10/fork-watch-4844-2511e0bc.md` |
| Mutation scoreboard with pre-registered criteria + witness column | `docs/evidence/2026-11-10/scoreboard-dry-run.txt` |
| Fail-closed exit codes (0/10/20/1) everywhere | `tests/test_fail_closed.py`, `tests/test_witness.py` |
| Local OpenAI-compatible provider + `--no-cloud` guard | `tests/test_v2_providers.py` (real HTTP round trip) |
| Installable package (works outside checkout) | clean-venv smoke test, CI job |

## B. Partially implemented

| Capability | What exists | What is missing |
| --- | --- | --- |
| Gemini 2.0 live analysis | Upgraded integration (3.8 Flash default, JSON mode, retries, truncation handling, usage metadata), unit-tested; `gemini-live.yml` | Live run results; quality numbers on the scoreboard |
| Besu Pilot Kit | Read-only workflow pair, pinned config, suppression list, scoreboard | Run inside a Besu fork/PR; replay of 3–5 historical Besu PRs; maintainer feedback |
| Docker image | Non-root Dockerfile + lock file; CI build + smoke test | Image not built locally (no daemon); not published to a registry |
| Fork Watch | Constant-level diff | Prose/algorithm-level change detection; automatic watching of merged spec PRs |
| Local models | Transport + privacy guard | A measured run with an open-weights model; hardware/cost notes |

## C. Proposed and worth funding

Ordered by value to client teams, each with a concrete acceptance test.

1. **Executable witnesses (EEST-format) verified against EELS.** For rules that are testable, generate a
   test, require it to pass on the execution-specs reference *before* it is run on clients, and report a
   client failure only with a failing witness. *Done when:* ≥ 5 witnesses for EIP-4844/7691 pass on EELS,
   run on 2 clients via `t8n`/`consume`, with false-positive counts published. Upstreamable to EEST.
2. **Spec-PR watcher (Fork Watch service).** Watch merged PRs in `ethereum/EIPs` and `execution-specs`,
   post an impact card per client (rules changed, files to review, witness result) to an issue or a
   Discord/Matrix channel the team chooses. *Done when:* a month of cards for an active fork (Hegotá)
   with noise measured.
3. **Fork-aware parameter schedules.** Model blob schedules (EIP-7691, EIP-7840, BPO forks) per fork, so
   witnesses check Prague/Osaka/BPO values, not just Cancun. *Done when:* the schedule for every activated
   fork matches all three clients' configs, and a deliberately wrong BPO value is caught.
4. **PR-level CI for client repositories.** Turn the Besu pilot into a reusable GitHub Action with SARIF
   output and a single folded PR comment; paths-filtered so it only runs on spec-relevant files. *Done
   when:* one client team runs it for 4 weeks and reports review effort saved or noise added.
5. **Policy atlas.** Separate consensus rules from txpool/devp2p/RPC policy per client (the distinction
   Besu #10714/#10715 asked for), so policy differences are reported as such, not as bugs.
6. **Reth and Erigon anchors**, plus witness rulebooks for EIP-7702, 2935, 7002, 7251.
7. **Cross-EIP composition checks.** Rules that combine several EIPs (e.g. EIP-7928 BAL with EIP-8253)
   where each EIP alone is fine but the combination is not.
8. **Local-model evaluation.** Same scoreboard, same budget, open-weights models on documented hardware;
   publish accuracy, false positives, time and cost side by side with Gemini.

## Funding-relevant milestones (maps to the TheDAO initiative)

| Milestone | Deliverable | Evidence of acceptance |
| --- | --- | --- |
| M0 (done in 2.0.0) | Witness + Fork Watch + fail-closed CLI + pilot kit | This repository, `VERIFICATION.md` |
| M1 | Gemini live scoreboard published with raw outputs; Docker image published | `docs/evidence/<date>/`, image digest |
| M2 | Executable witnesses (item 1) for EIP-4844/7691 | EELS-pass logs, client run logs |
| M3 | One client team piloting PR-level CI (item 4) | Public statement or issue from the team |
| M4 | Spec-PR watcher for Hegotá (item 2), 1 month of cards | Card archive + noise report |
| M5 | Third client + fork-aware schedules (item 3) | Witness matrix across 3 clients for every active fork |
