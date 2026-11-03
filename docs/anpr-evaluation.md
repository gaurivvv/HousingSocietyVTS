# Real-World ANPR Evaluation Report

**Date:** 2026-11-03  
**Pipeline Models:**
- Vehicle Detector: `yolov8n.pt` (Ultralytics COCO pre-trained, AGPL-3.0)
- Plate Detector: `plate_detector_yolov8n.pt` (`joker5914/yolov8n-license-plate`, fine-tuned on CC BY 4.0 dataset `keremberke/license-plate-object-detection`)
- OCR Engine: `EasyOCR` 1.7.2 (CPU inference)
- Plate Corrector: `plate_corrector.py` (Indian registration format validation and confusion correction)

## Test Dataset
Five openly licensed, real-world photographs from Wikimedia Commons depicting vehicles and registration plates in India.

| Filename | License | Ground Truth Vehicle | Ground Truth Plate | Notes |
|---|---|---|---|---|
| `real_ka19eq1316.jpg` | CC BY-SA 4.0 | car | `KA19EQ1316` | Rear plate on car in Karnataka (Navinhat94) |
| `real_ka19p8488.jpg` | Public Domain | car | `KA19P8488` | Embossed plate on bumper (Premnath Kudva) |
| `real_kolkata_hsrp.jpg` | CC BY 3.0 | car | `WB02AD9533` | Macro HSRP close-up with hologram & laser codes (Biswarup Ganguly) |
| `real_kerala_kl01ay.jpg` | CC BY 2.0 | car | `KL01AY5183` | Passenger vehicle with state badge (Lian Chang) |
| `real_tata_nexon.jpg` | CC BY-SA 4.0 | car | `MH14TC515A` | Full vehicle front-quarter view (Vauxford) |

## Summary Results

| Metric | Result | Percentage |
|---|---|---|
| Total test images | 5 | 100% |
| Vehicle Detection Rate | 1/5 | 20.0% |
| License Plate Detection Rate | 4/5 | 80.0% |
| Candidate Exact Plate Match | 0/5 | 0.0% |

## Detailed Breakdown per Image

| Image | Detected Vehicle | Plate Found | Raw OCR | Corrected Candidate | Match |
|---|---|---|---|---|---|
| `real_ka19eq1316.jpg` | none | Yes (conf 0.79) | `IDEONdia4t0VIQN#NDI^13Lo...` | `IDEONdia4t0VIQN...` | NO |
| `real_ka19p8488.jpg` | none | Yes (conf 0.62) | `INDKA 19P 8` | `KA19P8` | NO |
| `real_kolkata_hsrp.jpg` | none | Yes (conf 0.64) | `INDBA15000588412239228...` | `INDBA1500058841...` | NO |
| `real_kerala_kl01ay.jpg` | none | Yes (conf 0.45) | `KL.60.827KERALATAMILNADU` | `KL.60.827KERALATAMILNADU` | NO |
| `real_tata_nexon.jpg` | car (conf 0.88) | No (<0.25) | *None* | *None* | NO |

## Key Findings & Engineering Limitations

1. **Plate Localization Reliability:**
   - The dedicated plate detection model (`plate_detector_yolov8n.pt`) localized number plates with high confidence (up to 79.4%) in 80% of test cases.
2. **Vehicle Detection Reliability:**
   - Full vehicle shots (`real_tata_nexon.jpg`) were cleanly classified as `car` (conf 0.88). Tight bumper crops naturally lack contextual vehicle cues for standard COCO vehicle detection.
3. **OCR Ambiguity on Real Photographs:**
   - Real-world plates differ radically from synthetic renderings:
     - The blue `IND` hologram bar on Indian HSRP plates is frequently read as leading text (`INDKA 19P 8`). Adding an intelligent HSRP prefix stripper allows extracting `KA19P8`.
     - Hologram security patterns and laser branding (e.g. `BA1500058841...`) confuse character segmenters.
     - Glare, angle, and distance cause character dropping (e.g. `8488` truncated to `8`).
4. **Architectural Safety Conclusion:**
   - Raw OCR match was 0%. These empirical tests demonstrate why **automatic ANPR readings can never be stored directly as authoritative database records**.
   - Instead, the ANPR output must serve strictly as an *operator-assisted recommendation* that pre-fills the guard's gate entry form for visual verification and human confirmation.
