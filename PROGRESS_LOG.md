# Progress log

Times are UTC. Newest last.

- 2026-11-10 02:10 — Session start. Environment: no `GEMINI_API_KEY`, no GitHub credentials, no Docker.
  Network available. Cloned `Fosurero/PRSpec`; remote `evidence-pilot` already at `ae66a3e` (both
  attached patches are already on GitHub; nothing to re-apply). `main` still `047dd15`.
- 02:15 — Baseline on `evidence-pilot`: 175 passed, 2 skipped; ruff 8 fixable errors; scoreboard dry-run OK.
- 02:20 — Verified Gemini model ids on ai.google.dev/models (updated 2026-10-28): 3.8 Flash / 3.5 Flash-Lite
  recommended for new projects; 2.5 restricted; **2.0 Flash shut down**. Decision: "Gemini 2.0 config"
  = PRSpec 2.0's Gemini configuration with `gemini-3.8-flash`; `gemini-2.0-flash` cannot be used.
- 02:25 — Sparse-cloned EIPs, Besu (pinned), Geth, Nethermind. Located constants in all three clients.
- 02:30 — Implemented `src/witness.py` + rulebooks. First real matrix: all mapped rules PASS on 3 clients.
- 02:35 — Found real EIP-4844 parameter history (2511e0bc, 58e82a0a, 89b85203). Added aliases for renamed
  constants. Historical replay: exactly the 3 changed constants fail in all 3 clients.
- 02:40 — Gemini analyzer upgrade, local provider, `--no-cloud`; 2 legacy tests adapted; 175 → pass.
- 02:45 — CLI `witness`, `fork-watch`, `models`; scoreboard witness column (4/10 caught deterministically).
- 02:48 — Tests `test_witness.py`, `test_v2_providers.py` → 206 passed. Version 2.0.0; Python ≥ 3.10
  (google-genai 3.x needs 3.11+). Clean-venv install verified. `requirements.lock`.
- 02:50 — Dockerfile (not buildable here). CI rewritten. Caught and fixed invented action SHAs by resolving
  real tags with `git ls-remote` (decision: never hand-write SHAs).
- 02:52 — Commits `f0a2d23` (feature) and `240e412` (CI). `gemini-live.yml` added.
- 02:55 — Evidence generated in `docs/evidence/2026-11-10/`. README rewritten; CHANGELOG, ROADMAP,
  PROJECT_STATUS, VERIFICATION, NEXT_STEPS written.

- 2026-11-10 — Added optional Meta Model API provider (`muse-spark-1.3`) with JSON Schema,
  environment-only key, and no-cloud guard. Live synthetic spec/code analysis through PRSpec returned
  PARTIAL_MATCH and detected the deliberately wrong nonce boundary (536 input / 1,116 output tokens).
  Test suite: 210 passed, 2 skipped; ruff clean. This is a smoke test, not a benchmark.

- 2026-11-10 06:50 — Continuation session (new model). Machine state intact: branch `evidence-pilot` at
  `216fc47`, 4 commits ahead of remote `ae66a3e`; remote `main` still `047dd15`. GitHub token: API shows
  admin/push on the repo.
- 06:52 — Gemini diagnosis with the key Safi shared (outside the repo, never printed): model listing OK;
  `gemini-3.8-flash` → **503 "high demand"** on every attempt (capacity, not a key error);
  `gemini-3.7-flash` → 504; `gemini-3.6-flash` and `gemini-3.5-flash` answered (3.5 reports
  `model_version` `gemini-3.6-flash`). The key works.
- 06:55 — Found a real CI bug before pushing: `scripts/fetch_clients.sh` sparse-checked only
  `ethereum/core/.../mainnet/**`, but the scoreboard baseline reads `ethereum/core/.../core/Transaction.java`
  → `FileNotFoundError`. `gemini-live.yml` would have failed after fetching. Fixed: `ethereum/core/src/main/java/**`
  (same as `besu-mutation-scoreboard.yml`).
- 07:00 — **First live Gemini scoreboard row (local, 1 mutation):** `--only M3`, `gemini-3.6-flash`,
  verify 2 rounds → M3 **confirmed** (1 matching issue); 2 baseline issue candidates on clean Besu for hand
  triage (not triaged yet); primary-pass tokens 79,451 prompt / 1,511 output / 11,254 thinking; wall 211.5 s.
  Evidence: `docs/evidence/2026-11-10/gemini-local-smoke-M3/`. One mutation only; not the scoreboard result.
- 07:02 — `gemini-live.yml`: `model=` is now a preference list; the first model that is visible and passes the
  probe is used by all later steps (up to 3 passes, 90 s apart); attempts are saved in the artifact. Local
  test of the step: loop works; at that moment both 3.8 and 3.6 returned 503, so `gemini-3.5-flash` added as
  a third fallback. `pilot/live/REQUEST` requests all 10 mutations, 1 run.
- 07:05 — Demo: witness frame said "34 match, 0 mismatch, 0 incomplete" and clipped the last row; now also
  states the 2 checks without an anchor and uses a denser table. `demo/README.md` (commands, storyboard,
  source per frame); `demo/out/` ignored. Tests: 210 passed, 2 skipped (key-free); ruff clean.
  Note: with `GEMINI_API_KEY` exported, the 2 opt-in live tests run and hang on 3.8 Flash 503 retries;
  run the suite without keys.
- 07:05 — **Pushed `evidence-pilot`** `ae66a3e..f3c2f7a` (fast-forward, no force; `main` untouched at `047dd15`).
  CI run `42772789938` and Gemini live run `42772789877` started, and every job was refused before its first step:
  "The job was not started because your account is locked due to a billing issue." This is a GitHub account billing problem; no
  runner time or API calls were used.
- 07:06–07:14 — Local run of the `gemini-live.yml` steps verbatim. Probe pass 1: 3.8 Flash 504, 3.6 Flash **429
  free-tier daily quota (20 requests/model/day)**, 3.5 Flash OK. Stopped before the scoreboard because one
  scoreboard needs about 22 primary calls plus verification calls, more than the free-tier day allows. Probe evidence in
  `docs/evidence/2026-11-10/gemini-probe-local/`.
- 07:10 — `ci.yml` witness job run locally against today's default branches (Besu `6d134c0e`): 34 ✅, 2 ⚪, exit 0.
- 07:14–07:29 — **Meta Muse Spark full scoreboard** (labeled Meta, not Gemini): 10 mutations, verify 2 rounds → 6 confirmed,
  1 flagged, 3 inconclusive, 0 missed, 0 errors; baseline 33 raw issues, all refuted → 0 candidates; 226,847 in /
  82,430 out primary tokens (about 0.63 USD at published prices, verification calls not metered); 916 s.
  Human check: each mutated file has a correct matching issue. Evidence `docs/evidence/2026-11-10/meta-live/`.
- 07:35 — Video: live frame is provider-aware (kicker, column, "not Gemini" warning, outcome definitions, tokens). Built
  `demo/out/prspec-2.0-demo-meta.mp4` (84 s, 1920×1080, no audio); sampled every 5 s from the encoded file, and all 9 frames
  render correctly. The Gemini final cut is still pending.
- 07:45 — README, PROJECT_STATUS, VERIFICATION, ROADMAP, NEXT_STEPS updated.
