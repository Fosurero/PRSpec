# PRSpec 2.0 demo video

For the interactive Besu case walkthrough, see [pilot/besu/DEMO.md](../pilot/besu/DEMO.md). The older slide-based video below is not the main demo.

`demo/build_video.py` renders the demo as 1920×1080 HTML frames (Playwright + Chromium), then
joins them with `ffmpeg` cross-fades into an MP4. There is no narration or audio track.

Every number and table on screen is read from a file under `docs/evidence/`. Nothing is typed in by
hand, so the video cannot show a result that does not exist in the evidence folder.

## Build

```bash
pip install playwright        # uses the system chromium if present
python demo/build_video.py                                             # preliminary cut
python demo/build_video.py --live docs/evidence/<date>/gemini-live     # final cut
```

| Mode | Output | Gemini frame |
| --- | --- | --- |
| no `--live` | `demo/out/prspec-2.0-demo-preliminary.mp4` | says the live run has not happened |
| `--live DIR` | `demo/out/prspec-2.0-demo.mp4` | model, outcome counts, per-mutation table, tokens from `DIR/scoreboard/scoreboard.json` and `DIR/probe.json` |

`demo/out/` (frames + MP4) is generated and ignored by Git. Watch the whole MP4 before sharing it.

## Storyboard and sources

| # | Frame | Seconds | Source file(s) |
| --- | --- | --- | --- |
| 0 | Title: does the client code match the EIP text? | 6 | none (static text) |
| 1 | The problem: commits to the EIP-4844 text and parameter-table changes | 8 | `docs/evidence/2026-11-10/eip-4844-history.json` (from `git log -- EIPS/eip-4844.md` in ethereum/EIPs) |
| 2 | Layer 1, deterministic witness matrix (EIP-1559 + EIP-4844 × Besu, Geth, Nethermind) | 11 | `witness-1559.json`, `witness-4844.json` |
| 3 | Layer 2, Fork Watch on EIPs commit `2511e0bc` | 10 | `fork-watch-4844-2511e0bc.json` |
| 4 | Spec-drift replay: today's clients vs the spec before that commit | 11 | `witness-4844-at-2511e0bc-parent.json` |
| 5 | Besu pilot: 10 pre-registered mutations, witness column | 10 | `scoreboard-dry-run/witness.json` |
| 6 | Layer 3, live Gemini scoreboard | 12 | `--live DIR` (see above); placeholder text without it |
| 7 | Limits, stated plainly | 10 | none (static text) |
| 8 | Try it: commands | 10 | none (static text) |

File names in rows 2–5 are relative to `docs/evidence/2026-11-10/`. Exact durations are in the
`out.append((..., seconds))` calls in `build_video.py`.
