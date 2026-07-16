# CleanRun IQ — Loop Backlog

This file is the single source of truth for the autonomous work loop.
It is only trusted **on `main`**: every loop iteration reads it from a fresh
checkout of `origin/main`, never from a branch. A task is DONE only when its
checkbox is ticked here on `main` — the tick is made inside the task's own
implementation PR, so merging the PR is what records completion.

Verified against `origin/main` at commit `37adbd1` on 2026-07-16.

## How agents use this file (short form — full protocol is in the loop prompt)

- One task per iteration. Pick the **top-most eligible** task.
- Eligible = checkbox unticked, not marked **OWNER TASK**, and every listed
  dependency already ticked.
- The branch name and the PR title must contain the task ID.
- If any open PR title contains a backlog ID, the only permitted work is
  addressing review feedback on that PR. One open loop PR maximum, ever.
- A blocked task gets a short **Blocked:** line added under its entry (with
  evidence), committed via its own small PR — never a speculative workaround.
- If nothing is eligible, stop and report `BACKLOG COMPLETE / BLOCKED ON OWNER`
  with the reason for each remaining task. Never invent new work. Anything on
  CLAUDE.md's "Deferred — do not build" list is out of bounds regardless.

## Owner legend (plain English)

- **Owner gate** — nothing ships until you reply "Yes, proceed" on the PR.
  Every PR the loop opens is a draft; you are the only person who merges.
- **Phone QA** — must be tested on your phone (iOS Safari) on a Render
  preview link before you approve.

---

## Tasks (priority order)

### - [x] AUTH-01 — Secure-login readiness audit (report only) — done: `docs/AUTH-01-secure-login-audit.md`

- **Plain English:** Today anyone who opens app.cleanruniq.com gets full admin
  access without logging in. Before we turn logins on, this task writes a
  report explaining exactly how to do it safely — no code or settings change
  at all in this task.
- **Scope guard:** REPORT ONLY. No code changes, no env changes, no Supabase
  changes, no Render changes. The only files this PR may touch are the new
  report and this backlog file.
- **Expected files:** `docs/AUTH-01-secure-login-audit.md` (new),
  `LOOP_BACKLOG.md` (tick this box).
- **The report must contain, in plain English:**
  1. The full activation path, traced in code with file/line references:
     `login_required()` in `app/config.py` → `_authenticate()` /
     `_open_access_user()` in `app/auth.py` → expected JWT claim shape
     (`app_metadata.cleanrun`, per `SECURITY.md`) → the Render3 login screen
     (`renderLogin`/`loginRequired` in
     `CleanRun-IQ-Full-App-Render3/index.html`).
  2. Exact activation steps, clearly split into (a) repo changes that go
     through a PR, and (b) Render **dashboard** environment changes only the
     owner can make (note: dashboard-set env vars vs `render.yaml` values —
     state which wins and why it matters).
  3. A prerequisites checklist: which accounts must exist and exactly what
     `app_metadata.cleanrun` claims each needs (company_id, company_role,
     project_roles, subcontractors, demo_admin).
  4. What a logged-out or token-expired user experiences **mid-session on
     iOS Safari** specifically (401 handling in the Render3 `api()` wrapper,
     unsent offline queue, in-progress capture).
  5. A rollback runbook: the single env-var flip that restores open access,
     step by step, written for a non-coder.
  6. The phone-QA script to run on a `render-preview`-labelled PR preview
     before activation (login, wrong password, capture, logout mid-session,
     token expiry).
- **Evidence (verified 2026-07-16):** `render.yaml:34-35` has
  `CLEANRUN_LOGIN_REQUIRED: "false"`; `_open_access_user()`
  (`app/auth.py:101`) grants `company_role="admin"`,
  `project_roles={"*": "project_manager"}`, `is_demo_admin=True` to anonymous
  visitors; `_authenticate()` (`app/auth.py:285`) short-circuits to it when
  `login_required()` (`app/config.py:25`) is false.
- **Task-scoped do-not-break:** production behaviour must be byte-identical —
  this PR contains documentation only.
- **Risk:** none (docs only). **Phone QA:** no. **Owner gate:** merge approval.

