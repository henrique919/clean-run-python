# CleanRun IQ — Claude Code Onboarding Pack

Two parts. Part 1 is a CLAUDE.md file — commit it to the repo root (`/CLAUDE.md`), and Claude Code will read it automatically at the start of every session. Part 2 is the first task prompt, a small calibration batch to prove the workflow before it gets anything big.

**Timing rule: do not start Claude Code on this repo until Cursor's performance PR (fixes 1+2+3+5) is merged and verified. One agent per PR, always.**

---

## PART 1 — Commit this as `CLAUDE.md` in the repo root

```markdown
# CLAUDE.md — CleanRun IQ working rules

## What this product is
CleanRun IQ is a construction defect capture and closeout app for the Australian
market (app.cleanruniq.com). Core loop: site manager captures defects with photo
evidence on a phone → issues to subcontractors → subs upload rectification
evidence → supervisor reviews and closes → closeout/handover reports.
The product promise is SPEED and SIMPLICITY in the field: "30 defects in under
20 minutes", one-handed phone use, no training required. Every change is judged
against that. The owner is a non-coder tradesman-founder: explain technical
decisions in plain English in all summaries.

## Repo and deployment truth
- THIS repo serves production. FastAPI app (`app/main.py`), started via
  `python app.py`, hosted on Render (service: cleanrun-iq-python).
- **Merging to `main` auto-deploys to production.** Never merge without the
  owner's explicit approval ("Yes, proceed" or equivalent). Open a PR, post a
  summary, STOP.
- The live UI is `CleanRun-IQ-Full-App-Render3/` (index.html + assets/
  enhancements.js + assets/enhancements.css). Vanilla JS enhancement pattern —
  NO new frameworks, NO build tooling, NO npm dependencies.
- Other `CleanRun-IQ-*` folders are historical exports. Do not edit them.
- Every UI change bumps the build tag (cardsNN) in index.html and the test
  files that assert it.
- Supabase is the backend store (items, photos in `cleanrun-evidence` bucket,
  signed URLs with transforms for thumbnails). No schema, RLS, or auth changes
  without explicit approval.
- Render PR previews: label a PR `render-preview` (or `[render preview]` in
  title) to get a *.onrender.com URL. Previews share PRODUCTION Supabase env
  vars — test captures create real data; use a sandbox project.
- OpenAI is wired for voice/note parsing (`OPENAI_API_KEY`,
  `OPENAI_PARSE_MODEL`, default gpt-4o-mini). All AI calls must fail silent
  and degrade to non-AI behaviour; AI must never block capture.

## Non-negotiable working rules
1. **Inspect before coding.** Post a short plan of files/functions to touch,
   then implement. No rebuilds, no rewrites, no "while I was in there".
2. **Scoped batches.** Implement exactly the tasks given, nothing else. Any
   behaviour change beyond the tasks must be declared under "Behaviour changed
   beyond the tasks" and justified, or reverted.
3. **Do-not-break list is verified, not assumed.** Golden path: capture with
   photo (camera, iOS Safari) → markup (arrow, save marked-up copy) → Save +
   Next loops with walk counter → item appears on Items list → visible in
   reports. Plus: sticky capture defaults, photo-required validation,
   voice Speak Item / Draft form from note, all six report types, Review
   Queue, Subcontractor Mode, Project Setup.
4. **iOS Safari is the primary target.** Desktop-only APIs have already caused
   a P0 (createImageBitmap orientation options). Feature-detect; anything
   touching capture/photos/markup gets flagged for phone QA on a PR preview
   before merge.
5. **Run the test suite** (`python3 -m pytest tests/ -q`) before posting a
   summary. Add tests for new behaviour following existing patterns
   (test_phaseNN_checklist.py).
6. **Summary format, every PR:** Files changed · Plan vs implemented ·
   Each task done/partial/blocked (one line each) · Do-not-break item-by-item
   pass/fail · Manual checklist results, stating what needs phone QA ·
   Behaviour changed beyond tasks (must be empty or justified) · Known risks
   or follow-ups. Then STOP for approval.
7. **Measure before optimising.** Performance work reports numbers first,
   proposes ranked fixes, waits for approval.

## Product decisions already made (do not relitigate)
- Status vocabulary: Captured / Issued / In Progress / Ready / Rejected /
  Overdue / Closed — identical wording in filter chips, cards, detail, reports.
  Status chips show status only; actions (Re-issue) are separate buttons.
- Colours: Overdue red, Ready BLUE (#1D4ED8), Closed/complete GREEN, Issued
  gold, Captured neutral. Green means done, blue means action available.
- Markup NEVER auto-opens after photo attach. User-initiated only. Default
  tool is Arrow.
- Walk mode is the default capture state.
- Thumbnails: single centre-crop (Supabase transform cover at 2x card size +
  CSS object-fit cover on 142×108). Full-size views use originals.
- Capture defaults chip strip: collapsed after first save, expanded when no
  project defaults exist; validation errors auto-expand their section.
- Descriptions from voice/typed notes are AI-cleaned (defect statement only,
  location/trade/assignee stripped ONLY when mapped to fields); manual
  descriptions are never overwritten.
- Priority: High/Urgent only. Item types: Defect / Incomplete / Client Defect.

## Deferred — do not build unless explicitly asked
Subcontractor logins/portal, floor-plan pin-drop, integrations, custom report
builder, enterprise dashboards, server-side PDF, offline sync rework,
multi-worker hosting changes, item-data caching (signed-URL caching is fine).

## Known follow-ups (logged, build only when assigned)
- Expired-thumbnail recovery: onerror re-sign/refresh for signed URLs older
  than TTL while a tab stays open.
- Share Report file size: inline mid-size transforms (~1200px) instead of
  originals; ~5.7MB at 15 items today, linear growth.
- Dashboard "Issued" KPI counts issued + in_progress together (accepted).
- Field extraction is substring-only ("L01" won't match "Level 1").
- Rename/verify Render instance type vs render.yaml `starter`.
```

