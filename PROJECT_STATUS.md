# PRSpec project status

_Last updated: 2026-11-10 (UTC) · branch `evidence-pilot` · version 2.0.0 (untagged)_

## ملخص بالعربي

- **اتعمل واتتحقق منه:** طبقة witness حتمية (من غير LLM) لـ EIP-1559 وEIP-4844 على Besu وGeth وNethermind: 34 فحص، 34 مطابق. Fork Watch على تاريخ EIP-4844 الحقيقي. عمود witness في الـ mutation scoreboard بيمسك 4 من 10 من غير API key. تحديث Gemini (الافتراضي `gemini-3.8-flash`). مزود محلي مع `--no-cloud`. Dockerfile. CI جديد. الإصدار 2.0.0. 210 اختبارات ناجحة، بالإضافة إلى تكامل Meta Muse واختبار حي على مثال اصطناعي واحد.
- **ناقص:** تشغيل Gemini الحي والـ scoreboard: طلب التوليد رجّع 503 وقت الفحص. سر `GEMINI_API_KEY` موجود في GitHub Actions، لكن لم نتحقق من قيمته أو نشغّل الـ workflow. توكن GitHub الذي قدّمه المستخدم أثبت صلاحية الوصول والـ push، لكن الفرع لم يُرفع بعد. الفيديو النهائي مستني نتايج تشغيل Gemini.
- **ممنوع ادعاؤه:** أي نسبة اكتشاف أو false positives أو تكلفة لـ Gemini، لحد ما التشغيل يتم فعلًا.

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

1. **No `GEMINI_API_KEY` in this environment.** The secret exists in GitHub (per maintainer) and is only
   usable from Actions. → `gemini-live.yml` runs it from `evidence-pilot`.
2. **No push access from this environment** (no GitHub credentials; earlier sessions got 403). Work is
   committed locally and exported as a git bundle + patch series (see `NEXT_STEPS.md`).
3. **No Docker daemon** here; the Dockerfile is verified only by the CI job once pushed.
