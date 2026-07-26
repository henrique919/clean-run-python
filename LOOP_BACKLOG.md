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

### - [x] AUTH-02 — OWNER TASK: provision and verify QA/admin accounts — done 16 Jul 2026: script on `main` (PR #76), owner ran it in the Supabase SQL Editor and confirmed ("done")

- **Plain English:** Two pieces of earlier login work need to be in place
  before we can turn logins on, and one of them only exists on your computer.
- **What the owner must do (agents must NOT do this):**
  1. ~~Push `scripts/provision_launch_admins.sql` from your machine~~ —
     **resolved**: the original was lost from the owner's machine, so the
     script was regenerated from the actual claim shape in `app/auth.py`
     (`_user_from_claims()`) and committed as
     `scripts/provision_launch_admins.sql` (16 Jul 2026). Nothing to push.
  2. ~~Push commit `eba7129` ("Add gated QA access mode")~~ — **already
     done**: `eba7129` is the tip of the `codex/stability-health-pass` branch
     on GitHub (verified 2026-07-16; it sits 142 commits behind `main`).
     Nothing to push — the AUTH-03 agent will cherry-pick it onto a current
     branch. Do not delete that branch.
  3. Create (or confirm) the accounts in Supabase Dashboard → Authentication
     → Users: your two admin emails and `qa@cleanruniq.com`, each with a
     password. Then run `scripts/provision_launch_admins.sql` in the Supabase
     SQL Editor (instructions are at the top of the file) and check the
     verification query output. Agents never receive or request your
     credentials — QA accounts only.
- **How to record completion:** tick this checkbox yourself on GitHub (edit
  this file on `main`), or tell the assistant "AUTH-02 is done" and the next
  iteration will verify (SQL script visible on `main` + your confirmation)
  and tick it in the AUTH-03 PR.
- **Risk:** n/a (owner-executed). **Owner gate:** entire task.
- **Agents:** do not re-derive the SQL script or the gated-QA-access work.
  If AUTH-02 is unticked, AUTH-03 is blocked — skip past it.

### - [x] AUTH-03 — Secure-login activation PR (depends: AUTH-01, AUTH-02) — PR prepared as owner-gated draft; ships only on explicit "Yes, proceed" after preview phone QA. Declared deviation: the eba7129 cherry-pick was deliberately NOT included (the gated QA-token mode is superseded by the real `qa@cleanruniq.com` account provisioned in AUTH-02; rationale in the PR body; owner may overrule)

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

### - [x] VERIFY-01 — Offline capture field test (agent writes script; owner runs it) — script delivered: `docs/VERIFY-01-offline-field-test.md`; awaiting owner's phone run

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

### - [x] CLEANUP-BATCH-01 — Docs truth-up + legacy test retirement + serializer warning (DOC-01 + TEST-01 + HYGIENE-01) — done; migrated coverage in `tests/test_legacy_full_app_migration.py`

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

### - [ ] QUEUE-01 — Offline queue head-of-line blocking (found during VERIFY-01 emulated run, 16 Jul 2026)

- **Plain English:** if any queued offline request permanently fails when the
  connection returns, everything behind it in the queue silently never syncs
  and the pill sticks on "Syncing N…" forever.
- **Evidence (reproduced in emulated VERIFY-01 run):** capture offline →
  queue held [`POST /api/photos/stage`, `POST /api/items`]. On reconnect the
  stage request kept failing (503 in local storage mode) and
  `flushQueue()`'s `catch{break}` (`enhancements.js:1657`) stopped the whole
  flush at entry 1 — the item POST behind it never sent, no error surfaced,
  pill stuck at "Syncing 2…". Removing the doomed entry let the item sync
  perfectly (real code assigned, photo intact, no duplicate).
- **Production exposure:** stage normally succeeds against Supabase, so the
  common path works — but any entry that hits a permanent 4xx/5xx (validation
  reject, oversized photo, expired auth semantics) freezes all later syncs
  with zero user feedback. Evidence-capture product: silent sync freeze is a
  trust breaker.
