# VERIFY-01 — Offline capture field test (owner runs this on an iPhone)

**Purpose:** the app claims it keeps working with no signal — you capture
defects offline and they upload automatically when the connection returns.
All the code for this exists (offline queue, optimistic save, reconnect
flush, sync pill), but it has **never been proven end-to-end on a real
phone**. This script is that proof. Until it passes, do not market offline
capture.

**Time needed:** about 5 minutes. **Where:** anywhere — kitchen is fine,
airplane mode simulates the basement.

**Use the sandbox project** (e.g. Beach Parade) — the test creates one real
item.

---

## Before you start

- iPhone, Safari, app.cleanruniq.com open and loaded **while online**.
  (The offline cache is filled on load — `enhancements.js:1635` — so the app
  must load once online first.)
- Note the current item count in your sandbox project.
- You should see the sync pill (bottom of screen) showing **"Synced ✓"**.

## The test — follow in order, tick as you go

| # | Step | What you should see (pass) |
|---|------|-----------------------------|
| 1 | With the app open, turn on **Airplane Mode** (Control Centre). Wi-Fi off too. | Within a few seconds the pill turns red-ish: **"Offline · 0 queued"** |
| 2 | Go to Capture. Take a photo **with the camera**, fill the required fields, tap **Save + Next**. | Save succeeds instantly (no spinner hang). Toast says **"saved offline - queued to sync"**. Pill: **"Offline · 1 queued"** |
| 3 | Open the Items list. | The new item is there with a temporary code starting **OFF-** and its photo visible |
| 4 | Tap the pill. | A sheet opens listing the queued item ("Queued") |
| 5 | (Optional but good) Kill Safari completely (swipe away), reopen the app **still in airplane mode**. | App loads from cache; the queued item still shows; pill still says **"Offline · 1 queued"** — nothing lost by closing the app |
| 6 | Turn Airplane Mode **off**. Wait up to ~30 seconds, or tap the pill. | Pill goes **"Syncing 1…"** then **"Synced ✓"**, with a toast **"1 item synced"** |
| 7 | Pull up the Items list. | The item now has a **real code** (e.g. BP-DEF-10xx, not OFF-) and its photo loads. Total item count went up by exactly **one** |
| 8 | Open the item detail. | Photo present, audit trail shows it was created (with the offline note), fields are what you entered |
| 9 | On a desktop/second device (or after a full refresh), check the same project. | The same single item exists on the server — **exactly one**, no duplicate, photo attached |

## Pass / fail

- **PASS = all nine rows.** The offline claim is verified; tick this box in
  `LOOP_BACKLOG.md` and offline capture can be talked about with a straight
  face.
- **FAIL = any row wrong.** Most likely failure points, so you can describe
  what you saw precisely:
  - Step 2: save blocks or errors instead of queueing → the offline detection
    didn't classify the failure as offline.
  - Step 6: pill stuck on "Offline" or "Syncing" after reconnect → the flush
    didn't fire or the send failed silently.
  - Step 7: item stuck with OFF- code, photo missing, or **two** copies of
    the item → the merge/de-duplication on sync failed. Two copies is the
    worst outcome — say so explicitly if you see it.

## If it fails — how to report

Do not let anyone "quick fix" it. Post, in one message:

1. Which step number failed and what the pill said at that moment.
2. Screenshots: the pill, the Items list, and the item detail (if it made
   it that far).
3. Whether the photo survived.
4. iPhone model + iOS version.

A new backlog task will be created from that evidence before any fix is
attempted (per the loop protocol: never fix speculatively).

## Afterwards

Delete the test item from the sandbox project, or leave it — your call.
