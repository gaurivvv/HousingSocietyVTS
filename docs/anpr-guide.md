# Automatic Number Plate Recognition (ANPR) Integration Guide

This document describes the ANPR pipeline architecture, model licensing, security invariants, and the guard review workflow.

---

## 1. Architectural Principles

1. **AI Predictions Are Recommendations, Not Authoritative Facts:**
   Under real-world conditions (dirt, glare, angle, HSRP holographic patterns, and character similarities like `O`/`0` or `1`/`I`), optical character recognition can misread plates. An automatic reading must never be written directly to the database as a recorded movement.
2. **Guard Verification Required:**
   The ANPR pipeline generates a **candidate** plate. The candidate pre-populates the guard's gate console. The guard verifies the physical vehicle plate before clicking **Record Movement**.
3. **Manual Gate Entry Always Works:**
   If a camera fails, an image is blurred, or an operator prefers to type, manual entry remains 100% operational.
4. **Audit Integrity:**
   Every movement saved via the gate console records `recorded_by=request.user` (the signed-in guard). Movements confirmed from an ANPR scan carry the remark `"AI-assisted (Verified by Guard)"`.

---

## 2. Models & Open-Source Licensing

| Component | Architecture / Model | Source / Checkpoint | License |
|---|---|---|---|
| **Vehicle Detection** | YOLOv8n (nano) | Ultralytics COCO pre-trained weights (`yolov8n.pt`) | AGPL-3.0 |
| **Number Plate Detection** | YOLOv8n (nano) | `joker5914/yolov8n-license-plate` fine-tuned on CC BY 4.0 dataset | AGPL-3.0 (weights) / CC BY 4.0 (dataset) |
| **OCR Engine** | EasyOCR 1.7.2 | PyTorch & CRAFT text detector + CRNN recognizer | Apache 2.0 |
| **Format Corrector** | Rule-based Python engine | `anpr-lab/scripts/plate_corrector.py` | MIT |

---

## 3. Real-World Evaluation Findings

Evaluated on 5 openly licensed photographs of vehicles in India from Wikimedia Commons (`docs/anpr-evaluation.md`):
- **Plate Detection Rate:** **80.0% (4/5)**
- **Vehicle Classification Rate:** Cleanly classifies full vehicle shots as `car`; suppresses false vehicle hallucinations on tight bumper crops.
- **HSRP Country Code Handling:** The pipeline automatically identifies and removes the embossed left-hand `"IND"` country marker found on Indian High Security Registration Plates, preventing false 12-character plate errors.
- **OCR Limitations in Practice:** Bumper glare, hologram codes, and distance can degrade raw OCR accuracy, reinforcing the necessity of human operator confirmation.

---

## 4. Workflows

### Guard Console (`/gate/`)
1. Guard clicks **ANPR Camera Assist** and uploads/captures a vehicle photograph.
2. Click **Scan Plate**.
3. The system highlights:
   - Candidate Plate (e.g. `MH12AB1234`)
   - Vehicle Type (e.g. `CAR`)
   - Detection & OCR Confidence Percentages
   - Database Matching Status: **Registered Resident** (with Flat), **Expected Visitor** (with host Flat), or **Unknown**.
4. The candidate plate is auto-filled into the **Vehicle number** field.
5. The guard verifies the plate with the driver and clicks **Record Movement**.

### REST API

#### 1. Scan Vehicle Image (AI Candidate Detection)
```http
POST /api/v1/gate/anpr-scan/
Authorization: Token <guard-or-admin-token>
Content-Type: multipart/form-data

image: <binary image file>
```
**Response (HTTP 200):**
```json
{
  "success": true,
  "candidate_plate": "KA19P8",
  "vehicle_detected": true,
  "vehicle_type": "car",
  "plate_detected": true,
  "plate_confidence": 0.62,
  "ocr_confidence": 0.81,
  "format_status": "corrected_candidate",
  "corrections": ["prefix:IND"],
  "recorded": false,
  "instruction": "This candidate plate has NOT been saved to the gate log. The operator must verify the plate with the driver, then submit the confirmed movement to /api/v1/gate/anpr-log/ with source='manual'."
}
```

#### 2. Confirm Movement
```http
POST /api/v1/gate/anpr-log/
Authorization: Token <guard-or-admin-token>
Content-Type: application/json

{
  "plate_number": "KA19P8488",
  "movement_type": "ENTRY",
  "source": "manual",
  "remarks": "AI-assisted (Verified by Guard)"
}
```
*Note: Directly submitting `source="anpr"` to `/api/v1/gate/anpr-log/` is strictly rejected with HTTP 422.*
