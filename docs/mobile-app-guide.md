# Cross-Platform Mobile Application Guide

**Project:** Housing Society Member & Vehicle Tracking System (VTS)  
**Technology Stack:** React Native, Expo SDK 58, Django REST Framework 3.18, PostgreSQL 17  
**App Directory:** `C:\Users\gauri\Projects\HousingSocietyApp`  
**Backend API Endpoint:** `http://192.168.1.109:8000/api/v1`

---

## 1. System Architecture Overview

The system combines a Django backend with a React Native cross-platform application to support three core operational roles:

```
+-------------------------------------------------------------+
|                      React Native App                       |
|                   (Expo Go / Android / iOS)                 |
+---------------------+-------------------+-------------------+
|     Guard Role      |   Resident Role   |    Admin Role     |
| - ANPR Gate Camera  | - My Vehicles     | - Society Stats   |
| - Plate Review Card | - Pre-register    | - Live Telemetry  |
| - Visitor Passes    |   Visitor Passes  | - Movement Feed   |
+----------+----------+---------+---------+---------+---------+
           |                    |                   |
           +--------------------+-------------------+
                                | REST (Token Auth)
                                v
+-------------------------------------------------------------+
|                     Django 5.2.17 REST API                  |
|       (/api/v1/auth/login/, /api/v1/gate/anpr-scan/...)      |
+------------------------------+------------------------------+
                               |
                +--------------+---------------+
                |                              |
                v                              v
       PostgreSQL Database             ANPR Subprocess Service
     (Society, Residents,           (YOLOv8 + Plate Detector +
       Vehicles, Logs)                      EasyOCR)
```

---

## 2. API Endpoints Connected to Mobile App

| Endpoint | Method | Role | Description |
| :--- | :--- | :--- | :--- |
| `/api/v1/auth/login/` | `POST` | Public | Authenticates user; returns AuthToken, role name, and resident context. |
| `/api/v1/gate/anpr-scan/` | `POST` | Guard, Admin | Uploads vehicle image; executes ANPR pipeline; returns plate candidate, vehicle type, and confidence. |
| `/api/v1/gate/anpr-log/` | `POST` | Guard, Admin | Human-in-the-loop movement confirmation (Entry/Exit, Category, Remarks). |
| `/api/v1/guard/visitors/` | `GET` | Guard, Admin | Today's expected, checked-in, and departing visitors with search filter. |
| `/api/v1/visitors/<id>/check-in/` | `POST` | Guard, Admin | Checks in visitor at gate. |
| `/api/v1/visitors/<id>/check-out/` | `POST` | Guard, Admin | Checks out departing visitor. |
| `/api/v1/resident/me/` | `GET` | Resident | Retrieves resident profile, active vehicles, and visitors. |
| `/api/v1/resident/visitors/` | `POST` | Resident | Pre-registers a visitor and generates a `VP-XXXXX` digital pass. |
| `/api/v1/dashboard/stats/` | `GET` | Guard, Admin | Live counts of vehicles inside, total vehicles, residents, and movements. |
| `/api/v1/gate/logs/` | `GET` | Guard, Admin | History of recent gate entries/exits with timestamps. |

---

## 3. Pre-Configured Demo Credentials

The mobile app includes **One-Tap Demo Login chips** on the login screen for instant evaluation:

| Role | Username | Password | Linked Profile / Permissions |
| :--- | :--- | :--- | :--- |
| **Gate Guard** | `demo_guard` | `Guard@123` | Full gate operations, camera ANPR scanning, and visitor passes |
| **Resident** | `demo_resident` | `Resident@123` | Rajesh Sharma, Flat A-102 (Vehicle: `MH12KL4567` Hyundai i20) |
| **Society Admin** | `gauri` | *(master)* | Live society telemetry, overview stats, and gate activity feed |

---

## 4. How to Run the Demonstration

### Step 1: Start Django Backend (Accessible on LAN)
Open a PowerShell terminal:
```powershell
cd C:\Users\gauri\Projects\HousingSocietyVTS
.\.venv\Scripts\Activate.ps1
python manage.py runserver 0.0.0.0:8000
```

### Step 2: Start the Expo Mobile App
Open a second PowerShell terminal:
```powershell
cd C:\Users\gauri\Projects\HousingSocietyApp
npx expo start
```

### Step 3: Run on Physical Device or Browser
- **On Android or iOS Mobile Phone:**
  1. Connect your phone to the same Wi-Fi network (`192.168.1.109`).
  2. Open the **Expo Go** app on your phone.
  3. Scan the QR code shown in the Expo terminal.
- **On Web Browser (Desktop / Laptop):**
  - Press `w` in the Expo terminal to open the app directly in your browser.
- **On Android Emulator:**
  - Press `a` in the Expo terminal.