### - [ ] AUTH-02 — OWNER TASK: provision and verify QA/admin accounts

- **Plain English:** Two pieces of earlier login work need to be in place
  before we can turn logins on, and one of them only exists on your computer.
- **What the owner must do (agents must NOT do this):**
  1. Push `scripts/provision_launch_admins.sql` from your machine to GitHub —
     it is not in the repo today (verified: `scripts/` contains only
     generate/migrate/perf scripts).
  2. ~~Push commit `eba7129` ("Add gated QA access mode")~~ — **already
     done**: `eba7129` is the tip of the `codex/stability-health-pass` branch
     on GitHub (verified 2026-07-16; it sits 142 commits behind `main`).
     Nothing to push — the AUTH-03 agent will cherry-pick it onto a current
     branch. Do not delete that branch.
  3. Create (or confirm) the QA and admin accounts in Supabase with the
     `app_metadata.cleanrun` claims listed in the AUTH-01 report, using the
     SQL script above. Agents never receive or request your credentials —
     QA accounts only.
- **How to record completion:** tick this checkbox yourself on GitHub (edit
  this file on `main`), or tell the assistant "AUTH-02 is done" and the next
  iteration will verify (SQL script visible on `main` + your confirmation)
  and tick it in the AUTH-03 PR.
- **Risk:** n/a (owner-executed). **Owner gate:** entire task.
- **Agents:** do not re-derive the SQL script or the gated-QA-access work.
  If AUTH-02 is unticked, AUTH-03 is blocked — skip past it.

### - [ ] AUTH-03 — Secure-login activation PR (depends: AUTH-01, AUTH-02)

- **Plain English:** The pull request that actually turns logins on. It gets
  prepared by the agent, tested on your phone via a preview link, and only
  goes live when you say "Yes, proceed" and merge it.
- **Scope:**
  1. Flip `CLEANRUN_LOGIN_REQUIRED` to `"true"` in `render.yaml` (repo change
     only — the agent must NEVER touch the Render dashboard, and must note in
     the PR whether a dashboard-set variable would override this, per the
     AUTH-01 report).
  2. Cherry-pick `eba7129` ("Add gated QA access mode") from
     `codex/stability-health-pass` onto the task branch, resolving conflicts
     against current `main`. Do not re-implement it from scratch.
  3. Any repo-side wiring the AUTH-01 report identified as required.
  4. Label the PR `render-preview` so the owner gets a preview URL for
     phone QA. Include the AUTH-01 phone-QA script in the PR body.
- **Hard limits:** no Supabase Auth, schema, or RLS changes; no Render
  dashboard changes; no credential handling. The agent prepares; the owner
  QAs on the preview, then merges.
- **Expected files:** `render.yaml`, files brought in by `eba7129`,
  `LOOP_BACKLOG.md` (tick).
- **Task-scoped do-not-break:** full golden path on the preview (capture with
  photo → markup → Save + Next → Items list → reports), login/logout, the
  access-request screen, subcontractor mode, all six report types.
- **Risk:** HIGH — this changes who can reach production.
  **Phone QA:** YES, on the preview, before merge. **Owner gate:** explicit
  "Yes, proceed" required; preview shares production Supabase, so QA captures
  must use a sandbox project.

### - [ ] VERIFY-01 — Offline capture field test (agent writes script; owner runs it)

- **Plain English:** The app is supposed to keep working with no signal — you
  capture defects, and they upload automatically when you're back online.
  The code for this all exists, but nobody has ever proven it end-to-end on a
  real phone. This task writes the exact test for you to run; you run it on
  site or with airplane mode.
- **Agent deliverable (this is what ticks the box):**
  `docs/VERIFY-01-offline-field-test.md` — a step-by-step phone script:
  start online → enable airplane mode → capture an item **with photo** →
  reconnect → verify exactly **one** item on the server with its photo
  evidence attached (no duplicates, no lost photo). Must include: precise
  pass/fail criteria, what the sync pill should show at each step, what to
  screenshot, and how to report a failure.
