# Weekly Internship Reports

**Project:** Housing Society Member & Vehicle Tracking System – AI-Based Vehicle Security and Society Management
**Internship period:** 13 July 2026 – 16 October 2026
**Weeks:** 14, Monday to Friday, beginning Monday 13 July 2026

## How to read this report

Statements fall into three kinds:

- **Verified** — supported by commits, test runs, or recorded terminal output
- **Reported** — the intern's own account, not independently evidenced
- **Provisional** — not yet confirmed, pending records

**The Git history is not the internship timeline.** The repository was created on 21 September 2026, during Week 11. Work from Weeks 1–10 left no commits because no project repository existed. Later commit dates record when code was committed, which is not always when it was written.

Work is assigned to the calendar week containing its verified date.

## Week index

| Week | Dates | Focus | Status |
|---|---|---|---|
| 1–10 | 13 Jul – 18 Sep | Learning and practice | Reported, allocation provisional |
| 11 | 21–25 Sep | Project build; Vehicle Management planned | Verified |
| 12 | 28 Sep – 2 Oct | Interface redesign | Verified |
| 13 | 5–9 Oct | ANPR experiments, REST API, audit trail | Verified |
| 14 | 12–16 Oct | Gate history column, reports, documentation | Verified |

---

## Weeks 1–10 (13 July – 18 September 2026)

**Status:** Reported by the intern. Weekly allocation **provisional**.

### Topics studied and practised

| Topic | Week(s) |
|---|---|
| HTML | To be confirmed |
| CSS | To be confirmed |
| Bootstrap | To be confirmed |
| JavaScript | To be confirmed |
| Git and GitHub | To be confirmed |
| SQL | To be confirmed |
| PostgreSQL | To be confirmed |
| Django | To be confirmed |

### Evidence

None in this repository. The repository was created on 21 September 2026, in Week 11. The learning phase therefore produced no commits.

### Pending verification

The original weekly plans for this period were not available when this report was prepared. The topics above are the intern's recollection; which topics fell in which weeks is unconfirmed. **No individual week in this range should be described as covering a specific topic until those records are found.**

---

## Week 11 — 21 to 25 September 2026

**Planned topic:** Vehicle Management
**Status:** Verified

### Plan

The weekly plan covered: the Vehicle model and its relationship to Resident; registration with number, type, model, colour and owner; validation and duplicate prevention; search and filtering; and testing.

### What the evidence shows

All planned items were completed. The repository was also created during this week, and several earlier modules were committed at the same time.

**21 September** — initial Django setup; PostgreSQL configured with secrets in `.env`; society app (Wing, Flat); residents app; vehicles app with plate normalization; admin for all three with tests; dashboard; resident and vehicle list, create and edit pages.

**22 September** — visitor management with lifecycle rules and pass codes; `expire_visitors` command; gate logs linked to visitors; accounts app with three role groups; `LoginRequiredMiddleware`; permission checks on every staff page; role-based navigation; friendly 403 page; resident portal.

**25 September** — `seed_demo_data` command; sidebar application shell; dashboard activity.

### Evidence

- 27 vehicle tests passing
- `normalize_plate()` in `vehicles/utils.py`; `is_valid_indian_plate()` for format checking
- Duplicate plates rejected even when typed with different spacing
- Plate search matches regardless of spacing or case

### Note on scope

The commits show that work corresponding to several planned weeks was completed during Week 11. The weekly numbering is left unchanged; this note records the discrepancy rather than adjusting the dates.

---

## Week 12 — 28 September to 2 October 2026

**Status:** Verified

### Work

Interface redesign across the application: a design token system (colour, typography, spacing); the sign-in page given a dedicated centred layout; the gate page rebuilt as an operational console; the resident portal redesigned as a personal account area; add and edit forms given consistent structure; the visitor pass styled as a pass rather than a plain card.

### Evidence

Commits `ac8ea77` (27 September), `253cfb3`, `4f4e9af`, `f04c4a5`, `1a4aec4`, `b53c5e0` (28 September). The full test suite passed after every stage, confirming no functional regression.

### Constraint observed

Roughly sixty existing tests asserted exact HTML strings. The redesign preserved every asserted substring, so no test was modified to accommodate a visual change.

---

## Week 13 — 5 to 9 October 2026

**Status:** Verified

### ANPR experiments (9 October)

These sessions were labelled "Week 12" and "Week 13 Day 1" at the time. The calendar dates place them in Week 13.

Work took place in a separate lab at `C:\Users\gauri\Projects\anpr-lab`, outside this repository and with its own Python 3.10 environment.

**Environment:** PyTorch 2.14.1+cpu, Ultralytics 8.4.174, OpenCV 5.0.0, EasyOCR 1.7.2, NumPy 2.2.6. All verified by import and version check.

**Synthetic plate test.** A 420×140 image was generated with the text `MH12KL4567`. EasyOCR read it as **`MH1ZKL4567`** with confidence **0.7616** — one character wrong on a perfectly clean, undistorted image.

**Format-aware corrector.** A utility was written that checks OCR output against known Indian registration formats and corrects characters that are the wrong type for their position. It corrected `Z` to `2` because position 3 must be a digit. 15 test cases passed, later extended to 20.

