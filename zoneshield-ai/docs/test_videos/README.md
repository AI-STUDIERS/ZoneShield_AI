# ZoneShield AI Test Videos

This directory contains standalone, reproducible test MP4 video datasets specifically formatted for the ZoneShield AI vision pipeline and digital-twin conveyor tests.

---

## Included Datasets

### 1. `conveyor_nominal_test.mp4`
* **Path:** `docs/test_videos/conveyor_nominal_test.mp4`
* **Resolution & Framerate:** 640x360 @ 30 FPS
* **Scenario:** Nominal industrial conveyor line.
  * Workpieces move along the center belt channel.
  * Distinct high-contrast metallic foreign objects enter the line and cross the belt towards the Shield Zone boundary.
* **Test Focus:** Validates standard MOG2 background subtraction, Kalman filter continuous tracking ID retention, and nominal Tier 1 air-jet intercept calculation.

---

### 2. `conveyor_ambiguous_debris.mp4`
* **Path:** `docs/test_videos/conveyor_ambiguous_debris.mp4`
* **Resolution & Framerate:** 640x360 @ 30 FPS
* **Scenario:** High-speed irregular debris with non-linear motion / bouncing dynamics.
  * Fast-moving irregular polygon fragments passing adjacent to the air-jet nozzle dispersion zone.
* **Test Focus:** Tests velocity vector prediction jitter, Guardrail G2 (Jet Cone Alignment) vetoes, and Tier 2 ambiguous threat evaluation.

---

## How to Test in the Dashboard

1. Launch the backend server:
   ```bash
   python -m backend.main
   ```
2. Open `http://localhost:8000` in your web browser.
3. In the header navigation bar:
   - Change the **Source** dropdown to **`Video File`**.
   - Click **`Upload Video File`** (or `Choose File`).
   - Select either `conveyor_nominal_test.mp4` or `conveyor_ambiguous_debris.mp4` from this directory.
4. Watch the real-time Kalman tracking, TTI calculation, and air-jet actuation overlays on the live canvas.
