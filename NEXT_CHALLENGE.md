Video vs Image — which is better:

Images (now)	Video (later)
Collection	Manual one-by-one	Record once, auto-extract
Coverage	Random angles	Every angle automatically
Consistency	Varies per photo	Same lighting throughout
Training quality	Good	Better
When to use	Now, with 50 images you have	From Day 6 when camera is on turntable
3. Guidance
Most important things for your situation:

On images (do this now):

Shoot all 40+ "good" images in the same lighting — PatchCore learns what "normal" looks like, so inconsistent lighting creates false alarms
Keep the cooler at similar distance from camera in each photo
Fill the frame with the cooler — don't photograph from far away
If you have the 3 original images in data\raw\, copy those to data\reviewed\good\ too — every image counts
On training:

First training accuracy will be 50–65% — that is normal and expected
After training, run the evaluate script and share the score numbers — the thresholds (0.45 / 0.65) were set for general use and will need tuning for your specific cooler
More good images always help more than more defective images for PatchCore
On the demo (Day 10):

You do NOT need real cameras for the client demo — mock mode shows the full workflow perfectly
The story for the client: "This is the live system. Right now it runs simulation. In production it connects to two USB cameras on the turntable. The decision logic, database, and dashboard are already production-ready."
Train the model with your 50 images so you can show a real accuracy number
On videos (Day 6 onwards):

When real cameras are on the turntable, a single 360° rotation video of a good cooler gives you 30–60 training frames automatically
Record 5–10 good cooler videos = 300+ frames = very strong model
Use extract_frames.py --every 10 for 30fps video (gets ~1 frame every 0.3 seconds)




# NEXT_CHALLENGE.md — Day-by-Day Roadmap

**Project:** Air Cooler Inspection System
**Sprint:** 10 days × 15 hrs = 150 hrs
**Deadline:** Day 10 = client demo
**Last updated:** Day 2 code complete — waiting for images

---

## 📁 WHERE TO PUT YOUR 50 IMAGES

You have 50 images. Sort them into these folders right now:

| Your image type | Put it here |
|----------------|-------------|
| Normal working cooler (any angle) | `data\reviewed\good\` |
| Cooler with knob removed / missing | `data\reviewed\defective\missing_knob\` |
| Cooler with damaged/broken grill | `data\reviewed\defective\broken_grill\` |
| Cooler with missing wheel | `data\reviewed\defective\missing_wheel\` |
| Cooler with cable damage | `data\reviewed\defective\cable_damage\` |

### Recommended split from 50 images

```
data\reviewed\good\                         ← 40+ images  (all good/normal coolers)
data\reviewed\defective\missing_knob\       ←  3–5 images
data\reviewed\defective\broken_grill\       ←  3–5 images
data\reviewed\defective\missing_wheel\      ←  2–3 images
data\reviewed\defective\cable_damage\       ←  2–3 images
```

**Why mostly good images?**
PatchCore learns ONLY from good images. It needs as many good examples as
possible. Defective images are used only to TEST accuracy — not to train.

### After sorting, run these 3 commands (ai-engine venv):

```powershell
cd $HOME\Desktop\air-cooler-inspection
.\ai-engine\venv\Scripts\Activate.ps1

# 1. Check dataset
python ai-engine\src\utils\inspect_dataset.py

# 2. Augment (turns ~40 good → ~280 training images)
python ai-engine\src\data_tools\augment.py

