# Changelog

## v2.0.0 (2026-11-10, branch `evidence-pilot`, not yet tagged)

New
- **Deterministic witnesses** (`prspec witness`, `src/witness.py`, `src/rules/`): EIP constants are
  extracted from a pinned `ethereum/EIPs` revision and checked against anchors in Besu, go-ethereum
  and Nethermind source. No LLM, no API key. Fail-closed: a moved anchor or a missing spec constant
  is reported as incomplete (exit 20), never as a pass. Rulebooks: EIP-1559 (3 rules), EIP-4844 (9 rules).
- **Fork Watch** (`prspec fork-watch`): parameter-level diff between two EIP revisions (changes,
  additions, removals, renames), mapped to witness rules and to the client files to review, with an
  optional witness run of each client against the new revision.
- **Mutation scoreboard**: new deterministic witness column next to the LLM outcome; runs in `--dry-run`.
- **Local / self-hosted models**: `--provider local` talks to any OpenAI-compatible server (Ollama,
  vLLM, llama.cpp, LM Studio). `prspec --no-cloud ...` (or `PRSPEC_NO_CLOUD=1`) refuses every provider
  except a loopback/private-address server.
- **Docker image** (`Dockerfile`, non-root, no secrets at build time) and `requirements.lock`.
- `prspec models`: lists the Gemini models the configured key can call and probes one with a tiny request.
- CI: runs on `evidence-pilot`, lints, tests on Python 3.10/3.12/3.13, installs the package outside the
  checkout, builds the Docker image, and runs the key-free witness matrix against the three clients.
- `.github/workflows/gemini-live.yml`: the live Gemini experiment (model listing + probe, one full Besu
  EIP-1559 analysis, mutation scoreboard), triggered from `evidence-pilot` before anything is merged.

Changed
- **Gemini**: default model `gemini-3.8-flash` (Google lists 2.0 Flash as shut down and limits 2.5 to
  existing users). JSON response mode, model-default temperature (Google recommends not lowering it for
  Gemini 3+), bounded retries on 429/5xx, and truncated (`MAX_TOKENS`), safety-blocked or empty
  responses become `ERROR` instead of a clean result. Every result records model version, token usage
  and latency. `GEMINI_MODEL` overrides the model id.
- OpenAI provider: `max_completion_tokens`, optional `base_url`, JSON mode; default model `gpt-6.1-sol`.
- Python floor raised to 3.10 (current `google-genai` requires 3.11+ for its newest releases; 3.10 resolves
  an older SDK). The Docker image and lock file use Python 3.13.

Included from the unreleased v1.8.0 "Evidence Pilot" work
- Installed `prspec` works outside a checkout (`No module named 'src'` fixed; default config shipped).
- Fail-closed fetching and exit codes: `0` clean, `10` findings (`--fail-on findings`), `20` incomplete, `1` tool error.
- `--ref <sha>` pins the client commit; `--source-dir` analyses a local checkout.
- Besu pilot kit (`pilot/besu/`) and the pre-registered 10-mutation scoreboard.

### v1.7.1 (2026-06-30)
- **Staking-EIP coverage**: EIP-7002 (triggerable withdrawals) and EIP-7251 (consolidation) file mappings across go-ethereum, Nethermind, Besu, and Reth; EIP-4788 mappings extended to Nethermind and Besu; geth EIP-4788/6110 mappings corrected to the real processing paths
- **Finding**: confirmed cross-client divergence in the request system-call path (geth accepts a block with a missing checked-request predeploy where the reference, Nethermind, and Besu invalidate), corroborated across EIP-7002 and EIP-7251
- **Fix**: updated execution-specs fetch paths for the upstream `src/ethereum/forks/<fork>/` restructure (fork-to-fork spec diffs were silently failing)
- 4 new tests (149 passing total)

