# CleanRun IQ conversion audit

Canonical source reviewed: top-level `expo/` app declared by `rork.json`.

## Screen coverage

| Rork / Expo screen | HTML implementation |
|---|---|
| Home tab | Project selector, sync state, Capture CTA, four statistics, attention/inspection banners, prioritised item cards |
| Items tab | Active/all-project scope, text search, type filters, workflow filters, exact status matching |
| Capture tab | Photo-first evidence, required-photo rules, Voice-to-Note parsing, task/location/assignment fields, walk capture, Save and Issue Now |
| Plans tab | Project plans, image upload, normalised pins, item linking, status colours, removal |
| More tab | Reporting, Subcontractor Mode, Project Setup, Settings & Admin |
| Item detail | Summary, edit, original evidence, issue history, rectification, inspection, closeout, comments, audit trail and status actions |
| Reports | Six report types, active-project filtering, evidence counts, printable handover output |
| Subcontractor Mode | Subcontractor selection, assigned open items, rejection feedback, evidence upload, ready-for-review transition |
| Project Setup | Active project, buildings, levels, units/areas and rooms/locations editors |
| Settings | Company/preparer, projects, subcontractors and canonical demo reset |
| Report preview | Printable HTML with summary statistics and item/evidence details |
| Not found / native intent | Replaced by HTTP 404 JSON and the single-page router fallback |

## Domain and state coverage

- All item types, statuses, priority values, evidence records, comments, issue events, inspection events, audit events, voice notes, settings, project configs, subcontractor profiles, plans and pins are represented.
- All AppStore transitions are implemented: create, edit, issue/reissue, in-progress, ready, inspect, reject, close/complete, reopen, rectification evidence and comment.
- AsyncStorage is translated to atomic local JSON persistence.
- Native image capture/library selection is translated to browser file/camera inputs and data URLs.
- Native PDF sharing is translated to a standards-compliant printable report page.
- The original deterministic offline voice parser is translated to Python, including item type, location, trade, subcontractor, urgency and due-date inference.

## Canonical demo fixtures

- 14 items: `DEF-001`–`DEF-009`, `INC-001`–`INC-003`, `CLD-001`–`CLD-002`.
- Projects: Jura Noosa and Meta Street, with their original buildings, levels, units and rooms.
- Ten original subcontractors and trade mappings.
- Block A Level 3 plan with three original linked pins.

## Platform substitutions

- Expo Router navigation → browser SPA navigation.
- React Native modals → accessible HTML modal surfaces.
- NetInfo/local-first UI → localhost server health plus atomic local persistence.
- Expo ImagePicker/audio/haptics → browser file/camera, Web Speech API, and normal interaction feedback.
