# Besu pilot: reproducible walkthrough

This is a limited, advisory demonstration; it is not a completed deployment in Besu CI.
No source code is sent to an LLM in the key-free steps below.

## Recorded results (no setup)

- [Meta Muse Spark scoreboard](../../docs/evidence/2026-11-10/meta-live/scoreboard/scoreboard.md): 10 intentionally injected deviations; 6 confirmed by automated review, 1 flagged, 3 inconclusive. These are not newly discovered Besu bugs.
- [EIP-1559 witness matrix](../../docs/evidence/2026-11-10/witness-1559.md): mechanically compared constants against pinned client files.
- [Mutation definitions](mutations.yaml) and [raw results](../../docs/evidence/2026-11-10/meta-live/scoreboard/scoreboard.json).

## The main demonstration: a code change and a reviewable finding

Case M5 intentionally changes `int i = 1` to `int i = 2` in Besu's `BlobFeeMarket.fakeExponential`. PRSpec's recorded Meta Muse run points to the EIP-4844 rule, explains the discrepancy and suggests the one-line fix. The finding passed two automated review rounds; this is **not** human-confirmed and is **not** a discovered defect in Besu. This semantic example is a replay of a recorded API result, not a live call. A separate M2 constant check runs fresh and locally.

After the setup below, run the walkthrough:

```bash
python pilot/besu/demo.py --besu-dir ../clients/besu --eips-dir ../clients/EIPs
```

It validates the fresh M5 patch against the recorded one, shows the diff and recorded finding, and runs a fresh M2 witness. Outputs go into `output/besu-case-demo/`. No API key or cloud call is required.

## Setup and key-free checks

From the root of a PRSpec checkout (Python 3.10+ and Git required):

```bash
python -m venv .venv
. .venv/bin/activate
pip install .
scripts/fetch_clients.sh ../clients 8f01c7a3200780b00163ab76d544e0ef6646da41 c863eecbddb2c9db2cd2f07bb1db80740d75a5b3 8ba0b6d05ea0b036524658f5ba1b6d14afd8f20e 542e62eb129517130b7facc52bbb9a1f333c711e
prspec witness --eip 1559 -t besu=../clients/besu --eips-dir ../clients/EIPs --markdown besu-witness.md
python scripts/mutation_scoreboard.py --besu-dir ../clients/besu --eips-dir ../clients/EIPs --dry-run --out output/besu-demo
```

The first check compares three selected constants to the pinned spec; a match is not proof of behavioral compliance. The dry run validates the mutation inputs and runs deterministic checks; it does **not** perform model analysis. See the [pilot kit](README.md) for the draft GitHub Actions configuration. It currently uses Gemini, requires a repository secret, and has not been tested in Besu CI. Meta is supported by PRSpec, but that draft workflow is not a tested Meta workflow.

## Additional focused Meta Wonder experiment

A separate two-call experiment compared this exact file clean and with M5 using the stronger `muse-wonder-1.0`. It described the injected index error, but the original keyword scorer marked the comparison inconclusive because a different clean-file concern mentioned the same function. This was not independently verified and used a different specification input from the earlier Spark scoreboard. [Results and raw outputs](../../docs/evidence/2026-11-10/meta-wonder-case/README.md).

## Live Meta analysis (optional, billable)

Set `MODEL_API_KEY` securely in your environment (do not commit it); source code and EIP text are sent to Meta. With the same pinned checkouts:

```bash
prspec analyze --provider meta --eip 1559 --client besu --source-dir ../clients/besu --output markdown
```

This is a fresh cloud analysis, not a replay of the recorded scoreboard. Review its outputs; provider failures or missing files are not a clean result. Model can be configured using `META_MODEL`.
