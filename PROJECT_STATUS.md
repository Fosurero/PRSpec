> **Latest:** Targeted retrospective test on real Besu PR #5786: one relevant candidate before the fix, none after for the selected EIP-4844 requirement, using Meta Wonder. Three files were combined; no verifier or Besu runtime was used. This is not a newly found bug or a demonstrated CI workflow. See [case evidence](docs/evidence/2026-11-10/besu-pr5786/README.md).

> **Update:** The primary Besu case walkthrough is [`pilot/besu/DEMO.md`](pilot/besu/DEMO.md). It reproduces M5, replays the recorded Meta review, and runs a fresh M2 deterministic check. Gemini is optional and is not a prerequisite for the Meta demo. GitHub Actions billing remains a separate issue. The older status entries below preserve the original timeline.

# PRSpec project status

_Last updated: 2026-11-10 07:45 UTC · branch `evidence-pilot` (pushed) · version 2.0.0 (untagged)_

## ملخص بالعربي

_آخر تحديث 2026-11-10 07:45 UTC._

- **اتعمل واتتحقق منه:** طبقة witness حتمية لـ EIP-1559 وEIP-4844 على Besu وGeth وNethermind: 34 مطابق و0 مختلف، و2 من غير anchor. نفس الفحص شغال كمان على الفروع الحالية للعملاء. Fork Watch على تاريخ EIP-4844 الحقيقي، وعمود witness بيمسك 4 من 10 من غير API key. الفرع `evidence-pilot` اترفع على GitHub. 210 اختبارات ناجحة.
- **أول نتيجة LLM كاملة (Meta Muse، مش Gemini):** الـ 10 mutations على `muse-spark-1.3`: 6 confirmed و1 flagged و3 inconclusive و0 missed و0 errors. على كود Besu النظيف طلع 33 ملاحظة، والتحقق رفضها كلها، فمفيش أي false positive مؤكد. دي تجربة واحدة، مش نسبة اكتشاف.
- **Gemini:** المفتاح شغال. `gemini-3.8-flash` كان بيرجع 503 طول اليوم. تجربة M3 على `gemini-3.6-flash` طلعت confirmed. التشغيل الكامل متوقف لأن المفتاح free tier وحده 20 طلب في اليوم لكل موديل.
- **عوائق عند Safi:** GitHub Actions رافض يشغّل أي job بسبب قفل في الفوترة على الحساب، و`GEMINI_API_KEY` محتاج تفعيل الفوترة عشان التشغيل الكامل.
- **ممنوع ادعاؤه:** أي نسبة اكتشاف أو تكلفة لـ Gemini، ونجاح CI أو Docker على GitHub.

## Initial audit (requested sections)

### A. Decisive feature: Fork Watch + Witness

- **Planned** (plan page, Nov 2026): rulebook of atomic MUST/SHOULD/MAY rules from a pinned EIP; map to
  client code; LLM-written EEST-format witness verified on EELS; run on clients; drift radar per merged
  spec PR; a PoC in 48 h (Geth predeploy witness, or Nethermind #14030 replay, or EIP-7928 rulebook).
- **Before this session:** proposal only. No code, no tests. The Geth predeploy PoC is moot (fixed upstream
  in `26d0b2171`, covered by EEST).
- **Implemented now (verified):** a *deterministic* slice: `src/witness.py`, rulebooks
  `src/rules/eip-1559.yaml` (3 rules) and `eip-4844.yaml` (9 rules, with historical-name aliases), anchors
  for Besu/Geth/Nethermind, `prspec witness`, `prspec fork-watch`, 11 tests, evidence in
  `docs/evidence/2026-11-10/`. Demonstrable today: cross-client matrix (34/34), historical drift replay
  (exactly the 3 constants changed by EIPs `2511e0bc` fail), impact card.
- **Not implemented:** LLM-generated EEST witnesses, EELS verification, `t8n`/`consume` runs, the PR
  watcher service, MUST/SHOULD/MAY extraction from prose, the Nethermind #14030 replay (EIP-8272 is
  algorithmic, not a constant, so it needs the LLM layer or executable witnesses).
