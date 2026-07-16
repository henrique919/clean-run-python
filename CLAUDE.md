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
8. **Agents never receive or request owner credentials; QA accounts only.**
 Anything requiring authenticated production access is flagged for the
 owner instead.

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
- Dashboard "Issued" KPI counts issued + in_progress together (accepted).
- One-time owner check: confirm the instance type in the Render dashboard
 matches render.yaml `starter`. Paid Starter instances do not spin down
 (only Free does) — no code work; dashboard verification only.

Shipped and removed from this list: expired-thumbnail recovery
(`/api/photos/refresh-url` + client onerror, PR #44), Share Report mid-size
images (`SHARE_IMAGE_WIDTH=1200` in `app/storage.py`, PR #44), and field
alias matching ("Level 1" → "L01", `app/parse_fields.py` +
`tests/test_parse_fields.py`).
