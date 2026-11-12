# Besu pilot, end to end on a fork (2026-11-12)

All runs below happened on GitHub-hosted runners in the fork `Hardisky/besu`, with live model requests.
Nothing was edited after the runs.

| What | Link | Outcome |
| --- | --- | --- |
| Fork PR: comment-only change to `AbstractBlockCreator.java`, base `prspec-demo-base` | [Hardisky/besu#1](https://github.com/Hardisky/besu/pull/1) | DCO and `PRSpec pilot (trigger)` passed |
| Pilot (`workflow_run`, read-only, never blocks) | [run 43131616614](https://github.com/Hardisky/besu/actions/runs/43131616614) | success in 2 min 15 s, artifact `prspec-report` |
| Live recording (fork-only recorder) | [run 43132014617](https://github.com/Hardisky/besu/actions/runs/43132014617) | success in 6 min 25 s |
| Evidence: video, transcript, reports, pilot artifacts and logs, manifest | [`prspec-evidence/runs/43132014617`](https://github.com/Hardisky/besu/tree/prspec-evidence/runs/43132014617) | secret scan: 36 files, 0 hits |

**Video:** [`prspec-besu-live-demo.mp4`](https://github.com/Hardisky/besu/raw/prspec-evidence/runs/43132014617/prspec-besu-live-demo.mp4), 1920×1080, 15 fps, 5 min 10 s. ffmpeg captured the
runner's Xvfb screen in real time: xterm running PRSpec, then Chrome showing the HTML report, the PR and
the pilot run. There are no cuts, slides or overlays. [Terminal transcript](https://github.com/Hardisky/besu/blob/prspec-evidence/runs/43132014617/terminal-transcript.txt).

## Pins

- PRSpec `Hardisky/PRSpec@7cf99adc66ee843ae87061e79fa27cd294ac4fcf`
- ethereum/EIPs `eb2e7a97aa70b1d7f39968c6be9ed3e731512f9d`, `EIPS/eip-4844.md` SHA-256 `ef1316135b93e7ca…`
- Besu before the #5786 fix `19c989a6d96bb412f3815d14687da8cc334f1286`, after it `7605351c1ae86c955b28df90f66ede9c9c5f1386`;
  fork `main` `ad5eb36a7e5b` (upstream `main` plus the two pilot workflows)
- Model order: `gemini:gemini-3.8-flash`, `gemini:gemini-3.6-flash`, `meta:muse-wonder-1.0` (first complete answer wins)

## Results

| Run | Besu code | Result (Meta `muse-wonder-1.0`, one joint request) |
| --- | --- | --- |
| Fork PR [#1](https://github.com/Hardisky/besu/pull/1) → [pilot run](https://github.com/Hardisky/besu/actions/runs/43131616614) | fork `main` + a comment-only change; 8 mapped EIP-4844 files | FULL_MATCH, 0 findings; job green in 2 min 15 s, never blocks (input 17,953, output 8,895 tokens) |
| Replay before the [#5786](https://github.com/besu-eth/besu/pull/5786) fix | `19c989a6`, 3 files | 5 findings. The HIGH one is the bug #5786 fixed: the header `excessBlobGas` is computed from the current block's blobs and would be double-counted on the next block (input 11,578, output 11,405 tokens, 131.8 s) |
| Replay after the fix | `7605351c`, same 3 files | Excess-blob-gas formula judged to match the spec; the 7 remaining items are mostly requirements that live outside the 3 supplied files (input 11,577, output 8,090 tokens, 78.6 s) |

[`compare.txt`](compare.txt) is the before/after comparison printed in the recording, and
[`pilot-pr-report.md`](pilot-pr-report.md) is the pilot's report for PR #1. The full before/after reports
(JSON, Markdown, HTML) are in the evidence branch.

## What failed

Both Gemini models returned `401 UNAUTHENTICATED: API key not valid` (reason
`ACCESS_TOKEN_TYPE_UNSUPPORTED`) for the fork's `GEMINI_API_KEY` secret, in the pilot and in the recording.
No Gemini answer was produced. The failed attempts are kept (`attempts/`, `failed/`), and the Meta fallback
produced every result.

## Limits

- Each case ran once. Model output is not deterministic, and confidence is model-reported, not calibrated.
- #5786 and its fix are public, so the replay shows recognition of a known bug, not a new discovery.
- After the fix, most of the 7 items concern requirements in files that were not supplied (scope gaps,
  not confirmed defects). The note about the two `computeExcessBlobGas` overloads is a candidate to
  review, not a verified bug.
- FULL_MATCH on the fork PR covers the 8 mapped files only and is not proof of compliance.
- Not run inside `besu-eth/besu`. Meta request cost was not measured; token counts are reported instead.

## Reproduce

On a Besu fork with the secret `GEMINI_API_KEY` (optionally `PRSPEC_META_API_KEY` for the fallback): copy
[`pilot/besu/workflows/`](../../../../pilot/besu/workflows/) to `.github/workflows/` on `main`, open a PR
that touches a mapped file, then push [`pilot/besu/live-demo/`](../../../../pilot/besu/live-demo/README.md)
to a `prspec-demo-record` branch.
