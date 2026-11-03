# Housing Society Member & Vehicle Tracking System

A Django and React Native full-stack application for managing a housing society: residents, their vehicles, expected visitors, gate movements, an AI-assisted vehicle plate tracking pipeline, and a cross-platform mobile app.

## Scope: what this does and how AI is safely integrated

**Implemented and tested.** Resident and vehicle records, visitor pre-registration with passes, gate entry and exit logging with automatic 3-tier classification, three user roles with server-side permission checks, a resident self-service portal, a REST API, an audit trail, reports, offline static assets, production deployment hardening, an AI-powered Automatic Number Plate Recognition (ANPR) pipeline, and a React Native cross-platform mobile application.

**Safe AI Design Principle.** Optical Character Recognition in real conditions (dirt, glare, angle, high-security holograms) can misread characters. Therefore, **ANPR predictions are never recorded directly into the database as facts**. Instead, the AI pipeline extracts and normalizes a candidate plate to assist the guard. The candidate pre-fills the gate console for visual verification and driver confirmation before the movement is logged. Manual gate entry and exit remain 100% operational at all times.

## Features

| Module | What it does | Tests |
|---|---|---|
| society | Wings and flats | 6 |
| residents | Resident records, search, optional login link | 50 |
| vehicles | Registration, plate normalization, duplicate prevention, search | 27 |
| tracking | Gate entry/exit, classification, history, audit trail, ANPR scan assist | 103 |
| visitors | Pre-registration, pass codes, check-in/out, expiry | 64 |
| accounts | Three roles, login, resident portal, API tokens | 88 |
| dashboard | Live counts and recent activity | 4 |
| api | 13 REST endpoints, token and session authentication | 84 |
| reports | Gate and visitor statistics with date filters | 23 |
| config | Offline static asset verification, CORS, and deployment checks | 5 |
| **Total** | | **454** |

### Gate classification

When a movement is recorded, the plate is normalized and checked:

1. Matches a registered vehicle → **Registered**
2. Matches a visitor expected that day → **Visitor**
3. Otherwise → **Unknown**

**Unknown means the plate was not recognised. It is not a judgement that the vehicle was unauthorised.** A courier van is Unknown and perfectly legitimate.

### Roles

| Role | Can do |
|---|---|
| Society Admin | Everything, including Django Admin, ANPR, and reports |
| Guard | Gate console, ANPR camera scan assist, gate history, visitors, view vehicles |
| Resident | Own account, own vehicles, own visitors only |

Permissions are enforced on the server. Hiding a link is not the control: typing a restricted address directly returns 403.

## Technology & ML Stack

- Python 3.13.5 (Django backend) & Python 3.10.0 (ANPR ML environment)
- Django 5.2.17 & Django REST Framework 3.18.3
- PostgreSQL 17
- React Native & Expo SDK 58 (cross-platform mobile app)
- Offline Bootstrap 5.3.3 & Bootstrap Icons 1.11.3 (bundled locally)
- Ultralytics YOLOv8n (vehicle detection - AGPL-3.0)
- YOLOv8n License Plate Detector (`joker5914/yolov8n-license-plate` fine-tuned on CC BY 4.0 dataset, mAP 0.983)
- EasyOCR 1.7.2 & Custom Indian plate format corrector (`plate_corrector.py`)

## Cross-Platform Mobile Application (HousingSocietyApp)

Located at `C:\Users\gauri\Projects\HousingSocietyApp`:
- **Guard Portal**: Mobile camera / gallery ANPR scanning, plate verification card, visitor pass check-in/out.
- **Resident Portal**: My vehicles, guest pre-registration with instant `VP-XXXXX` digital passes.
- **Admin Portal**: Live society metrics, vehicle counts, and recent gate movements feed.
- See the [Mobile App Guide](docs/mobile-app-guide.md) for complete details.

## Setup (Windows PowerShell)

### Prerequisites

- Python 3.13 installed
- PostgreSQL running locally with database `housing_society_db`
- Node.js 24+ and npm (for mobile app)

### 1. Environment and dependencies

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Environment variables

Copy `.env.example` to `.env` and fill in:

```env
DB_NAME=housing_society_db
DB_USER=housing_society_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
DJANGO_SECRET_KEY=your_secret_key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,192.168.1.109
```

### 3. Run database migrations

```powershell
python manage.py migrate
```

### 4. Create user roles and initial admin

```powershell
python manage.py setup_roles
python manage.py createsuperuser
```

### 5. Seed demo data (optional)

```powershell
python manage.py seed_demo_data --password Society@123
```

This creates demo accounts:
- `demo_guard` (password: `Guard@123`)
- `demo_resident` (password: `Resident@123`)

### 6. Run the server

```powershell
python manage.py runserver 0.0.0.0:8000
```

Open http://127.0.0.1:8000/ in your browser.

## Running Tests

```powershell
python manage.py test
```

454 automated tests passing with zero failures.

## API

Thirteen endpoints under `/api/v1/`:

| Endpoint | Method | Permission | Description |
|---|---|---|---|
| `auth/login/` | POST | AllowAny | Mobile/Client login returning AuthToken & role |
| `ping/` | GET | IsAuthenticated | Confirm API connectivity |
| `vehicles/` | GET | `vehicles.view_vehicle` | List registered vehicles |
| `vehicles/lookup/?plate=` | GET | `vehicles.view_vehicle` | Fast vehicle lookup |
| `gate/logs/` | GET | `tracking.view_vehiclelog` | Gate movement history |
| `gate/anpr-scan/` | POST | `tracking.add_vehiclelog` | AI vehicle & plate detection |
| `gate/anpr-log/` | POST | `tracking.add_vehiclelog` | Guard-confirmed gate logging |
| `resident/me/` | GET | IsAuthenticated | Resident profile, vehicles & visitors |
| `resident/visitors/` | POST | IsAuthenticated | Mobile visitor pre-registration |
| `guard/visitors/` | GET | `visitors.view_visitor` | Today's visitor pass management |
| `visitors/<pk>/check-in/` | POST | `visitors.check_in_out_visitor` | Visitor gate check-in |
| `visitors/<pk>/check-out/` | POST | `visitors.check_in_out_visitor` | Visitor gate check-out |
| `dashboard/stats/` | GET | `tracking.view_vehiclelog` | Live society telemetry counts |

Both session and token authentication work. See `docs/api-tokens.md` for issuing, rotating and revoking tokens.

**The `gate/anpr-log/` endpoint rejects `source="anpr"` with HTTP 422.** Unverified camera readings cannot be logged directly. A guard or operator must verify the plate and submit it with `source="manual"`.

## Project Documentation

- [Mobile Application Guide](docs/mobile-app-guide.md) - React Native mobile app architecture and workflows.
- [Deployment Guide](docs/deployment.md) - Production configuration, SSL/TLS, and Nginx/Gunicorn setup.
- [ANPR Integration Guide](docs/anpr-guide.md) - Full explanation of the ML pipeline, models, and workflows.
- [ANPR Real-World Evaluation Report](docs/anpr-evaluation.md) - Empirical benchmarks on openly licensed vehicle photographs.
- [API Tokens](docs/api-tokens.md) - Token issuance, rotation, and revocation.
- [Project Status](docs/project-status.md) - Full audit of verified modules and architectural guarantees.
