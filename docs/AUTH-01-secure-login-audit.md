# AUTH-01 — Secure-login readiness audit

**Status:** report only. Nothing in this document changes the app. Production
remains in open-access mode until AUTH-03 is approved and merged.

**Verified against:** `origin/main` after PR #72 (`599cbfe`), 16 Jul 2026.

---

## 1. What happens today, and how login turns on (the code path)

Today anyone who opens app.cleanruniq.com gets full admin access without
signing in. That is controlled by a single switch:

- `CLEANRUN_LOGIN_REQUIRED` — currently `"false"` (`render.yaml:34-35`).
- `login_required()` (`app/config.py:25-27`) reads that variable; default is
  `false` when unset.
- `_authenticate()` (`app/auth.py:285-302`): when login is NOT required, a
  visitor with no token gets `_open_access_user()` (`app/auth.py:101-111`) —
  `company_role="admin"`, `project_roles={"*": "project_manager"}`,
  `is_demo_admin=True`. A visitor with a *bad* token also silently falls back
  to open access (`app/auth.py:293-294`).
- When login IS required: no token → `401 Authentication required`
  (`app/auth.py:296-297`); a token is verified as a Supabase JWT via
  `_decode_supabase_jwt()` (`app/auth.py:217-244`) — first locally with
  `SUPABASE_JWT_SECRET` (HS256), and if that fails (e.g. rotated keys) it
  falls back to asking Supabase's Auth API directly
  (`_fetch_supabase_auth_user()`, `app/auth.py:247-276`). No service-role key
  is ever used.
- Who the user *is* comes from the token's `app_metadata.cleanrun` claims
  (`_user_from_claims()`, `app/auth.py:188-214`), per `SECURITY.md`.
  **Launch-admin shortcut:** any account whose email is listed in
  `CLEANRUN_LAUNCH_ADMIN_EMAILS` (default
  `info@cleanruniq.com,harrysfuel@outlook.com`, `app/auth.py:25` and
  `render.yaml:32-33`) is elevated to full admin automatically
  (`app/auth.py:195-203`) — those accounts work even with **no** cleanrun
  claims set.

On the phone side (Render3 UI):

- `boot()` (`index.html:178`) calls `/api/auth/config`
  (`app/main.py:456-464`), which reports `login_required` to the browser.
- With login on, any 401 clears the stored token and shows the sign-in
  screen (`api()` wrapper, `index.html:92`; reports path,
  `enhancements.js:541`).
- The sign-in screen (`renderLogin`, `index.html:88`) posts the password
  directly to Supabase (`loginWithPassword`, `index.html:91`), stores the
  access token in localStorage and a `cleanrun_access_token` cookie
  (`setAuthToken`, `index.html:80`), and reloads the workspace.
- A "Request access" screen exists (`renderAccessRequest`, `index.html:89` →
  `POST /api/access-requests`, `app/main.py:467`) — that endpoint stays
  reachable without a token, by design.
- Sign out appears in Settings only when login is on (`enhancements.js:1900`).

## 2. Exact activation steps — repo vs Render dashboard

**Which value wins:** if the Render service was created from the Blueprint,
`render.yaml` values are applied when the Blueprint syncs. If the service was
created manually (suspected — see CLAUDE.md follow-up about verifying the
instance type), **`render.yaml` is ignored and the dashboard is the only
truth**. Treat the dashboard as authoritative either way; the `render.yaml`
change is the versioned record.

Repo change (goes through the AUTH-03 PR):

1. `render.yaml:35`: `CLEANRUN_LOGIN_REQUIRED` → `"true"`.

Owner-only dashboard steps (agents must never do these):

2. Render Dashboard → `cleanrun-iq-python` → Environment: set
   `CLEANRUN_LOGIN_REQUIRED=true` (add it if absent). Saving env vars
   triggers a restart — this is the moment login actually turns on.