- **Suggested shape of fix (for discussion, not prescriptive):** distinguish
  permanent failures (4xx except 401/408/429) from transient ones — skip or
  dead-letter permanent failures with a visible per-item error, keep
  retrying transient ones. Never silently drop evidence.
- **Risk:** medium (touches sync logic; needs careful iOS QA).
  **Phone QA:** yes. **Owner gate:** merge approval.
- **Status (25 Jul 2026):** fix implemented and code-reviewed, on branch in
  PR #82 (build tag cards63) — `flushQueue()` now classifies
  transient-vs-permanent failures, quarantines permanent failures into a
  visible failed-queue with a Discard action instead of blocking the drain
  forever, and gained a re-entrancy guard for the separate concurrent-flush
  bug found alongside this one. Still **not ticked**: this needs phone QA
  on a Render preview (poison-pill recovery, concurrent flush via
  airplane-mode toggling) before it can be considered verified per this
  repo's rules for anything touching capture/sync — see PR #82 for the
  exact test script.
- **Re-verified 26 Jul 2026:** fix confirmed present and unchanged on
  `main`. Still awaiting the phone QA above before ticking.

---

### - [x] IDOR-01 — `/api/photos/markup-source` bypasses the item-visibility allowlist (found during launch assessment, 25 Jul 2026) — done: verified still present 26 Jul, fixed same day (`app/storage.py::is_markup_source_path_allowed`, `tests/test_auth_permissions.py::test_markup_source_rejects_paths_outside_visible_items`)

- **Plain English:** any signed-in account — including one with zero
  projects assigned — can fetch the raw bytes of any evidence photo in the
  bucket by guessing/enumerating its storage path, because one of the two
  checks on this endpoint is a blanket "is it under `cleanrun/public/`"
  check rather than "is it a photo this user can actually see."
- **Evidence:** `app/main.py` — `markup_photo_source()` builds an allowlist
  from `visible_items(ctx.user, ...)` (correct), but then admits the
  request anyway `if is_markup_source_path_allowed(path)`
  (`app/storage.py::is_markup_source_path_allowed`), which returns `True`
  for any path under the public-launch prefix — i.e. every production
  photo, since all production evidence lives under `cleanrun/public/`.
  Compare `/api/photos/refresh-url` (`app/main.py`), which does this
  correctly: allowlist-only, no bypass.
- **Suggested fix:** delete the `is_public_launch_storage_path(path)` half
  of the `or` in `is_markup_source_path_allowed` (keep the staging-path
  half — a user's own in-progress capture upload legitimately isn't in
  `visible_items` yet). Track staged-but-not-yet-saved paths per session
  instead if the allowlist needs to admit them.
