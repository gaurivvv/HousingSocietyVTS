# Project Status

**Last updated:** 3 November 2026

A plain, transparent account of what works, empirical test results, and production readiness.

## Summary

The Housing Society Member & Vehicle Tracking System is complete and verified: ten test suites, 446 automated tests passing, role-based security, offline static assets, production deployment hardening, and an integrated AI-assisted Automatic Number Plate Recognition (ANPR) pipeline with a safe human confirmation workflow.

## Verified Working

Confirmed by automated test runs, empirical ML evaluations, and browser execution.

| Area | Evidence |
|---|---|
| Society: wings and flats | 6 tests |
| Residents: CRUD, search, login link | 50 tests |
| Vehicles: normalization, duplicates, search | 27 tests |
| Gate tracking: entry/exit, classification, history, ANPR scan assist | 103 tests |
| Visitors: lifecycle, pass codes, expiry | 64 tests |
| Roles and permissions | 88 tests |
| Dashboard | 4 tests |
| REST API: 6 endpoints | 77 tests |
| Reports: analytics & date filters | 23 tests |
| Config: Offline static assets & deployment checks | 4 tests |
| **Total** | **446 passing (100% OK)** |

### Security Properties, Verified by Tests
- Every page requires an active login, enforced by `LoginRequiredMiddleware`.
- Each view checks server-side permissions; hiding UI links is not the security boundary.
- Residents hold no staff permissions and receive HTTP 403 on all staff pages and API endpoints.
- Guards cannot access resident phone numbers on the vehicle list or API endpoints.
- `VehicleLog.recorded_by` is set from the authenticated session, never request data.
- `on_delete=models.PROTECT` prevents deleting any user whose gate movements are recorded.
- API tokens authenticate callers without bypassing role-based permissions.
- Direct submission of unverified `source="anpr"` movements is rejected with HTTP 422.

---

## Offline Static Assets & Deployment

1. **Offline Assets:**
   - Bootstrap 5.3.3 (`bootstrap.min.css`, `bootstrap.bundle.min.js`) and Bootstrap Icons 1.11.3 (`bootstrap-icons.min.css`, `.woff2`, `.woff`) are bundled locally under `static/vendor/`.
   - Zero external CDN dependencies in HTML templates.
2. **Production Deployment Configuration:**
   - `DEBUG` dynamically reads `DJANGO_DEBUG` (defaults safely to `False`).
   - `ALLOWED_HOSTS` reads comma-separated values from `DJANGO_ALLOWED_HOSTS`.
   - Production security headers active when `DEBUG=False`: `SECURE_BROWSER_XSS_FILTER`, `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS = "DENY"`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, and optional `SECURE_SSL_REDIRECT` / `SECURE_HSTS_SECONDS`.
   - `STATIC_ROOT` configured for `collectstatic`.
   - Django deployment check (`python manage.py check --deploy`) passes cleanly with 0 issues.

---

## ANPR Integration & Real-World Evaluation

### Architecture
- **Vehicle Detection:** `yolov8n.pt` (Ultralytics COCO pre-trained, detecting `car`, `motorcycle`, `bus`, `truck`).
- **Plate Detection:** `plate_detector_yolov8n.pt` (`joker5914/yolov8n-license-plate`, fine-tuned on CC BY 4.0 dataset `keremberke/license-plate-object-detection`).
- **OCR Engine:** EasyOCR 1.7.2.
- **Plate Corrector:** Format-aware corrector (`plate_corrector.py`) with support for Indian standard plates, BH-series plates, and HSRP `"IND"` prefix stripping.
- **Guard Confirmation Workflow:** AI predictions pre-fill the gate entry console for guard verification. Movements are only committed to the database when confirmed by the guard.

### Empirical Real-World Evaluation
Evaluated on 5 openly licensed real-world photographs from Wikimedia Commons (`docs/anpr-evaluation.md`):
- License plate detection rate: **80.0% (4/5)**.
- Vehicle detection cleanly categorizes passenger cars.
- Demonstrated that lighting, HSRP laser watermarks, and camera angles degrade raw character recognition, validating the necessity of guard verification.

---

## Architectural Principles Upheld

1. **An unrecognised plate is not an unauthorised vehicle:** "Unknown" means the plate did not match a registered vehicle or expected visitor.
2. **An OCR reading is a candidate, not a database fact:** Requires human confirmation before logging.
3. **Audit attribution is never invented:** Records maintain verifiable author credentials (`recorded_by`).
4. **Manual gate logging is always preserved:** Guards can always enter plates manually if an image cannot be read.
