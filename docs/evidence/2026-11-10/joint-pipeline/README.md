# Joint pipeline: local verification only

This is **not** a live Meta evaluation or successful GitHub Actions run. No
model calls were made during this local check; model-call cost for the check was
zero. Actual billing and the remaining account budget were not checked.

- PRSpec base: `bf935bf25c2ece1433648f0bc5b3624efa4211fd`.
- Pipeline implementation: `b8fb6e0c11f314d0723594525635b8541dbd35bd`.
- Historical Besu before: `19c989a6d96bb412f3815d14687da8cc334f1286`; after:
  `7605351c1ae86c955b28df90f66ede9c9c5f1386`.
- Three public files in the existing `besu-pr5786/manifest-focused.json` were
  retrieved at each full SHA. The exact focused excerpt was checked to appear
  in `EIPS/eip-4844.md` at EIPs commit `eb2e7a97aa70b1d7f39968c6be9ed3e731512f9d`.
  Excerpt SHA-256: `c5cc2701cd64c5c8f9800200be6f2b01f8451bea673ef64702367e3d105c951d`.
- `_run_analysis` was called for each version with those three selected files,
  a local focused spec and a **stub analyzer**. It passed all three labeled
  files to one call, with combined UTF-8 sizes of 25,682 and 25,700 bytes.
  The stub returned `FULL_MATCH` for both: this is a wiring assertion, not
  inference, a finding, or a before/after comparison.
- At the historical after SHA, `BlobFeeMarket.java` from today's expanded
  EIP-4844 registry was not available at that path. Use the explicit three-file
  subset for this historical replay; the full-registry joint mode correctly
  reports incomplete if any mapped file is unavailable.
- Local `ruff check .`, `pytest -q` and `git diff --check` passed: 225 passed,
  2 skipped. The draft workflow uses the full pinned EIP rather than the
  focused excerpt, and its model behavior has not been tested.

Next: publish the PRSpec commit before using it as the workflow pin; provide an
authorized working Actions test repository and its Meta secret; then perform
bounded live analysis, record actual usage and screen capture, and test the
workflow's trigger, association checks, report artifacts, failure paths and
fork rejection. A byte cap and an output-token cap are not a dollar budget.
Do not run untrusted PR code, transmit credentials to the model, or present a
recorded response or stub result as a live run.
