# Housing Society Member & Vehicle Tracking System

A Django application for managing a housing society: residents, their vehicles, expected visitors, and every vehicle movement at the gate.

## Scope: what this does and does not do

**Implemented and tested.** Resident and vehicle records, visitor pre-registration with passes, gate entry and exit logging with automatic classification, three user roles with server-side permission checks, a resident self-service portal, a REST API, an audit trail, and reports.

**Not implemented.** The project title refers to AI-based vehicle security. **Automatic Number Plate Recognition is not integrated.** The gate currently accepts a vehicle number typed by a guard. A separate experimental lab exists outside this repository where OCR has been tested on synthetic images only. No vehicle detection, plate detection, or camera input exists in this application.

## Features

| Module | What it does | Tests |
|---|---|---|
| society | Wings and flats | 6 |
| residents | Resident records, search, optional login link | 50 |
| vehicles | Registration, plate normalization, duplicate prevention, search | 27 |
| tracking | Gate entry/exit, classification, history, audit trail | 93 |
| visitors | Pre-registration, pass codes, check-in/out, expiry | 64 |
| accounts | Three roles, login, resident portal, API tokens | 88 |
| dashboard | Live counts and recent activity | 4 |
| api | Five REST endpoints, token and session authentication | 73 |
| reports | Gate and visitor statistics with date filters | 23 |
| **Total** | | **428** |

### Gate classification

When a movement is recorded, the plate is normalized and checked:

1. Matches a registered vehicle → **Registered**
2. Matches a visitor expected that day → **Visitor**
3. Otherwise → **Unknown**

**Unknown means the plate was not recognised. It is not a judgement that the vehicle was unauthorised.** A courier van is Unknown and perfectly legitimate.

### Roles

| Role | Can do |
|---|---|
| Society Admin | Everything, including Django Admin and reports |
| Guard | Gate, gate history, visitors, view vehicles |
| Resident | Own account, own vehicles, own visitors only |

Permissions are enforced on the server. Hiding a link is not the control: typing a restricted address directly still returns 403.

## Technology

- Python 3.13.5
- Django 5.2.17
- PostgreSQL 17
- Django REST Framework 3.18.3
- HTML, CSS, Bootstrap 5

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

This creates the Society Admin, Guard and Resident groups with their permissions. The application will not restrict access correctly without it.

### 8. Create an administrator

```powershell
python manage.py createsuperuser
```

### 9. Optional: demo data

```powershell
python manage.py seed_demo_data --password "ChooseAPassword123!"
```

Creates residents, vehicles, visitors and gate movements, plus `demo_guard` and `demo_resident` logins. Safe to run more than once; it adds nothing the second time. Omit `--password` to create data without logins.

### 10. Run

```powershell
python manage.py runserver
```

Open http://127.0.0.1:8000/

## Testing

```powershell
python manage.py test
```

428 tests. A single module:

```powershell
python manage.py test vehicles
```

## API

Five endpoints under `/api/v1/`:

| Endpoint | Method | Permission |
|---|---|---|
| `ping/` | GET | any signed-in user |
| `vehicles/` | GET | `vehicles.view_vehicle` |
| `vehicles/lookup/?plate=` | GET | `vehicles.view_vehicle` |
| `gate/logs/` | GET | `tracking.view_vehiclelog` |
| `gate/anpr-log/` | POST | `tracking.add_vehiclelog` |

Both session and token authentication work. See `docs/api-tokens.md` for issuing, rotating and revoking tokens.

**The POST endpoint rejects `source="anpr"` with HTTP 422.** The gate log has no field distinguishing an unverified camera reading from a movement a person confirmed, so storing one would present a guess as a fact. A guard must confirm the plate and submit it as `source="manual"`.

## Project status

**Working and verified:** all nine modules above, 428 tests passing, demo data, role enforcement across every page and endpoint.

**Not built:** ANPR, deployment configuration (`DEBUG` is True and `ALLOWED_HOSTS` is empty), offline static assets (Bootstrap loads from a CDN).

**Blocked:** ANPR detection requires a plate-detection model whose licence and availability have not been verified, and test images that have not been selected.

## Limitations

- ANPR is not integrated; the gate requires a typed plate.
- API tokens do not expire; revoke them when a client no longer needs one.
- Development configuration only. Deployment needs `DEBUG=False`, `ALLOWED_HOSTS`, and HTTPS.
- Gate logs created before the audit field existed show "Not recorded" rather than a fabricated user.