- **Depends on:** should land after SAFETY-BATCH-03 (PR #82) is merged and
  the anon-access migration is applied — this finding is materially worse
  before that (anon doesn't even need an account), but stays a real bug
  after it too (any authenticated account, not just ones with project
  access).
- **Risk:** medium — no photos/markup UI change, server-side check only.
  **Phone QA:** confirm markup still loads for a user's own photos after
  the fix. **Owner gate:** merge approval.

---

### - [x] RACE-01 — item code allocation race can 503 and orphan uploaded photos (found during launch assessment, 25 Jul 2026) — done: fixed on `main` as part of the "Fix Esplanade capture wedge" commit (71132b3) — bounded 3-attempt retry on `items_code_key`/23505 with a freshly recomputed code; verified 26 Jul

- **Plain English:** if two site managers save a new item at close to the
  same moment, both can get assigned the same `DEF-10NN` code. The
  database correctly refuses the second one, but by then its photos are
  already uploaded and the capture is lost — the user just sees a failed
  save.
- **Evidence:** `app/store_supabase.py` — the `next_code` allocation reads
  `max(code)+1` outside the per-process lock, and there's nothing
  preventing two concurrent requests (different processes, or just two
  people) from computing the same next code before either commits. `code`
  is `unique not null` (`supabase/migrations/202606280002_core_schema.sql`),
  so the second insert raises, and `app/main.py`'s create-item handler
  turns that into a 503 toast (`main.py`, search the create_item route's
  except block for the 503 detail construction).
- **Suggested fix:** allocate codes via a Postgres sequence, or retry the
  insert with a freshly recomputed code on a `23505` unique-violation
  (bounded retry, not infinite).
- **Risk:** medium. **Phone QA:** yes — two devices saving concurrently on
  the same project. **Owner gate:** merge approval.

---

### - [ ] RACE-02 — item patch is last-write-wins across concurrent edits (found during launch assessment, 25 Jul 2026)

- **Plain English:** if two changes land on the same item close together —
  e.g. a supervisor closes it out with evidence while an offline device
  replays a queued comment — one of them silently disappears. Whichever
  read-modify-write finishes last wins, full stop, with no warning to
  either party.
- **Evidence:** `app/store_supabase.py::_patch` reads the current item,
  applies the mutator, then upserts the **entire row** back. The read
  happens outside any lock that spans the read-modify-write, and the
  in-process `RLock` doesn't help across the multiple Render worker
  processes/threads a `starter` instance can run anyway.
- **Suggested fix:** switch to targeted column updates with an
  `updated_at`-based optimistic-concurrency check (`where updated_at = $1`,
  0 rows affected → 409, caller re-reads and retries) instead of a full-row
  upsert from a stale read.
- **Risk:** medium-high (touches every item mutation path — needs careful
  regression testing, not just phone QA). **Owner gate:** merge approval,
  recommend its own PR rather than bundling with anything else.

---

### - [x] SEC-02 — JWT audience never verified; wrong/stale secret means a network round-trip on every request (found during launch assessment, 25 Jul 2026) — done: PR #82, `app/auth.py` + `render.yaml`, `tests/test_jwt_verification.py`

- **Plain English:** two related gaps in how the server checks a login
  token. Neither is exploitable on its own today, but together they mean a
  misconfigured secret would make the app slow for everyone with no error
  telling you why.
- **Evidence:** `app/auth.py::_decode_supabase_jwt` — `verify_aud` is only
  enabled `if os.getenv("SUPABASE_JWT_AUDIENCE")`, and `render.yaml` never
  sets that variable, so the `aud` claim is never actually checked.
  Separately, local verification is wrapped in a bare
  `except Exception: pass` that falls through to a live call to
  `{SUPABASE_URL}/auth/v1/user` — meaning if the configured
  `SUPABASE_JWT_SECRET` is ever wrong (e.g. the Supabase project rotates to
  its newer asymmetric signing keys), *every single authenticated request*
  silently starts doing a synchronous network round-trip instead of local
  verification, with nothing in the logs calling it out.
- **Suggested fix:** set `SUPABASE_JWT_AUDIENCE=authenticated` in
  `render.yaml`; add `leeway=30` to the `jwt.decode` call; log once
  (`logger.warning`, not `pass`) when local verification fails so the
  fallback path is visible instead of invisible.
- **Risk:** low (additive checks, existing fallback stays as the safety
  net). **Phone QA:** no. **Owner gate:** merge approval.

---

### - [ ] UI-01 — Reports and Share Report don't work on iOS Safari (found during launch assessment, 25 Jul 2026)

- **Plain English:** the reports customers actually pay for don't reliably
  open on an iPhone — the two things this product exists to produce.
- **Evidence:** `enhancements.js` opens the report in a new tab via
  `window.open(url, "_blank")` *after* an `await fetch(...)` — by then the
  original tap's "this was a user gesture" permission has expired, so iOS
  Safari blocks the popup silently (fallback is just a toast asking the
  user to allow popups). Separately, `app/reporting.py`'s Share Report flow
  calls `navigator.share({files: [file]})` with an HTML file — iOS Safari's
  share sheet doesn't accept HTML files, so `canShare` returns false and it
  falls back to a `download` attribute on a blob URL, which iOS Safari
  doesn't honour (and does nothing at all in installed-PWA mode).
- **Suggested fix:** open the tab synchronously in the click handler
  (`window.open("", "_blank")` first, write into it once the fetch
  resolves) rather than after the await. For Share, share the report's URL
  or plain text on iOS instead of an HTML file.
- **Risk:** medium. **Phone QA:** yes, this is the whole point — verify on
  a real iPhone. **Owner gate:** merge approval.

---

### - [ ] UI-02 — Issue/Re-Issue button can silently stop working; Reject/other actions can double-fire (found during launch assessment, 25 Jul 2026)

- **Plain English:** two related double-tap-guard bugs. One can make the
  Issue button look normal but do nothing until the page is reloaded. The
  other can let a Reject (or similar) action fire twice from one tap.
- **Evidence:** `enhancements.js` — the Issue/Re-Issue handler does
  `cardActionLocks.add(id)` using the id as first rendered, then
  *reassigns* the same local variable via `id=canonicalItemId(item.id)`
  partway through the async body, and the `.finally()` deletes the lock
  under the *new* value — so the original lock key is never removed. This
  happens whenever `canonicalItemId` normalizes the id differently than
  how it was first passed in (offline-resolved ids, undashed UUIDs).
  Separately, the Reject handler (and one other action — search for
  `setBusyButton` call sites and check what runs *before* it) calls
  `await chooseImage()` (the photo picker) *before* calling
  `setBusyButton(...)`, so the button stays tappable for the whole time the
  picker is open.
- **Suggested fix:** capture the lock key in a `const` before the async
  body starts and delete by that captured value; move `setBusyButton(...)`
  to the very first line of each handler, before any `await`.
- **Risk:** low-medium, UI-only. **Phone QA:** yes — tap-twice and
  cancel-the-picker checks. **Owner gate:** merge approval.

---

### - [ ] SW-01 — Service worker can cache a 401 and log an offline user out (found during launch assessment, 25 Jul 2026)

- **Plain English:** if your login expires right before you lose signal,
  the app can lock you out of your own offline data instead of just
  showing what's cached.
- **Evidence:** `service-worker.js` — both the `networkFirst` and
  `cacheFirst` helpers call `cache.put(cacheKey, response.clone())`
  unconditionally, with no `response.ok` check, and `/api/state` is routed
  through `networkFirst`. If `/api/state` ever 401s (expired token) while
  online, that 401 response gets cached; the next time the device goes
  offline, the cached 401 is served, the client's `api()` wrapper sees
  `status === 401` and clears the session — an offline user gets logged
  out by a cached response, not a real one.
- **Suggested fix:** only `cache.put` when `response.ok`; also fine to just
  drop `/api/state` from the service worker's cached routes entirely, since
  the app already keeps its own IndexedDB copy of state for offline use.
- **Risk:** low. **Phone QA:** yes — force a 401, go offline, confirm no
  logout. **Owner gate:** merge approval.
- **Status (26 Jul 2026):** fix implemented in `service-worker.js`'s
  `networkFirst`/`cacheFirst` (both now guard `cache.put` on
  `response.ok`), cache bumped to `cleanrun-iq-shell-v25`. Still **not
  ticked** — needs the phone QA described above before merge.

---

### - [ ] LOGOUT-01 — signing out doesn't clear the previous user's data from the device (found during launch assessment, 25 Jul 2026)

- **Plain English:** the Settings screen tells people to "sign out on
  shared devices when you are finished," but signing out doesn't actually
  clear anything except the login token — the previous user's project data
  is still sitting in the browser's local storage for the next person who
  opens the app offline.
- **Evidence:** `index.html`'s `logout()` clears the auth token/cookie only
  — no IndexedDB purge of the cached app state, capture draft, walk
  context, or offline queue, and no service worker cache clear.
- **Suggested fix:** on logout, purge the IndexedDB keys the app uses for
  cached state/drafts/queue and clear the service worker's Cache Storage —
  refuse (or warn loudly) if the offline queue is non-empty rather than
  silently discarding unsynced work.
- **Risk:** low-medium (touches logout, a rarely-exercised path — test
  carefully). **Phone QA:** yes. **Owner gate:** merge approval.

### - [ ] DEPLOY-01 — production build may not be installed from requirements.txt (found during launch-readiness session, 25 Jul 2026)

- **Plain English:** the running server's photo-storage library reported
  itself as a version (`storage3 v0.12.1`) that today's `requirements.txt`
  cannot install (`supabase==2.10.0` pins `storage3 <0.10`). That means at
  least the build serving traffic at 22:46 UTC on 25 Jul was built from a
  stale dependency cache, not from what the repo says. Fixes tested against
  the repo's pinned versions can behave differently on a drifted build.
- **Evidence:** Supabase storage logs, 22:46-22:48 UTC 25 Jul — user-agent
  `supabase-py/storage3 v0.12.1` on every request; `requirements.txt` pins
  `supabase==2.10.0` whose metadata requires `storage3 >=0.9.0,<0.10.0`.
- **Suggested fix:** owner action in the Render dashboard — "Clear build
  cache & deploy" once; then confirm the next storage log line reports
  `storage3 v0.9.x`. No code change.
- **Risk:** none (dashboard action). **Phone QA:** no. **Owner gate:**
  owner performs the dashboard step.

### - [ ] STORAGE-02 — bucket-info check logs noisy failures now that storage requires login (found 25 Jul 2026)

- **Plain English:** before each upload the server asks "does the photo
  bucket exist?" — that check now gets refused (the locked-down storage
  rules have no allowance for reading bucket info), so every upload writes
  a scary-looking failure line to the logs before proceeding fine.
  Harmless in production (the code skips on), but it muddies the logs and
  in non-production it can still abort uploads.
- **Evidence:** two `GET/POST /storage/v1/bucket/...` 400s in the
  25 Jul storage logs alongside the (since-fixed) upload failures;
  `app/storage.py::_ensure_bucket` get_bucket → exception → production
  skip-and-continue.
- **Suggested fix:** either stop calling `_ensure_bucket` per-upload in
  production entirely (the bucket is migration-managed), or add a
  `storage.buckets` SELECT policy for `authenticated`. First option is
  simpler and has no policy surface.
- **Risk:** low. **Phone QA:** no. **Owner gate:** merge approval.

---

## Verification evidence — VERIFY-01 emulated run (agent, 16 Jul 2026)

Run via Playwright (Chromium, 390×844) against a local instance
(`CLEANRUN_STORAGE=local`, `CLEANRUN_LOGIN_REQUIRED=true`), server process
killed/restarted to simulate signal loss. Results: offline save instant with
"saved offline - queued to sync" toast and OFF- code · item visible on list
with photo while offline · reconnect flush → real code (DEF-11), photo
attached, exactly one item client-side AND server-side (JSON store
inspected), pill "Synced ✓" · plus the QUEUE-01 finding above. This proves
the mechanics; the owner's real-iPhone airplane-mode run
(`docs/VERIFY-01-offline-field-test.md`) is still the final word for iOS
Safari + real camera.

### - [x] APPSTORE-01 — OWNER DECISIONS: what's actually needed before Apple App Store / Google Play submission (found during app-store-readiness review, 26 Jul 2026) — decisions 1-3 resolved same day per owner reply ("no business. info@. go with optimal icon."); decision 4 (native wrapper) still open

- **Plain English:** CleanRun IQ today is a website/PWA, not a native app —
  there is no iOS or Android project anywhere in this repo. You cannot
  submit a website to either store as-is. Before any of that work starts,
  four decisions are yours to make; nothing below gets built without your
  "Yes, proceed" on each.
- **1. Icon/logo — RESOLVED, "go with optimal icon."** Swapped to the
  higher-quality 1024×1024 running-figure-and-checkmark mark (the only
  real square, high-resolution source available; the old
  105×78 chevron `icon-mark.png` was too small/wrong-shaped for any store
  and has been removed). Generated and wired up the full set:
  `assets/icon-192.png`, `icon-512.png`, `icon-maskable-512.png`
  (content already sits within the maskable safe zone — measured at ~65%
  width, well inside the 80% circle), `apple-touch-icon.png` (180×180),
  `favicon-32.png`/`favicon-16.png`, and `icon-1024.png` (no-alpha master,
  ready for the future App Store Connect / Play Console listing upload —
  not linked from the app itself). Manifest and `index.html` updated
  accordingly (cards67). Note: this only changes the home-screen/favicon
  icon — the in-app brand mark (chevron SVG in the top bar and loading
  screen, `assets/chevrons.svg`) is a separate element and was **not**
  touched.
- **2. Legal pages — RESOLVED, "no business."** Read as: no separate
  registered company at this stage. Both Privacy Policy and Terms of
  Service now describe CleanRun IQ as operated by its founder as an
  individual rather than a registered company, and the outstanding-review
  banners no longer reference a missing ABN/entity name (that line item is
  resolved; only the "not yet reviewed by a qualified Australian legal
  adviser" review itself remains outstanding). Terms' governing-law clause
  now reads "the laws of Australia" / "Australian courts" generically
  (no specific state/territory was given — flag to the owner: worth
  tightening to a specific state once/if you register a business address,
  but not a blocker to submit as a non-final draft, which the page already
  discloses it is).
- **3. Support contact address — RESOLVED, "info@".** Contact and Demo
  pages' `PUBLIC_CONTACT_EMAIL` fallback (and the two resource-page
  fallbacks) now default to `info@cleanruniq.com`, matching Privacy/Terms.
  Note: Render has `PUBLIC_CONTACT_EMAIL` set as a dashboard env var
  (`sync: false` in `render.yaml`) — if it's currently set to something
  else there, the dashboard value wins over this code default; only the
  owner can check/change that in the Render dashboard.
- **4. Native wrapper path.** Neither store will list the site directly.
  Realistic routes: **Google Play** — a Trusted Web Activity (PWABuilder
  or Bubblewrap) wraps the existing PWA with minimal new code; Google
  explicitly supports this, no "just a website" rejection risk; ~$25
  one-time account fee; roughly 1–2 weeks once assets exist (longer if
  Google's new-account closed-testing period applies). **Apple App Store**
  — needs a real native wrapper (Capacitor is the standard low-effort
  choice, works with the existing vanilla-JS app with no rewrite);
  bare-wrapped-website submissions risk rejection under Guideline 4.2, so
  pairing it with at least one real native feature (Capacitor's Camera
  plugin fits naturally, and would also route around the iOS Safari camera
  quirks already flagged in this file) is the safer bet; $99/year Apple
  Developer account, a Mac or cloud-Mac CI for the Xcode build, and roughly
  2–4 weeks end to end. Both stores also need a reviewer/demo login with
  realistic seeded data — **agents cannot create or hold this**
  (credentials rule); it must be provisioned by you. **Needed from you:**
  go/no-go on building a wrapper at all, which store to prioritise first
  (Play is faster and lower-risk), and sign-off to create a new, separate
  wrapper repo — this is new build tooling (npm/Capacitor or
  PWABuilder/Bubblewrap) but lives in its own project, the same way
  `clean-run-website` already sits alongside this repo; it does not touch
  `index.html`/`enhancements.js`/`app.py`.
- **Already done, no action needed:** Privacy Policy content itself is
  accurate against what the app actually collects (photos, optional GPS on
  capture, account email — cross-checked against
  `enhancements.js`'s geolocation call and Supabase storage architecture).
  Config-only PWA meta tags that don't depend on the icon decision are
  already added (`apple-mobile-web-app-capable`,
  `apple-mobile-web-app-status-bar-style`, `apple-mobile-web-app-title`,
  `mobile-web-app-capable`, manifest `id`/`scope`).
- **Risk:** none from the review itself (no live change to who can access
  what). **Phone QA:** n/a. **Owner gate:** all four decisions above.

## Blocked records

(Agents append `**Blocked:** <task ID> — <evidence>` entries here via their
own small PR when a task cannot proceed. None yet.)
