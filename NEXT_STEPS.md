# Next steps (exact, in order)

1. **Push `evidence-pilot`.** Requires GitHub credentials with write access to `Fosurero/PRSpec`
   (e.g. `gh auth login` device flow). If the machine that ran this session is gone, apply the exported
   work instead: `git fetch prspec-2.0.bundle evidence-pilot:evidence-pilot` or
   `git am PRSpec-2.0-*.patch` on top of `ae66a3e`.
2. **CI must be green** on the push: jobs `test` (3 Pythons), `docker`, `witness-live-clients`.
   If `witness-live-clients` fails, that is information: read the matrix (a client moved/changed a
   constant) before touching anchors.
3. **Gemini live run.** The push includes `pilot/live/REQUEST`, which triggers `gemini-live.yml`.
   Check the probe step first: if `gemini-3.8-flash` is not visible to the key, rerun with another id
   from `models.txt` by editing `model=` in `pilot/live/REQUEST`. Quota errors show up as `ERROR`
   rows and exit 20; rerun with `only=M3,M5,M9` to reduce calls.
4. **Publish the results**: download the `gemini-live` artifact
   (`gh run download <id> -n gemini-live -D docs/evidence/<date>/gemini-live`), commit it, and update
   README §Verified results with the *actual* numbers (detected / missed / inconclusive / errors,
   baseline false-positive candidates, tokens, wall time). Hand-triage baseline candidates.
5. **Video final cut**: `python demo/build_video.py --live docs/evidence/<date>/gemini-live` →
   `demo/out/prspec-2.0-demo.mp4`. Watch it end to end before sharing.
6. **Release**: PR `evidence-pilot` → `main`; review; merge; tag `v2.0.0`; GitHub release from
   `CHANGELOG.md`; optionally push the Docker image to GHCR.
7. **Outreach (only after 4–6):** Besu #9850 follow-up (draft in Notion), Nethermind (Łukasz Rozmej,
   flcl42) with the witness matrix + spec-drift replay, Griff (cutoff date, pledge mechanics).

Open engineering items (ROADMAP B/C): verification bound to claim identity; EIP text pinning in
`analyze`; SARIF + reusable Action; Besu historical-PR replay; fork-aware blob schedules.
