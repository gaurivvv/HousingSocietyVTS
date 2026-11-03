# Housing Society Member & Vehicle Tracking System

A Django application for managing a housing society: residents, their vehicles, expected visitors, gate movements, and AI-assisted vehicle plate tracking.

## Scope: what this does and how AI is safely integrated

**Implemented and tested.** Resident and vehicle records, visitor pre-registration with passes, gate entry and exit logging with automatic 3-tier classification, three user roles with server-side permission checks, a resident self-service portal, a REST API, an audit trail, reports, offline static assets, production deployment hardening, and an AI-powered Automatic Number Plate Recognition (ANPR) pipeline.

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
| api | Six REST endpoints, token and session authentication | 77 |
| reports | Gate and visitor statistics with date filters | 23 |
| config | Offline static asset verification and production deployment checks | 4 |
| **Total** | | **446** |

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
- Offline Bootstrap 5.3.3 & Bootstrap Icons 1.11.3 (bundled locally)
- Ultralytics YOLOv8n (vehicle detection - AGPL-3.0)
- YOLOv8n License Plate Detector (`joker5914/yolov8n-license-plate` fine-tuned on CC BY 4.0 dataset, mAP 0.983)
- EasyOCR 1.7.2 & Custom Indian plate format corrector (`plate_corrector.py`)

## Setup (Windows PowerShell)

### Prerequisites

Python 3.13, PostgreSQL 17, and Git installed.

### 1. Clone and enter the project

```powershell
git clone https://github.com/gaurivvv/HousingSocietyVTS.git
cd HousingSocietyVTS
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the script:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Create the database

In psql, as a PostgreSQL superuser:

```sql
CREATE DATABASE housing_society_db;
CREATE USER housing_society_user WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE housing_society_db TO housing_society_user;
```

### 5. Configure settings

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your database password and a new secret key. Generate one with:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Never commit `.env`.** It is in `.gitignore`.

### 6. Apply migrations

```powershell
python manage.py migrate
```

### 7. Create the roles

```powershell
python manage.py setup_roles
```

### 8. Create an administrator

```powershell
python manage.py createsuperuser
```

### 9. Optional: demo data

```powershell
python manage.py seed_demo_data --password "ChooseAPassword123!"
```

### 10. Run

```powershell
python manage.py runserver
```

Open http://127.0.0.1:8000/

## Testing

```powershell
python manage.py test
```

446 automated tests passing with zero failures.

## API

Six endpoints under `/api/v1/`:

| Endpoint | Method | Permission |
|---|---|---|
| `ping/` | GET | any signed-in user |
| `vehicles/` | GET | `vehicles.view_vehicle` |
| `vehicles/lookup/?plate=` | GET | `vehicles.view_vehicle` |
| `gate/logs/` | GET | `tracking.view_vehiclelog` |
| `gate/anpr-scan/` | POST | `tracking.add_vehiclelog` |
| `gate/anpr-log/` | POST | `tracking.add_vehiclelog` |

Both session and token authentication work. See `docs/api-tokens.md` for issuing, rotating and revoking tokens.

**The `gate/anpr-log/` endpoint rejects `source="anpr"` with HTTP 422.** Unverified camera readings cannot be logged directly. A guard or operator must verify the plate and submit it with `source="manual"`.

## Project Documentation

- [Deployment Guide](docs/deployment.md) - Production configuration, SSL/TLS, and Nginx/Gunicorn setup.
- [ANPR Integration Guide](docs/anpr-guide.md) - Full explanation of the ML pipeline, models, and workflows.
- [ANPR Real-World Evaluation Report](docs/anpr-evaluation.md) - Empirical benchmarks on openly licensed vehicle photographs.
- [API Tokens](docs/api-tokens.md) - Token issuance, rotation, and revocation.
- [Project Status](docs/project-status.md) - Full audit of verified modules and architectural guarantees.
