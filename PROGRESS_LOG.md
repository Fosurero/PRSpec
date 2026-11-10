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