**Robustness experiment.** 10 image variants (blur, rotation, noise) × 5 preprocessing methods = 50 OCR runs.

| Measure | Result |
|---|---|
| Exact match from raw OCR | 22 of 50 |
| Correct after the corrector | 49 of 50 |
| No text detected | 0 |

### Findings

**Confidence is not a reliable indicator of correctness.** A wrong reading scored **0.917** — higher than several correct readings. A confidence threshold alone would not be a safe basis for accepting a plate.

**Blur improved accuracy on this image.** The sharpest version failed; heavy blur read correctly at 0.965. The likely explanation is that the rendered font draws `2` with angular strokes resembling `Z`, and blurring rounds them. **This is probably an artefact of the synthetic font and should not be assumed to hold for photographs.**

**One unrecoverable failure.** `MHL2KL4567` — an `L` where a digit belongs. The corrector returned `invalid_format` rather than guessing, because `L` is not in its confusion table. A later investigation confirmed this was correct behaviour, not a defect, and no change was made.

**No preprocessing method outperformed doing nothing.** Otsu thresholding performed worst.

### REST API (10 October)

Five endpoints under `/api/v1/`, built in four verified checkpoints.

| Endpoint | Method | Permission |
|---|---|---|
| `ping/` | GET | authenticated |
| `vehicles/` | GET | `vehicles.view_vehicle` |
| `vehicles/lookup/?plate=` | GET | `vehicles.view_vehicle` |
| `gate/logs/` | GET | `tracking.view_vehiclelog` |
| `gate/anpr-log/` | POST | `tracking.add_vehiclelog` |

The API reuses the existing `normalize_plate()` and `VehicleLog._apply_rules()` rather than reimplementing them. Resident contact details are never serialized. Commit `60e6efd`.

**The POST endpoint rejects `source="anpr"` with HTTP 422.** The gate log has no field distinguishing an unverified camera reading from a movement a person confirmed, so storing one would present a guess as a fact. This was a deliberate design decision, documented rather than worked around.

### Audit trail (10 October)

`VehicleLog.recorded_by`, a nullable foreign key to User with `on_delete=PROTECT`. Migration `tracking/0003`. The user is assigned server-side in the gate form, the API and Django Admin; a client-supplied value is ignored. The 14 pre-existing gate logs remain `NULL` — no attribution was invented. Commit `9d5c24f`, 18 tests.

### Token authentication (10 October)

`rest_framework.authtoken` enabled alongside session authentication. An `api_token` management command issues, shows, rotates and revokes tokens, and refuses inactive accounts and Residents. Commit `256acf2`, 26 tests.

**A token authenticates; it does not authorize.** A Resident's valid token still receives 403 on every restricted endpoint, which is explicitly tested.

---

## Week 14 — 12 to 16 October 2026

**Status:** Verified

### Gate History attribution column (12 October)

The `recorded_by` value surfaced in the Gate History table. Records predating the audit field show "Not recorded" rather than a fabricated user. `select_related` was extended so the page issues six queries regardless of row count. Commit `594abb0`, 11 tests.

### Reports module (15 October)

A new `reports` app with no models and no migration, aggregating existing `VehicleLog` and `Visitor` data.

**Gate statistics:** entries, exits, and Registered / Visitor / Unknown classification for a date range, with a daily breakdown.

**Visitor statistics:** registered visits distinguished from actual arrivals. A booked visit that was cancelled or expired is counted as registered but not as an arrival, because counting rows alone would overstate how many people visited.

**Filters:** start and end dates defaulting to the last 30 days, validated on the server. Restricted to Society Admin; Guards and Residents receive 403.

Charts are CSS bars with inline percentage widths — no charting library was added. Commit `67c6e10`, 23 tests.

**Verification:** the page reported 9 entries and 5 exits for 13 September to 12 October, totalling 14, which matched Gate History exactly.

### Documentation (15–16 October)

`README.md`, `docs/weekly-reports.md` and `docs/project-status.md` prepared. `docs/api-tokens.md` was written in Week 13.

---

## Project status at Week 14

### Verified working

| Module | Tests |
|---|---|
| society | 6 |
| residents | 50 |
| vehicles | 27 |
| tracking | 93 |
| visitors | 64 |
| accounts | 88 |
| dashboard | 4 |
| api | 73 |
| reports | 23 |
| **Total** | **428** |

All 428 pass. Django system checks report no issues. No migrations are pending.

### Not complete

**ANPR is not integrated.** No vehicle detection, no plate detection, no camera input. OCR has been tested on synthetic images only.

### Blockers, with reasons

1. **No real vehicle photograph.** The intern does not have access to a vehicle to photograph. Nothing in the detection pipeline can be tested without one.
2. **No verified plate-detection model.** Two candidates were identified on Roboflow but neither has been checked for downloadable weights or licence terms.
3. **No public test images selected.** An alternative to photography, but a source with clear licensing has not yet been chosen.

### Honest statement of limitations

- The standard YOLO model cannot detect number plates. It is trained on 80 everyday categories; "number plate" is not among them. A plate-specific model is required.
- OCR accuracy on synthetic images says nothing reliable about accuracy on photographs.
- A valid plate format does not prove a vehicle's identity.
- An unrecognised plate is not an unauthorised vehicle.