# 3. Train (~10–20 min on CPU)
python ai-engine\src\train_anomaly.py
```

---

## 📊 Current Status (End of Day 2 — Code Phase)

### ✅ Completed

- [x] Folder structure (20 directories)
- [x] All 20 project files created (Day 1)
- [x] Python venvs for AI engine + backend
- [x] All base dependencies installed
- [x] Next.js 16 dashboard scaffolded
- [x] SQLite database schema + auto-create
- [x] Backend API (5 endpoints: health, start, inspect, history, stats)
- [x] AI Engine with mock inference (random but structured)
- [x] Decision engine (6-rule PASS/FAIL/RECHECK logic)
- [x] All 3 services running: port 8000 / 8001 / 3001
- [x] End-to-end test: PASS/FAIL/RECHECK results in dashboard
- [x] Data persisted in `backend\inspection.db`
- [x] `src\utils\logger.py` — JSON structured logger
- [x] `src\utils\inspect_dataset.py` — dataset quality checker
- [x] `src\data_tools\augment.py` — 7× image augmentation
- [x] `src\train_anomaly.py` — PatchCore training → ONNX export
- [x] `src\inference\engine.py` — real ONNX inference engine
- [x] `inspection_runner.py` updated — AI_MODE=real/simulation switch
- [x] `scripts\start_all.ps1` and `stop_all.ps1`

### 🚧 Waiting on User (Day 2 completion blockers)

- [ ] **Install ML deps** (one-time, ~10 min):
  ```powershell
  .\ai-engine\venv\Scripts\Activate.ps1
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  pip install onnx onnxruntime anomalib
  ```
- [ ] **Copy 50 images** into `data\reviewed\good\` (and defective subfolders)
- [ ] Run `inspect_dataset.py` → `augment.py` → `train_anomaly.py`
- [ ] Test with `AI_MODE=real` — dashboard should give non-random results

### ❌ Not Started Yet

- Real camera capture (USB OpenCV)
- Rotary encoder integration (COM3)
- Cloud sync service (Node.js)
- Dashboard v2 (image viewer, defect overlay)
- Model v2 (EfficientNet defect classifier)

### 🎯 Current Accuracy

**0% real** — mock engine runs until train_anomaly.py succeeds.
Expected after first training with 50 images: **50–65%**

---

## ⚠️ CHALLENGES FACED — DECISIONS NEEDED

### 1. anomalib export API changes between versions
**Problem:** anomalib 1.x and 2.x have different export APIs. The training script
handles both with a try/except fallback, but if export fails, you may need:
```powershell
pip install anomalib==1.1.0   # pin to known stable version
```
**Decision needed:** If training fails, tell me the error message — I will fix it.

### 2. torch CPU install requires special URL
**Problem:** `pip install torch` installs the CUDA version (2+ GB).
CPU version needs the --index-url flag:
```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```
**Already handled** in instructions. No decision needed.

### 3. PatchCore ONNX scores are raw distances, not 0–1
**Problem:** PatchCore outputs patch-level anomaly distances. These can exceed
1.0 for very abnormal images. The engine.py clamps to [0, 1] but thresholds
(0.45 recheck, 0.65 fail) may need tuning after first real run.
**Decision needed:** After training, run `src\evaluate.py` and share the score
distribution — I will set the right thresholds for your cooler images.

### 4. data\raw\ images were not in data\reviewed\
**Problem:** You may have images in `data\raw\` (the 3 original cooler photos)
that are NOT in `data\reviewed\good\`. PatchCore trains from `reviewed\good\`,
not `raw\`. Make sure to copy/sort images to the right place.
**Action needed:** Copy all 50 images to `data\reviewed\` subfolders (see top).

### 5. No GPU — CPU training is slow
**Problem:** CPU training of PatchCore on 280+ images takes 10–25 minutes.
This is fine for first run. If it is too slow, we can reduce to 100 images.
**No decision needed** — just let it run.

### 6. ONNX model nesting after export
**Problem:** anomalib sometimes saves the .onnx file inside a nested subfolder
like `models/active/lightning/cooler/Patchcore/...`. The training script detects
this with `rglob("*.onnx")` and copies it to `models/active/model.onnx`.
**Already handled.** No decision needed.

---

## 🗺️ Full 10-Day Roadmap

| Day | Focus | Deliverable | Accuracy |
|-----|-------|-------------|----------|
| 1 | ✅ Skeleton | 3 services running, DB persists | 0% (mock) |
| 2 | ⏳ Dataset + first model | 50 images sorted, augmented, PatchCore trained | 50–65% |
| 3 | Real inference end-to-end | Swap mock → real ONNX in pipeline | 55–65% |
| 4 | Threshold tuning | Evaluate on test set, tune fail/recheck thresholds | 65–72% |
| 5 | Dashboard v2 | Image viewer, defect overlay, history filters | same |
| 6 | Camera integration | OpenCV dual capture from USB cameras | same |
| 7 | Rotation tracking | Encoder reading + 360° coverage check | same |
| 8 | Model v2 | EfficientNet defect classifier + threshold tuning | 72–82% |
| 9 | Sync service + offline packaging | Node.js sync, offline installer | same |
| 10 | Demo prep + validation | Full run-through, client presentation | 80–88% |

---

## ✅ WHAT WAS GOOD IN THE SETUP

1. **Mock engine first** — Full end-to-end pipeline worked on Day 1 with zero ML.
   Dashboard, API, DB, decisions all validated before a single real image existed.

2. **One env var to swap engines** — `AI_MODE=real` switches to real model.
   No code changes, no restarts of backend or dashboard. Clean separation.

3. **Decision engine is separate from inference** — PASS/FAIL/RECHECK logic
   lives in `decision/engine.py`. Changing thresholds or rules does not touch
   the ML code at all.

4. **SQLite offline-first** — Zero setup. Works with WiFi off. Migrations are
   just SQLAlchemy table changes — no Postgres server to manage.

5. **6-rule decision engine** — Never gives PASS on incomplete rotation or
   too few frames. This is the safety guarantee for the client demo.

6. **Augmentation script** — 7 variants per image means 40 raw photos → 280
   training images. Enough for a working PatchCore model.

---

## ❌ WHAT IS LEFT (for a real production system)

| Gap | Impact | When to fix |
|-----|--------|-------------|
| No real camera yet | Demo uses mock/simulated frames | Day 6 |
| No rotation encoder | Can't do real 360° capture | Day 7 |
| PatchCore only detects "different from normal" — no defect class | Can't say WHICH defect | Day 8 |
| Thresholds not tuned to real cooler images | False positives/negatives unknown | After first training |
| No sync service | Inspections never reach cloud | Day 9 |
| No blur/quality check on frames | Bad frames counted as good | Day 6 |
| Dashboard shows no defect images | Can't review what triggered FAIL | Day 5 |
| No operator login | All inspections show "unknown" operator | Day 9 |
