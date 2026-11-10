# Next steps

PRSpec Evidence Pilot is a preliminary demonstrator; Meta Muse is a supported provider and the recorded Meta scoreboard can be used independently of Gemini. The paid Meta key does not fix GitHub Actions billing.

1. Review [the Besu walkthrough](pilot/besu/DEMO.md), recorded evidence, and limitations with a maintainer. The draft GitHub Actions integration is Gemini-based and has not run inside Besu CI.
2. Unblock GitHub Actions account billing, then run CI and Docker; previous runs were refused before starting. Do not describe them as verified.
3. Review the 33 raw baseline findings by a human to measure false positives. Repeat experiments, meter verification tokens, and evaluate a real historical Besu case before claiming general performance.
4. Gemini is optional for a separate comparison, not a prerequisite for the Meta demo. Do not enable its billing or incur extra calls merely to deliver this demo.
5. No release tag until the owner decides the pilot is ready; owner sends outreach himself. Do not store keys in the repository.

Engineering backlog: verification claim identity, EIP pinning in analyze, SARIF, historical-PR replay, executable EEST witnesses verified by EELS, and fork-aware blob schedules.