- **To make the full feature demonstrable:** ROADMAP C1 + C2.

### B. Besu demo: Pilot Kit

- **Planned:** one-page explainer; read-only, non-blocking workflow with paths filter, minimal
  permissions, SHA-pinned actions; secret-free PR job + `workflow_run` LLM job; job summary + artifacts +
  at most one folded comment; distinct exit codes; `prspec.besu.yaml`; replay of 3–5 historical PRs;
  10-mutation scoreboard; 2-minute video; limitations section.
- **Delivered (before this session, on `evidence-pilot`):** `pilot/besu/README.md`, `prspec.besu.yaml`,
  workflow pair, exit codes, pre-registered `mutations.yaml`, `scripts/mutation_scoreboard.py`,
  `besu-mutation-scoreboard.yml`.
- **Added now:** witness column (4/10 caught deterministically, verified), Gemini 3.8 Flash pin,
  `config/` added to the Besu sparse checkout (needed by witnesses), `gemini-live.yml` that runs the
  scoreboard from `evidence-pilot` without merging to `main`.
- **Missing:** an actual Gemini scoreboard run; replay of historical Besu PRs; a run inside a Besu fork;
  SARIF output; the video (pipeline in `demo/`, final cut waits for live results); the message to
  Sally (draft exists in Notion, not sent; must not be sent before the live results exist).
- **Reproducible by another developer?** The deterministic part: yes, with `scripts/fetch_clients.sh`
  and the commands in `VERIFICATION.md`. The Gemini part: yes once they have a key; nothing depends on
  this machine.

### C. Post-demo release (planned v1.8.0 → now 2.0.0)

| Planned item | Status |
| --- | --- |
| Entry-point fix | Done (earlier), re-verified in a clean venv |
| Fail-closed exit codes | Done (earlier), extended to witness/fork-watch |
| Verification bound to claim identity | **Not done.** Score is still a vote ratio; README says so |
| Pinned SHAs and cache keys | Client commit: done. EIP text for `analyze`: still fetched from a live branch. Witnesses: pinned |
| GitHub Action wrapper + SARIF + step summary | Step summaries done; reusable Action + SARIF not done |
| `OPENAI_BASE_URL` / local provider + `--no-cloud` | Done (2.0.0) |
| Model presets separated from provider/params | Done for Gemini/OpenAI/local (config + env overrides) |
| `pilot besu` command + replay mode | Not done (the kit uses the scoreboard script instead) |
| Soften "no other tool" README claim | Done; README rewritten for 2.0 |
| Version number | 2.0.0 (per maintainer), not 1.8.0 |

**Before publishing 2.0.0:** (1) push `evidence-pilot`, CI green incl. Docker job; (2) Gemini live run
completed and results committed under `docs/evidence/`; (3) video final cut; (4) PR to `main`, review,
merge, tag `v2.0.0`, GitHub release with notes from `CHANGELOG.md`.

## Blockers

_Updated 2026-11-10 07:25 UTC._

1. **GitHub Actions cannot start any job: "your account is locked due to a billing issue".** The push of
   `evidence-pilot` (`f3c2f7a`) triggered CI run `42772789938` and Gemini live run `42772789877`; every job
   failed before its first step with that annotation. No runner time and no API calls were used. Fix is on
   the account owner's side (GitHub → Settings → Billing and plans). Until then CI, the Docker job and the
   repository-secret Gemini run cannot be verified on GitHub.
2. **The Gemini key Safi shared is on the free tier: 20 `generate_content` requests per day per model**
   (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, quotaValue 20). The pre-registered scoreboard needs
   roughly 19 primary calls plus verification calls, so one model cannot complete it in a day on this key.
   `gemini-3.8-flash` additionally returned 503 "high demand" on every probe. Options: enable billing on the
   Google AI project (paid-tier cost not measured yet; the M3 smoke used about 92k tokens) or split the run across days.
3. **No Docker daemon** on the agent machine; the Dockerfile is only verifiable by the CI job (blocked by 1).