---

## PART 2 — First Claude Code task (calibration batch)

Paste this as the first prompt after CLAUDE.md is committed and the Cursor perf PR is merged:

---

Read CLAUDE.md in the repo root and follow every rule in it. This is your first batch on this codebase — it is deliberately small, and it is partly a test of the working process: inspect first, scoped implementation, full summary format, PR, stop before merge.

**Batch: resilience follow-ups (two logged items from CLAUDE.md).**

**Task 1 — Expired/failed thumbnail recovery.**
Signed image URLs are issued on state load and cached server-side. If a tab stays open past expiry (or a signed URL fails for any reason), images render broken until a manual reload. Add a lightweight client-side recovery in enhancements.js: on an image element's error event, request a fresh signed URL for that photo (add a minimal endpoint if none exists that re-signs a single storage path — reuse the existing signing/cache code in app/storage.py; no new patterns) and retry once. If the retry fails, show the existing placeholder styling, not a broken-image icon. Must not fire retry loops (guard against repeated errors per element).

**Task 2 — Share Report weight.**
shareReport() currently inlines ORIGINAL images as base64 (~5.7MB at 15 items, growing linearly). Change the share/inline path only to fetch mid-size transformed versions (~1200px width, quality similar to current uploads) via the existing transform signing, falling back to the original if a transform fetch fails. Print/preview in-app rendering is unchanged. Report the before/after file size for the current Esplanade Drive register in your summary.

**Do-not-break (verify per CLAUDE.md golden path, plus):** report generation and print page breaks; Share on desktop (download fallback) and the shared file opening with intact images in an email client; thumbnail loading and lazy-load on the Items list; the server-side URL cache behaviour from the recent performance PR.

**Acceptance:** a forced-failure image (temporarily bad URL in dev) recovers on error exactly once then placeholders; shared register file size drops materially (state the number); no visual change anywhere else.

PR with `render-preview` label, summary in the CLAUDE.md format, stop for approval.

---

## Why this first task
Both items are real (logged during earlier batches), self-contained, low-blast-radius, and they touch enough of the system (client JS, storage signing, reports, share path) to prove Claude Code has actually absorbed the repo's patterns — without letting it near the capture screen or the data model on day one. If the summary comes back in format, honest about what needs phone QA, with no unrequested changes: promote it to Phase 3 (sub notifications on issue, report photo compression, field-first Home rebalance). If it comes back with "I also took the liberty of…": you know what to do.
