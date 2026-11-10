# Next steps (exact, in order)

_Updated 2026-11-10 07:45 UTC. Branch `evidence-pilot` is pushed to GitHub. Do not merge into `main` or tag
without a new explicit approval from the maintainer._

1. **Unlock GitHub Actions (maintainer).** Every job is refused with "account is locked due to a billing
   issue" (runs `42772789938`, `42772789877`). Fix it under GitHub → Settings → Billing and plans, then
   re-run both runs from the Actions tab (or push any commit to `evidence-pilot`). Nothing else can make CI,
   Docker or the repository-secret Gemini run happen.
2. **CI must be green**: jobs `test` (3.10, 3.12, 3.13), `docker`, `witness-live-clients`. The witness job
   already passes locally against today's default branches (VERIFICATION row 16). If it fails in Actions,
   read the matrix before touching anchors.
3. **Gemini scoreboard.** One scoreboard needs about 22 primary calls plus about 2 verification calls per
   raised issue. That is well above the free tier's 20 requests per model per day. Choose one:
   - enable billing on the Google AI project behind the key (preferred), then re-run `gemini-live.yml`
     (edit `pilot/live/REQUEST`; `model=` is a preference list and the chosen model is recorded), or locally:
     `GEMINI_MODEL=<model> python scripts/mutation_scoreboard.py --besu-dir clients/besu --provider gemini --runs 1 --workers 2 --eips-dir clients/EIPs --out output/gemini-live/scoreboard`;
   - or, on the free tier, `--no-verify --only …` over several days (label it as unverified and partial).
   Retry `gemini-3.8-flash` first; it returned 503 "high demand" all day on 2026-11-10.
4. **Publish the Gemini results**: copy the artifact to `docs/evidence/<date>/gemini-live/`, update README
   §Verified results with the actual counts (detected, missed, inconclusive, errors), baseline candidates,
   tokens and wall time, and hand-triage the baseline candidates. Triage the 2 candidates from the M3 smoke run too.
5. **Video final cut**: `python demo/build_video.py --live docs/evidence/<date>/gemini-live` →
   `demo/out/prspec-2.0-demo.mp4`. Sample the encoded file and watch it end to end before sharing. The current
   shareable cut is `prspec-2.0-demo-meta.mp4` (Meta Muse results, labeled as not Gemini).
6. **Release (needs new approval):** PR `evidence-pilot` → `main`, review, merge, tag `v2.0.0`, GitHub release
   from `CHANGELOG.md`, optional GHCR image.
7. **Outreach (maintainer sends it himself, only after 4–6):** Besu #9850 follow-up, Nethermind, Griff.

Open engineering items: meter tokens of verification calls in the scoreboard; repeat runs (n > 1);
verification bound to claim identity; EIP text pinning in `analyze`; SARIF + reusable Action; Besu
historical-PR replay; fork-aware blob schedules.
