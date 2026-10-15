# Project Status

**Last updated:** 16 October 2026
**Latest commit:** `67c6e10`

A plain account of what works, what is unverified, and what is not built. Written so a reviewer does not have to discover the gaps themselves.

## Summary

The Django application is complete and tested: nine modules, 428 automated tests, role-based security, a REST API, an audit trail, and reports.

**The AI component named in the project title is not built.** Automatic Number Plate Recognition is not integrated. The gate accepts a vehicle number typed by a guard.

## Verified working

Confirmed by test runs and, where noted, by use in a browser.

| Area | Evidence |
|---|---|
| Society: wings and flats | 6 tests |
| Residents: CRUD, search, login link | 50 tests; browser-verified |
| Vehicles: normalization, duplicates, search | 27 tests; browser-verified |
| Gate tracking: entry/exit, classification, history | 93 tests; browser-verified |
| Visitors: lifecycle, pass codes, expiry | 64 tests; browser-verified |
| Roles and permissions | 88 tests; 30 role × page combinations checked |
| Dashboard | 4 tests; browser-verified |
| REST API: 5 endpoints | 73 tests |
| Reports | 23 tests; figures reconciled against Gate History |
| **Total** | **428 passing** |

### Security properties, each tested

- Every page requires a login, enforced by `LoginRequiredMiddleware`
- Each view checks a Django permission server-side; hiding a link is not the control
- Residents hold **no** permissions and receive 403 on every staff page and API endpoint
- Guards cannot see resident phone numbers on the vehicle list or through the API
- `VehicleLog.recorded_by` is set from the session, never from request data
- `on_delete=PROTECT` prevents deleting a user whose movements are recorded
- A valid API token authenticates but grants no permission its owner lacks

## Implemented but not verified in a browser

Passing tests, never exercised by hand:

- The five API endpoints. Tests cover them thoroughly; no manual call has been made with curl or a browser.
- Reports date filters and empty states. The default view was verified; custom ranges were not.

## Not built

| Item | Note |
|---|---|
| **ANPR** | No detection, no OCR integration, no camera input |
| Deployment configuration | `DEBUG=True`, `ALLOWED_HOSTS` empty — development only |
| Offline static assets | Bootstrap and icons load from a CDN; the application loses its styling without internet |
| Token expiry | DRF's default tokens never expire; revoke manually |

## Blockers

### 1. No real vehicle photograph

**Impact:** nothing in the detection pipeline can be tested. Vehicle detection, plate detection, and the crop-to-OCR path all need an image containing a vehicle.

**Status:** the intern does not have access to a vehicle to photograph.

**Alternative under consideration:** public vehicle images with clear licensing. **Results from public images would indicate whether the pipeline runs, not how it performs at a housing society gate.** Camera position, angle, lighting and plate condition all differ.

### 2. No verified plate-detection model

**Impact:** a general YOLO model cannot find number plates. It is trained on 80 everyday categories and "number plate" is not among them. It finds cars, which is a different thing.

**Status:** two candidates were identified on Roboflow. Neither has been checked for downloadable weights, licence terms, class names, or training-data provenance.

**Required before any download:** confirm the model detects plates rather than vehicles; confirm weights can be downloaded and run locally; read the licence; check compatibility with the installed Ultralytics version.

### 3. No test images selected

**Status:** no public dataset chosen; licensing unexamined.

## ANPR: current state

Work took place in a separate lab at `C:\Users\gauri\Projects\anpr-lab`, outside this repository.

| Stage | Status |
|---|---|
| Environment | Working — Python 3.10, PyTorch 2.14.1+cpu, Ultralytics, OpenCV, EasyOCR |
| Model files | **None** — the `models` folder is empty |
| Test images | **Synthetic only** — one generated plate and ten derived variants |
| Vehicle detection | Not implemented |
| Plate detection | Not implemented, no verified model |
| OCR | Working — 50 recorded runs with real confidence values |
| Plate correction | Working — 20 tests passing |
| Real-image evidence | **None** |
| Django integration | None, deliberately |
| GPU | RTX 3050 present; the installed PyTorch is a CPU-only build |

### Findings from the OCR experiments

These are genuine experimental results, recorded because they shape how the finished system must behave.

**OCR failed on a perfect image.** Expected `MH12KL4567`, read `MH1ZKL4567`, confidence 0.7616. No blur, no angle, no noise.

**Confidence does not indicate correctness.** A wrong reading scored 0.917, higher than several correct ones. **A confidence threshold alone would not be a safe basis for accepting a plate.**

**Format knowledge recovers most errors.** The corrector fixed 27 of 28 failures by checking character types against known Indian registration formats, and correctly declined the 28th rather than guessing.

**Consequence for the design:** a guard must always be able to see and correct an automatic reading. This is why `POST /api/v1/gate/anpr-log/` rejects `source="anpr"` with HTTP 422 — the gate log has no field distinguishing an unverified reading from a confirmed movement, so storing one would present a guess as a fact.

## Principles the system holds to

Stated here because they are easy to lose when adding automation:

1. **An unrecognised plate is not an unauthorised vehicle.** Unknown means the plate did not match a registered vehicle or an expected visitor. A courier van is Unknown and legitimate.
2. **A valid plate format does not prove identity.** Format checking says "this looks like a plate", nothing more. Identity is a database question.
3. **An OCR reading is a candidate, not a fact.** It requires human confirmation before it becomes a record.
4. **Audit attribution is never invented.** Records predating the audit field show "Not recorded" rather than a plausible-looking user.

## What would make the project complete

| Task | Completion criterion |
|---|---|
| Verify a plate-detection model | Licence, classes and download method confirmed |
| Obtain test images | Source selected, licence recorded |
| Build the detection pipeline | A real image produces a plate string |
| Measure accuracy honestly | Results reported with their limitations stated |
| Design safe integration | A reviewed design for recording ANPR readings without presenting them as confirmed |
| Deployment hardening | `DEBUG=False`, `ALLOWED_HOSTS` set, HTTPS |
| Offline assets | Bootstrap served locally |

## Pending verification in this document

- Weeks 1–10 weekly allocation — the intern's original plans were unavailable
- Roboflow model availability and licensing — not yet checked
- API endpoints in a browser — tested but not manually exercised