3. Confirm `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and
   `SUPABASE_JWT_SECRET` are set in the dashboard (they are `sync: false`
   in `render.yaml`, so they only exist there).
4. Optional cleanup, later: the `CLEANRUN_OPEN_ACCESS_EMAIL` /
   `CLEANRUN_OPEN_ACCESS_PASSWORD` vars are only used by open-access mode
   and become dormant. Leave them during the transition (they make rollback
   instant); remove them once login has been stable for a while.

## 3. Prerequisites — accounts and claims

Accounts live in Supabase Auth. Two kinds are needed before the flip:

| Account | How it gets access | What must exist |
|---|---|---|
| Owner/admin (`info@cleanruniq.com`, `harrysfuel@outlook.com`) | Launch-admin email list — auto-elevated to admin, no claims needed | Supabase Auth user with a password the owner holds |
| QA account (for agent/phone testing) | `app_metadata.cleanrun` claims | Supabase Auth user + claims set via `scripts/provision_launch_admins.sql` (still on the owner's machine — AUTH-02) |

Claim shape for non-launch-admin accounts (from `SECURITY.md` and
`_user_from_claims()`):

```json
{
  "app_metadata": {
    "cleanrun": {
      "company_id": "00000000-0000-0000-0000-000000000001",
      "company_role": "site_manager",
      "project_roles": { "Beach Parade": "site_manager" },
      "subcontractors": [],
      "demo_admin": false
    }
  }
}
```

Recommended QA account: non-admin, `site_manager` on the sandbox project
only. Agents never receive or request owner credentials.

## 4. What a signed-in user experiences when the token dies (iOS Safari)

This is the one real UX consequence of turning login on, so it is spelled
out honestly:

- **Sessions hard-expire.** `loginWithPassword` stores only the
  `access_token` and discards Supabase's `refresh_token`
  (`index.html:91`). Supabase access tokens expire after ~1 hour by
  default. There is no auto-renew: roughly an hour after signing in, the
  next API call gets a 401 and the user is bounced to the sign-in screen
  ("Sign in to continue.") mid-session.
- **Nothing is lost.** Unsent offline captures live in the IndexedDB queue
  (`enhancements.js:1639`), and `flushQueue()` stops (without dropping the
  queue) when a send fails (`enhancements.js:1657`). After re-login, the
  queue flushes and queued items sync.
- **An in-progress capture form** survives via the capture-draft
  persistence added in cards60 — but the save action itself will bounce to
  login first if the token has expired.
- Mitigation options (NOT in scope for AUTH-03; log as a follow-up if the
  hourly re-login annoys in practice): store and use the refresh token, or
  raise the JWT expiry in Supabase Auth settings (a Supabase dashboard
  change — owner approval required).

## 5. Rollback runbook (non-coder, ~2 minutes)

If anything goes wrong after activation:

1. Open the Render Dashboard → `cleanrun-iq-python` → **Environment**.
2. Change `CLEANRUN_LOGIN_REQUIRED` from `true` to `false`. Click Save.
3. Render restarts the service (watch the Events tab; usually 1–3 minutes).
4. Open app.cleanruniq.com in a private/incognito window — it should load
   straight to the dashboard with no sign-in screen. Done.

No code change, no revert, no data touched. The AUTH-03 PR can stay merged;
the env var alone decides the behaviour.

## 6. Phone-QA script for the AUTH-03 preview (before any merge)

Run on the `render-preview` URL on an iPhone (Safari). The preview shares
production Supabase — do test captures in the sandbox project only.

1. **Cold open** → the sign-in screen appears (no workspace data visible
   behind it).
2. **Wrong password** → clear error on the sign-in screen, still no data.
3. **Request access** → submit the form → confirmation message appears.
4. **Sign in with the QA account** → workspace loads; only the QA
   account's project(s) visible.
5. **Golden path:** capture with camera photo → markup arrow → save
   marked-up copy → Save + Next loops with walk counter → item on the
   Items list → visible in a report.
6. **Sign out** (Settings → Session) → returned to sign-in screen; reopening
   the app stays on sign-in (token really cleared).
7. **Expiry behaviour (spot-check):** sign in, leave the tab idle for over
   an hour, then tap anything → expect the "Sign in to continue." screen;
   sign back in → workspace returns, nothing lost.
8. **Report path while signed in:** generate a Defect Register → it opens
   (reports carry the token; `enhancements.js:531-541`).
9. Owner account signs in and sees all projects (launch-admin elevation).

Pass = all nine. Any failure: screenshot, stop, do not merge AUTH-03.
