# Historical Besu PR #5786: targeted before/after evaluation

## Question
Can PRSpec flag the EIP-4844 excess-blob-gas mistake that Besu fixed in [PR #5786](https://github.com/besu-eth/besu/pull/5786), and stop flagging it after the fix? The issue and fix are publicly known, and were found and fixed by Besu contributors, not by PRSpec. This was an early EIP implementation; it is not a current mainnet vulnerability.

## Procedure
- Pre-fix Besu commit `19c989a6d96bb412f3815d14687da8cc334f1286`; post-fix commit `7605351c1ae86c955b28df90f66ede9c9c5f1386`.
- EIP-4844 at `ethereum/EIPs@eb2e7a97aa70b1d7f39968c6be9ed3e731512f9d` (the latest EIP-4844 revision before the PR fix). We selected the exact `calc_excess_blob_gas` paragraph and first-post-fork sentence, not the full EIP.
- One request per version via PRSpec's existing `Runner.analyze_file` using Meta `muse-wonder-1.0`. Each input joins the real `AbstractBlockCreator.java`, `ExcessBlobGasCalculator.java` and `CancunGasCalculator.java` from the corresponding commit. No PR description, patch or expected finding was provided in the prompt. This is a purpose-built targeted replay, not the default CLI or a CI workflow run. A public historical case may have been in model training data.
- Two analysis calls, no automated verifier. Inputs 5,961 / 5,960 tokens; outputs 4,229 / 1,072 tokens respectively. One earlier broader attempt was incomplete (`finish_reason=length`, 11,565 input and 8,192 output tokens); its [result](before-truncated.json) is retained. No billing statement was available.

## Results
Before the fix the model produced one finding at `AbstractBlockCreator.computeExcessBlobGas`, explaining that excess gas uses the current block's blobs instead of the parent's blob gas used, and suggesting the parent-header helper. After the fix it returned `FULL_MATCH` and zero findings for the selected requirement and supplied files. See the actual [before](before.json) and [after](after.json) outputs, [test configuration](manifest-focused.json) and [real Besu change](real-change.diff).

The code shows the pre-fix `int` overload converts the current blob count into gas; for zero parent excess and a current block of six blobs, that gives `6 × 131072 − 393216 = 393216`, whereas the first-post-fork rule gives zero. This is arithmetic from the source and spec, not a runtime Besu or EELS execution test.

## Limits
This is one retrospective case, selected with knowledge of the fix, with a hand-selected spec excerpt and source context. No statistical accuracy, independent verification, real-world deployment, runnable EEST test or CI integration was established. `FULL_MATCH` is a model label, not proof of overall correctness. The present generic CI draft analyzes registry files separately and is **not proven to detect this cross-file issue**. Broader independent evaluation on real PRs, cases with false-positive review, and integration in a client team's environment are future work; funding would support that work, not retroactively validate this result.