### v1.7.0 (2026-06-26)
- **Reth (Rust) client support**: PRSpec now analyzes [paradigmxyz/reth](https://github.com/paradigmxyz/reth) alongside go-ethereum, Nethermind, and Besu — Rust parser with `fn`, `impl`, `struct`, and `trait` extraction added to `CodeParser`
- **Pectra EIP coverage**: full file mappings for EIP-7702 (Set EOA Account Code), EIP-2935 (Historical Block Hashes), EIP-2537 (BLS12-381 precompiles), and EIP-6110 (Validator Deposits) across all four clients
- Focus areas for each Pectra EIP defined in `config.yaml` (authorization tuple validation, delegation designator prefix, ring buffer index, subgroup membership checks, etc.)
- 20 new tests: Rust parser correctness, Reth registry validation, Pectra EIP file mapping coverage, branch-aware fetching for non-master repos
- Registry now spans 10 EIPs × 4 clients (145 tests passing total)

### v1.6.0 (2026-06-25)
- **Verified findings**: every candidate finding is now adversarially re-examined (independent skeptic rounds vote `CONFIRMED`/`DISPUTED`/`REFUTED`) and grounded against the exact specification text, collapsing the false-positive rate. Verification is on by default for `analyze` (`--no-verify` to skip, `--verify-rounds` to tune)
- `DifferentialEngine` and reports can restrict stats to confirmed-only findings
- **Fork-to-fork spec diffs**: the analyzer is fed the execution-spec delta between the implementing fork and its predecessor (e.g. `london` vs `berlin`) instead of the whole `fork.py`, focusing the comparison on the EIP boundary
- New `src.verifier` library API (`VerificationEngine`, `SpecGrounding`); `SpecFetcher.fetch_execution_spec_diff`
- **Azure AI Foundry provider**: point PRSpec at a Claude (or any) deployment in your own Foundry resource via `LLM_PROVIDER=azure` and the `AZURE_AI_*` variables; useful when you want a stronger reasoning model for the verification passes
- 31 new tests covering grounding, verdict tallying, diff extraction, and the Azure provider (125 passing total)

### v1.5.0 (2026-06-08)
- **Cross-client differential analysis (Phase 3)**: new `prspec diff` command compares how multiple clients implement the same EIP and produces an agree/diverge comparison matrix
- `DifferentialEngine`: deterministic comparison across overall status, issue types, and EIP focus areas (no API key required)
- Optional `--llm-synthesis` pass for a natural-language divergence narrative
- Differential reports in JSON, Markdown, and HTML
- New `src.differential` library API (`analyze_clients`, `DifferentialEngine`)
- 18 new tests covering the differential engine

### v1.4.0 (2026-02-14)
- **Multi-client support**: Nethermind (C#) and Besu (Java) alongside go-ethereum (Go)
- EIP-1559 and EIP-4844 file mappings for all three clients (5 files each)
- C# and Java regex parsers with class + method extraction
- 25 new tests covering registry, parsers, and fetch integration
- Keyword matching verified language-agnostic (case-insensitive)

### v1.3.0 (2026-02-06)
- Parallel analysis: all files analyzed concurrently via thread pool, ~3x faster on multi-file EIPs
- Expanded file coverage: EIP-1559 and EIP-4844 now analyze 5 files each (added `state_transition.go`, `protocol_params.go`, `legacypool.go`)
- Beautified CLI: progress bar with file counter, styled config panel
- Migrated to `google-genai` SDK (replaces deprecated `google-generativeai`)
- Executive summary paragraph at the top of every report

### v1.1.0 (2026-02-01)
- Multi-EIP architecture: registry-based spec and code fetching
- Added EIP-4844, EIP-4788, EIP-2930 support
- HTML report with dark-nav professional layout
- Comprehensive test suite (37 tests)

### v1.0.0 (2026-01-22)
- Initial release: EIP-1559 analysis against go-ethereum
- Gemini and OpenAI support, JSON/Markdown/HTML output
