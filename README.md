# PRSpec

**Spec-to-client evidence for Ethereum execution clients.** PRSpec checks Besu, go-ethereum,
Nethermind and Reth source code against the EIP text they implement. It uses deterministic
witnesses where a rule can be checked mechanically, and LLM analysis with adversarial
verification where it cannot. Each result records the exact spec revision and client commit
it was produced from.

<p>
<a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT"></a>
<img src="https://img.shields.io/badge/version-2.0.0-informational.svg" alt="2.0.0">
</p>

> **Status of 2.0.0 (2026-11-10).** Code is on the `evidence-pilot` branch, not yet merged or tagged.
> Everything under [Verified results](#verified-results-2026-11-10) was produced by commands you can
> rerun ([VERIFICATION.md](VERIFICATION.md)). The live Gemini experiment runs in
> [`gemini-live.yml`](.github/workflows/gemini-live.yml); its results are published in
> [`docs/evidence/`](docs/evidence/) only after the run has actually happened. See
> [PROJECT_STATUS.md](PROJECT_STATUS.md) for what is done, partial, and planned.

---

## Why a client team would want this

- **Spec churn is real.** EIP text keeps changing after clients start implementing it. In June
  2023 alone, [one EIP-4844 commit](https://github.com/ethereum/EIPs/commit/2511e0bc3eac7343ff306d246dee0f69d0862498)
  changed three fee-market constants. More recently, Nethermind
  [#14030](https://github.com/NethermindEth/nethermind/issues/14030) was an implementation that kept an
  older EIP-8272 design after the spec moved on. A client can be correct against last month's spec
  and wrong against today's.
- **Client diversity multiplies the work.** Every spec change has to be found in four codebases in four
  languages. PRSpec maps each rule to the file and line in each client, so the question "which of our
  files does this spec PR touch?" has a reproducible answer.
- **It complements, not replaces, existing testing.** EEST and hive test behaviour. PRSpec reads the
  spec and the code *before* a test exists, shows reviewers where to look, and produces candidates
  that a human can turn into tests.
- **It can run without code leaving your machine.** The deterministic layer needs no model at all. The LLM
  layer can use a local OpenAI-compatible server, and `--no-cloud` enforces that.

## What PRSpec does: three layers

| Layer | What it checks | Needs an LLM? | Status |
| --- | --- | --- | --- |
| **Witnesses** (`prspec witness`) | EIP constants and simple derived values (for example `TARGET_BLOB_GAS_PER_BLOCK = target_blobs × GAS_PER_BLOB`) against anchors in client code | No | **Implemented and verified** for EIP-1559 (3 rules) and EIP-4844 (9 rules) on Besu, go-ethereum and Nethermind |
| **Fork Watch** (`prspec fork-watch`) | Parameter-level diff between two EIP revisions, mapped to rules and to the client files to review | No | **Implemented and verified** on real EIP-4844 history. Prose and algorithm changes are not detected yet |
| **Semantic analysis** (`prspec analyze`, `prspec diff`) | Logic and missing checks that cannot be reduced to a constant. Spec and code go to an LLM, and every finding is re-examined adversarially and grounded in the quoted spec text | Yes (Gemini, OpenAI, Meta Muse, local, Azure/Claude) | **Implemented.** Gemini 2.0 integration is covered by unit tests. The live run is in [`gemini-live.yml`](.github/workflows/gemini-live.yml) |

Executable witnesses (EEST-format tests checked against the EELS reference before they touch a
client) are **planned, not built**. See [ROADMAP.md](ROADMAP.md).

---

## Verified results (2026-11-10)

All of the following are deterministic and key-free. Raw outputs are in
[`docs/evidence/2026-11-10/`](docs/evidence/2026-11-10/).

**1. Cross-client witness matrix.** Spec `ethereum/EIPs@542e62eb`. Clients: Besu `8f01c7a3`,
go-ethereum `c863eecb`, Nethermind `8ba0b6d0`. There were **34 checks: 34 matched, 0 mismatched,
0 incomplete**. Two rule/client pairs (`FIELD_ELEMENTS_PER_BLOB` for Besu and Nethermind) have no
anchor yet and are shown as ⚪, not as passes.
[EIP-1559](docs/evidence/2026-11-10/witness-1559.md) · [EIP-4844](docs/evidence/2026-11-10/witness-4844.md)

**2. Historical spec-drift replay.** The three clients' current code was checked against the EIP-4844
text *before* commit `2511e0bc`. Exactly the three constants that the commit changed fail in all three
clients (`BLOB_BASE_FEE_UPDATE_FRACTION`, `TARGET_BLOB_GAS_PER_BLOCK` and `MAX_BLOB_GAS_PER_BLOCK`),
and nothing else does. Fork Watch's impact card for that commit names the same three rules and the
files to review in each client.
[Replay](docs/evidence/2026-11-10/witness-4844-at-2511e0bc-parent.md) ·
[Impact card](docs/evidence/2026-11-10/fork-watch-4844-2511e0bc.md)

This replay runs in one direction: current clients against an old spec. It shows that the mechanism
pinpoints a spec change. It is **not** a claim that PRSpec would have caught a historical client bug.

**3. Besu mutation scoreboard, deterministic column.** 10 realistic EIP-1559/4844 deviations were
pre-registered in [`pilot/besu/mutations.yaml`](pilot/besu/mutations.yaml) and injected in memory into
Besu `8f01c7a3`. Witnesses catch **4 of 10** (M1, M2, M7 and M8, all constant changes) with file and
line. The other 6 are logic changes (a removed `max(1, …)`, rounding, an off-by-one in
`fake_exponential`, a flipped sign, the fork-block base fee and the excess-blob-gas formula). No
constant check can see those, so they are what the Gemini layer is measured on.
[Output](docs/evidence/2026-11-10/scoreboard-dry-run.txt)

**4. Engineering checks.** There are 206 passing tests (2 skipped because they need a key) and ruff is
clean. A clean install outside the checkout gives `prspec --version` → `2.0.0`. A real HTTP round trip
to a local OpenAI-compatible server passes, and so do the `--no-cloud` guard and the Gemini fail-closed
handling for truncated, blocked, empty and transient-error responses.

**Not verified yet:** the Gemini live numbers, which come from the
[`gemini-live`](.github/workflows/gemini-live.yml) workflow; the Docker build, which no Docker daemon
was available to test, so CI builds it; a run inside Besu's own CI; and inference against a real local
model.

---

## Quick start

```bash
git clone https://github.com/Fosurero/PRSpec && cd PRSpec
python -m venv .venv && . .venv/bin/activate
pip install .

# Deterministic, no key: fetch pinned client sources and run the witness matrix
scripts/fetch_clients.sh ../clients 8f01c7a3200780b00163ab76d544e0ef6646da41 "" "" 542e62eb129517130b7facc52bbb9a1f333c711e
prspec witness --eip 4844 -t besu=../clients/besu -t go-ethereum=../clients/go-ethereum \
  -t nethermind=../clients/nethermind --eips-dir ../clients/EIPs

# Impact card for a real EIP-4844 spec change
prspec fork-watch --eip 4844 --from 2511e0bc^ --to 2511e0bc --eips-dir ../clients/EIPs \
  --check besu=../clients/besu

# Semantic analysis with Gemini (key from https://aistudio.google.com/apikey)
export GEMINI_API_KEY=...            # never commit it
prspec models --probe gemini-3.8-flash
prspec analyze --eip 1559 --client besu --source-dir ../clients/besu --output html
```

### Docker

```bash
docker build -t prspec:2.0.0 .
docker run --rm -v "$PWD/../clients:/src:ro" prspec:2.0.0 \
  witness --eip 1559 -t besu=/src/besu --eips-dir /src/EIPs
docker run --rm -e GEMINI_API_KEY -v "$PWD/../clients/besu:/src/besu:ro" prspec:2.0.0 \
  analyze --eip 1559 --client besu --source-dir /src/besu
```

The image runs as a non-root user (uid 10001) and contains no secrets. The key is passed at run time.

### Meta Muse (optional cloud provider)

Set `MODEL_API_KEY` securely in your environment and run:

```bash
prspec analyze --provider meta --eip 1559 --client besu --source-dir ../clients/besu
```

The default model is `muse-spark-1.3`; override it using `META_MODEL` or the
`meta` section of `config.yaml`. Spec and source code are sent to Meta and
usage may be billed. Never commit API keys. `--no-cloud` blocks this provider.
Meta supports the OpenAI-compatible Chat Completions endpoint and JSON Schema
responses: https://dev.meta.ai/docs/structured-output.

### Fully local: no code leaves your machine

```bash
ollama serve & ollama pull qwen3-coder:30b        # or vLLM / llama.cpp / LM Studio
export PRSPEC_LOCAL_BASE_URL=http://127.0.0.1:11434/v1 PRSPEC_LOCAL_MODEL=qwen3-coder:30b
prspec --no-cloud analyze --provider local --eip 1559 --client besu --source-dir ../clients/besu
```

With `--no-cloud`, PRSpec refuses Gemini, OpenAI, Meta and Azure. It also refuses a "local" URL that is not a
loopback or private address. Whether a given open-weights model is *good enough* has not been measured
yet. The transport is tested; the quality is not.

---

## CLI

| Command | Purpose | Exit codes |
| --- | --- | --- |
| `prspec witness --eip N -t CLIENT=DIR …` | Deterministic witness matrix | 0 match · 10 mismatch · 20 incomplete |
| `prspec fork-watch --eip N --from A --to B [--check CLIENT=DIR]` | Spec-change impact card | 0 · 10 a checked client disagrees · 20 incomplete |
| `prspec analyze --eip N --client C [--source-dir D \| --ref SHA]` | LLM analysis + verification, JSON/Markdown/HTML | 0 · 10 findings (`--fail-on findings`) · 20 incomplete · 1 tool error |
| `prspec diff --eip N --clients a,b,c` | Cross-client comparison of LLM results | as `analyze` |
| `prspec models [--probe MODEL]` | Models visible to `GEMINI_API_KEY`, with a one-request probe | |
| `prspec --no-cloud …` | Privacy guard for any command | |
| `prspec list-eips`, `list-files`, `fetch-spec`, `check-config`, `clear-cache` | Registry and config helpers | |

An incomplete run always takes precedence over a findings or clean exit code: a partial analysis
can never look clean.

### Configuration

`config.yaml` (also shipped inside the package) selects the provider and model. The environment
overrides it.

| Variable | Meaning |
| --- | --- |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Gemini key and model id (default `gemini-3.8-flash`) |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | OpenAI, or an OpenAI-compatible endpoint |
| `PRSPEC_LOCAL_BASE_URL` / `PRSPEC_LOCAL_MODEL` / `PRSPEC_LOCAL_API_KEY` | Local provider |
| `PRSPEC_NO_CLOUD=1` | Same as `--no-cloud` |
| `AZURE_AI_API_KEY` / `AZURE_AI_ENDPOINT` / `AZURE_AI_DEPLOYMENT` | Claude via Azure AI Foundry |
| `MODEL_API_KEY` / `META_MODEL` | Meta Model API key and model id (default `muse-spark-1.3`) |
| `LLM_PROVIDER` | `gemini` · `openai` · `meta` · `local` · `azure` |
| `GITHUB_TOKEN` | Optional, for GitHub rate limits when fetching remote code |

**Gemini model choice.** On 2026-11-10, Google's [models page](https://ai.google.dev/gemini-api/docs/models)
listed `gemini-3.8-flash` and `gemini-3.5-flash-lite` as the recommended models for new projects. It
limited 2.5 to existing users and listed 2.0 Flash as shut down. PRSpec therefore defaults to
`gemini-3.8-flash`. Run `prspec models` to see what *your* key can call. The free tier has quotas, and
Google's pricing page says free-tier content may be used to improve its products. Do not send
unreleased client code through the free tier; use the paid tier or `--provider local`.

---

## CI integration

- **This repository** ([`ci.yml`](.github/workflows/ci.yml)) runs lint, tests on Python 3.10, 3.12
  and 3.13, an install outside the checkout, a Docker build and smoke test, and the key-free witness
  matrix against Besu, go-ethereum and Nethermind at their default branches. If a client moves a
  constant or changes a value, the job fails with the file and line.
- **Besu pilot kit** ([`pilot/besu/`](pilot/besu/README.md)) is a read-only, non-blocking workflow pair
  for a client repository. The PR job has no secrets; the LLM job runs from `workflow_run`. It also has a
  baseline config pinned to model and commit, a policy-vs-consensus suppression list, and the mutation
  scoreboard. It has not been run inside Besu's repository yet.
- **Gemini live experiment** ([`gemini-live.yml`](.github/workflows/gemini-live.yml)) uses the repository
  secret `GEMINI_API_KEY`. It is triggered by editing `pilot/live/REQUEST` on `evidence-pilot`, or by
  manual dispatch once the file is on `main`.

## Supported clients and limits

| | go-ethereum | Nethermind | Besu | Reth |
| --- | --- | --- | --- | --- |
| LLM file registry (10 EIPs) | ✅ | ✅ | ✅ | ✅ (7 EIPs) |
| Witness anchors EIP-1559 | 3/3 | 3/3 | 3/3 | — |
| Witness anchors EIP-4844 | 9/9 | 8/9 | 8/9 | — |

Limits, stated plainly:

- Witnesses check constants, not behaviour. A ✅ does not prove compliance.
- Anchors are regular expressions reviewed at the commits listed in each rulebook. When code moves, the
  result becomes ⚠️ incomplete, never ✅.
- EIP-4844 witnesses check **Cancun** values. Later forks change blob parameters (EIP-7691, BPO forks),
  and those are not modelled yet.
- LLM findings are candidates for human review. The verification score is an internal vote, not a
  probability.
- No detection rate, false-positive rate or cost has been published until the live run produces one.

---

## Public interactions with client teams

These are links to public threads, with what the teams actually said:

- **Nethermind** [#10522](https://github.com/NethermindEth/nethermind/issues/10522): PRSpec flagged
  `FeeCollector` against EIP-1559's burn. The team explained it is an optional extension for other
  chains, not a mainnet deviation. A contributor suggested focusing on type sizes, limits and
  MUST/SHOULD/MAY semantics. That suggestion shaped the witness layer.
- **Ethereum Foundation execution-specs** [#2212](https://github.com/ethereum/execution-specs/issues/2212):
  maintainers advised using fork-to-fork diffs, which PRSpec now does.
- **Besu** [#9850](https://github.com/besu-eth/besu/issues/9850): a maintainer asked for a minimal GitHub
  Actions workflow and a reproducible baseline config. The [pilot kit](pilot/besu/README.md) answers that
  request. Besu also clarified [#10714](https://github.com/besu-eth/besu/issues/10714) and
  [#10715](https://github.com/besu-eth/besu/issues/10715) as pool policy or validation done in another
  layer, and PRSpec's suppression list encodes that.
- **go-ethereum** [#35263](https://github.com/ethereum/go-ethereum/issues/35263): a latent divergence for a
  missing checked-request predeploy, with no mainnet impact because predeploys exist at activation.
  It is fixed upstream in [`26d0b2171`](https://github.com/ethereum/go-ethereum/commit/26d0b2171), and EEST
  covers it. [Write-up](findings/geth-eip7002-missing-code-invalidation.md).

None of these is an endorsement or an adoption decision.

## Related work

The EF Protocol Security [wishlist](https://security.ethereum.org/wishlist) lists "Differential LLMing" and
"LLM Test Generation". EPF Cohort 6 has a
[Differential LLMing](https://github.com/eth-protocol-fellows/cohort-six/blob/master/projects/differential-llming.md)
project. [SpecTrum](https://arxiv.org/pdf/2608.17738) reports consensus-layer divergences, and
[LLM-driven differential testing](https://www.youtube.com/watch?v=btaJkpmFs4s) was presented at Black Hat
Asia 2026. PRSpec's focus is narrower and complementary: pinned, reproducible spec-to-code evidence for
execution clients, with a deterministic layer that does not depend on a model.

## Reproducing the demo

See [`demo/README.md`](demo/README.md). It contains the exact commands and the video storyboard, and
explains how each frame maps to a raw artifact.

## Roadmap and support

[ROADMAP.md](ROADMAP.md) separates what is implemented, what is partial, and what is proposed and
worth funding. The proposed work includes executable EEST witnesses verified against EELS, a spec-PR
watcher that posts impact cards, fork-aware blob schedules, a policy atlas, and Reth anchors.

PRSpec is MIT-licensed and maintained by one developer. The milestone-based
[TheDAO Security Fund initiative](https://initiatives.thedao.fund/initiative/automated-eip-compliance-checks-for-ethereum-clients)
and the [Giveth project](https://giveth.io/project/prspec-automated-eip-compliance-checker-for-ethereum)
fund the roadmap. A pledge is collected only under the fund's stated conditions, and backing is not
an endorsement of results. Technical evaluation and any security disclosure stay independent of
funding. Suspected live vulnerabilities go through each client's private disclosure channel
([SECURITY.md](SECURITY.md)).

The most useful contribution from a client team is technical: run the witness matrix or the pilot
on one PR, and tell us whether it saved review time or added noise.

## Development

```bash
pip install -e ".[dev]"
ruff check . && python -m pytest -q
```

Layout: `src/` holds the CLI, analyzers, fetchers, witness engine and rulebooks (`src/rules/`).
`scripts/` holds the scoreboard and client fetch scripts, `pilot/` the Besu kit and live request,
`docs/evidence/` dated raw results, and `demo/` the video sources. The full history is in
[CHANGELOG.md](CHANGELOG.md).

## License

MIT. [Fosurero/PRSpec](https://github.com/Fosurero/PRSpec)