- **Evidence the stack exists (verified 2026-07-16):** IndexedDB kv queue
  with localStorage fallback (`enhancements.js:36-50`), offline POST queueing
  + optimistic capture (`enhancements.js:1639`), reconnect flush
  (`enhancements.js:1645`), `service-worker.js`, offline/sync pill
  (`updateOfflinePill`). The end-to-end claim is unproven on a phone.
- **On failure:** the owner posts what happened (screenshots + which step).
  A NEW backlog task is added with that evidence before any fix is attempted.
  Never fix speculatively.
- **Expected files:** `docs/VERIFY-01-offline-field-test.md` (new),
  `LOOP_BACKLOG.md` (tick).
- **Risk:** none (docs only). **Phone QA:** the owner executing the script IS
  the QA. **Owner gate:** merge approval, then owner runs the test.

### - [ ] CLEANUP-BATCH-01 — Docs truth-up + legacy test retirement + serializer warning (DOC-01 + TEST-01 + HYGIENE-01)

One branch, one PR titled `CLEANUP-BATCH-01`. Combined because none of the
three changes production behaviour and they touch disjoint files; one review
instead of three.

- **DOC-01 — Documentation truth-up.**
  - In `CLAUDE.md` "Known follow-ups": REMOVE the expired-thumbnail-recovery
    bullet (shipped — re-sign endpoint at `app/main.py:755`), the Share
    Report file-size bullet (shipped — `SHARE_IMAGE_WIDTH = 1200` at
    `app/storage.py:49`), and the field-extraction substring bullet (shipped —
    alias matching in `app/parse_fields.py`, tested in
    `tests/test_parse_fields.py`). KEEP the dashboard "Issued" KPI bullet
    (accepted behaviour).
  - Reword the Render-instance bullet to: a one-time owner check of the
    instance type in the Render dashboard against `render.yaml` (paid Starter
    instances do not spin down; only Free does — no code work).
  - Add to the non-negotiable working rules: "Agents never receive or request
    owner credentials; QA accounts only."
  - In `CODE_HEALTH.md`: correct the `/api/plans` known-gap note — the Plans
    nav is intercepted with a "coming soon" toast
    (`CleanRun-IQ-Full-App-Render3/index.html:95`) and the feature is
    deliberately deferred; the backend routes are intentionally absent.
- **TEST-01 — Resolve GitHub issue #67 (legacy test suite).**
  - `CleanRun-IQ-Full-App-Render3/tests/test_full_app.py` targets an obsolete
    monolithic API: 7 of its 13 tests fail with
    `AttributeError: cleanrun_root_app has no attribute 'default_state'`,
    6 still pass (reproduced 2026-07-16). `AGENTS.md` already excludes legacy
    suites from the test run.
  - Do NOT reintroduce `default_state`. Audit all 13 tests: for each, either
    cite the covering test in `tests/` (file::test name) or migrate the
    still-relevant coverage into `tests/` following the existing patterns.
    Then delete the legacy file and close issue #67 with the mapping table.
- **HYGIENE-01 — Pydantic serializer warning.**
  - Reproduce: `.venv/bin/python -m pytest tests/test_auth_permissions.py -q`
    → `UserWarning: Expected 'enum' but got 'str' with value 'issued'`
    (from `test_register_and_exceptions_reports_filter_items`).
  - Fix at the model/typing level — somewhere a plain string reaches a field
    typed `ItemStatus` (`app/models.py`) without validation/coercion. NEVER
    fix by suppressing or filtering the warning.
- **Expected files:** `CLAUDE.md`, `CODE_HEALTH.md`,
  `CleanRun-IQ-Full-App-Render3/tests/test_full_app.py` (deleted), possibly
  new/updated tests in `tests/`, `app/models.py` or the module that assigns
  the raw string, `LOOP_BACKLOG.md` (tick).
- **Task-scoped do-not-break:** `python3 -m pytest tests/ -q` fully green;
  `/api/state` and report JSON output unchanged (the serializer fix must not
  alter any serialized value); no edits to Render3 UI files other than the
  legacy test deletion; no other legacy folders touched.
- **Risk:** low. **Phone QA:** no. **Owner gate:** merge approval.

---

## Blocked records

(Agents append `**Blocked:** <task ID> — <evidence>` entries here via their
own small PR when a task cannot proceed. None yet.)
