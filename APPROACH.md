# APPROACH.md — Complete System Approach & Architecture

**Project:** Air Cooler Inspection System
**Product:** Brize Glacier 110 air cooler
**Goal:** Automated 360° visual QC — every cooler gets PASS / FAIL / RECHECK before leaving the factory
**Sprint:** 10 days × 15 hrs = 150 hrs to client demo

---

## 1. The Core Problem

A human inspector walks around a cooler and checks it visually. This is:
- **Slow** — takes 2–3 minutes per unit
- **Inconsistent** — depends on who is working that shift
- **Undocumented** — no record if a defective unit slips through

This system replaces that with a machine that puts the cooler on a turntable, rotates it 360°, photographs it from every angle, and gives a verdict in under 30 seconds.

---

## 2. What Defects Are Detected

| Defect | How Identified |
|--------|----------------|
| Missing pump knob | PatchCore anomaly + EfficientNet classifier |
| Missing speed knob | PatchCore anomaly + EfficientNet classifier |
| Broken/missing fan grill | PatchCore anomaly |
| Missing caster wheel | PatchCore anomaly |
| Cable damage | PatchCore anomaly |
| Missing fan assembly | PatchCore anomaly |

---

## 3. System Architecture — 3 Services + 1 Database

```
  [Dashboard]          [Backend API]         [AI Engine]
  Next.js :3001  <-->  FastAPI :8000   <-->  FastAPI :8001
                           |
                      [SQLite DB]
                    backend/inspection.db
```

### Service 1 — AI Engine (port 8001)
- **Language:** Python 3.12
- **Framework:** FastAPI + Uvicorn
- **Venv:** `ai-engine\venv\`
- **Entry:** `ai-engine\main.py`
- **Role:** Runs the inspection pipeline — captures frames, runs AI model, returns verdict
- **Endpoints:**
  - `GET  /health` — is AI engine alive?
  - `POST /inspect` — run a full inspection given inspection_id + cooler_serial
  - `POST /analyse-image` — analyse a single uploaded image (for testing)

### Service 2 — Backend API (port 8000)
- **Language:** Python 3.12
- **Framework:** FastAPI + SQLAlchemy + Uvicorn
- **Venv:** `backend\venv\`
- **Entry:** `backend\app\main.py`
- **Role:** Business logic — creates inspection records, calls AI engine, saves results to DB
- **Endpoints:**
  - `GET  /health` — checks DB + AI engine
  - `POST /inspection/start` — creates DB record, calls AI engine, saves verdict
  - `GET  /inspection/{id}` — fetch one inspection with defects
  - `GET  /history` — paginated list of past inspections
  - `GET  /stats` — total/pass/fail/recheck counts + pass rate
  - `POST /analyse-image` — proxy to AI engine + save image file
  - `POST /feedback` — record human correction on a prediction
  - `GET  /corrections` — list human corrections

### Service 3 — Dashboard (port 3001)
- **Language:** TypeScript
- **Framework:** Next.js 16 + React + Tailwind CSS
- **Runtime:** Node.js 24 + Turbopack
- **Entry:** `dashboard\app\page.tsx`
- **Role:** Operator UI — start inspection, see result live, review history

### Database — SQLite
- **File:** `backend\inspection.db` (auto-created on first start)
- **ORM:** SQLAlchemy 2.x
- **Why SQLite:** Zero setup, offline-first, no server needed, easy to move to PostgreSQL later

---

## 4. Folder Structure

```
air-cooler-inspection/
│
├── ai-engine/                     ← Python: cameras + AI
│   ├── main.py                    ← FastAPI app, port 8001
│   ├── venv/                      ← Python 3.12 venv
│   └── src/
│       ├── camera/
│       │   ├── capture.py         ← single USB camera (OpenCV)
│       │   ├── dual_capture.py    ← 2 cameras simultaneously
│       │   └── quality.py         ← blur + brightness check
│       ├── rotation/
│       │   └── encoder.py         ← rotary encoder via serial (COM3)
│       ├── inference/
│       │   ├── mock_engine.py     ← simulation (no model needed)
│       │   ├── engine.py          ← ONNX inference (production)
│       │   └── torch_engine.py    ← PyTorch checkpoint inference
│       ├── decision/
│       │   └── engine.py          ← PASS/FAIL/RECHECK rules
│       ├── pipeline/
│       │   └── inspection_runner.py ← orchestrates full inspection
│       ├── data_tools/
│       │   ├── augment.py         ← 7× image augmentation
│       │   ├── extract_frames.py  ← pull frames from video
│       │   ├── annotate_views.py  ← label images
│       │   └── apply_corrections.py ← move feedback to training set
│       └── utils/
│           ├── logger.py          ← JSON structured logger
│           └── inspect_dataset.py ← dataset quality checker
│
├── backend/
│   ├── app/
│   │   ├── main.py                ← FastAPI app, port 8000
│   │   └── database/
│   │       └── models.py          ← SQLAlchemy tables
│   ├── inspection.db              ← SQLite (auto-created)
│   └── venv/
│
├── dashboard/
│   ├── app/
│   │   ├── page.tsx               ← main operator screen
│   │   └── layout.tsx
│   └── package.json
│
├── sync-service/                  ← Node.js cloud sync (Day 9)
│
├── data/
│   ├── raw/                       ← original cooler photos
│   ├── reviewed/
│   │   ├── good/                  ← 40+ confirmed-good images
│   │   └── defective/             ← defect examples (test only)
│   ├── augmented/                 ← 280+ training images after augment.py
│   └── test_inspection/           ← test frames for simulation
│
├── models/
│   └── active/
│       └── model.onnx             ← trained model (after train_anomaly.py)
│
├── configs/
│   └── settings.yaml              ← all thresholds + ports
│
└── scripts/
    ├── start_all.ps1
    ├── stop_all.ps1
    └── run.ps1                    ← quick launcher (clears ports first)
```

---

## 5. Full Inspection Flow (Step by Step)

```
Operator types "COOL-001" → clicks Start Inspection
         │
         ▼
Dashboard  POST /inspection/start  →  Backend
         │
         ▼
Backend creates:
  • coolers row (if new)
  • inspections row  result = "IN_PROGRESS"
         │
         ▼
Backend  POST /inspect  →  AI Engine
         │
         ▼
InspectionRunner.run()
  ┌─ For each of 24 angles (0°, 15°, 30° ... 345°) ─────────────┐
  │   Camera 1 → capture frame → quality check → inference       │
  │   Camera 2 → capture frame → quality check → inference       │
  │   Each inference returns: anomaly_score, defect_type,        │
  │   confidence, is_defective, recheck flag                     │
  └──────────────────────────────────────────────────────────────┘
         │
         ▼
DecisionEngine.decide()  →  PASS / FAIL / RECHECK
         │
         ▼
Backend saves result + defects to SQLite
         │
         ▼
Dashboard shows verdict + defect list + updates history table
```

---

## 6. The AI Model Pipeline

### Phase 1 — Simulation (Now, Day 1–7)
`MockInferenceEngine` returns randomised but realistic results:
- 8% chance of defect per frame
- Anomaly score 0.55–0.95 for defects, 0.1–0.4 for clean frames
- Synthetic heatmap overlay on the cooler image

### Phase 2 — PatchCore Anomaly Detection (Day 2–4)
**What:** Learns what a "normal" cooler looks like. Anything different = anomaly.
**Why PatchCore:** Needs only good images to train — no defect labels required.
**Training flow:**
```
data/reviewed/good/  (40+ images)
       │
       ▼
augment.py  →  7 augmented variants per image  →  ~280 images
       │
       ▼
train_anomaly.py  →  PatchCore via anomalib  →  model.onnx / model.ckpt
       │
       ▼
engine.py / torch_engine.py  →  anomaly score 0.0–1.0
```
**Output:** Single float — anomaly score. High score = something looks wrong.

### Phase 3 — EfficientNet Classifier (Day 8)
**What:** Classifies WHICH defect it is (missing_knob, broken_grill, etc.)
**Why needed:** PatchCore says "something is wrong". EfficientNet says "it's a missing knob."
**Input:** Cropped region around the anomaly
**Output:** defect class + confidence 0.0–1.0

### Phase 4 — ONNX Export (Production)
Both models export to `.onnx` for fast CPU inference without PyTorch overhead.
PatchCore `.ckpt` checkpoint is preferred (memory bank intact) with ONNX as fallback.

---

## 7. The Decision Engine (Most Critical Logic)

File: `ai-engine/src/decision/engine.py`

Rules applied in order — first rule that fires wins:

| Rule | Condition | Result | Why |
|------|-----------|--------|-----|
| 1 | Rotation < 90% complete | RECHECK | Didn't see full cooler |
| 2 | Both cameras failed | RECHECK | Hardware problem |
| 3 | < 10 frames analysed | RECHECK | Lighting/camera issue |
| 4 | Missing critical component detected | FAIL | Safety critical |
| 5a | anomaly_score ≥ 0.65 AND confidence ≥ 0.60 | FAIL | High-confidence defect |
| 5b | anomaly_score ≥ 0.65 AND confidence < 0.60 | RECHECK | Possible defect, not sure |
| 5c | anomaly_score 0.45–0.65 | RECHECK | Borderline, human checks |
| 6 | > 30% of frames are recheck | RECHECK | Too much uncertainty |
| Default | All clean | PASS | |

**Rule:** System can never return PASS on an incomplete inspection.
This is the production safety guarantee.

---

## 8. Thresholds (tunable in `configs/settings.yaml`)

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `anomaly_score_fail` | 0.65 | Above this = candidate FAIL |
| `anomaly_score_recheck` | 0.45 | Between 0.45–0.65 = RECHECK |
| `classify_min_confidence` | 0.60 | Classifier must be ≥ 60% sure |
| `min_coverage_percent` | 90.0 | Must see ≥ 324° of rotation |
| `blur_score_minimum` | 80.0 | Reject blurry frames (Laplacian variance) |

These are **starting values**. After first real training, run `src/evaluate.py` and `src/tune_thresholds.py` to find optimal values for your specific cooler.

---

## 9. Operating Modes

Controlled by one env var `AI_MODE`:

| Mode | Engine Used | When |
|------|-------------|------|
| `simulation` | MockInferenceEngine (random) | Now — no model needed |
| `real` | TorchInferenceEngine → RealInferenceEngine (ONNX) → MockInferenceEngine (fallback) | After training |

**Switch:** Change `AI_MODE` env var, restart AI engine only. No code changes, no DB changes.

---

## 10. Database Schema

### `coolers`
Registers each physical unit by serial number.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | auto |
| serial_no | VARCHAR UNIQUE | e.g. COOL-001 |
| model | VARCHAR | "Brize Glacier 110" |
| created_at | DATETIME | |

### `inspections`
One row per inspection run.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| cooler_id | FK → coolers | |
| result | VARCHAR | PASS / FAIL / RECHECK / IN_PROGRESS |
| rotation_completed | FLOAT | 0–360 |
| frames_analysed | INTEGER | usually 48 |
| fail_reasons | JSON | list of defect type strings |
| synced_cloud | BOOLEAN | false until cloud sync runs |
| duration_seconds | FLOAT | |
| operator_id | VARCHAR | who started it |
| model_version | VARCHAR | which model was used |

### `defects`
One row per detected defect.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| inspection_id | FK | |
| camera_id | INTEGER | 1 or 2 |
| rotation_angle | FLOAT | at what angle (0–360) |
| defect_type | VARCHAR | "missing_knob" etc |
| anomaly_score | FLOAT | PatchCore output |
| confidence | FLOAT | classifier confidence |
| image_path | VARCHAR | path to saved frame |
| bbox | JSON | bounding box of defect |

### `corrections`
Human feedback on model predictions — feeds back into training.

| Column | Type | Notes |
|--------|------|-------|
| image_id | VARCHAR | UUID of saved image |
| predicted | VARCHAR | what model said |
| actual | VARCHAR | what it really is |
| correct_type | VARCHAR | correct defect type |
| applied | BOOLEAN | moved to training set yet? |

### `sensor_readings`
Reserved for water level, motor current, temperature (Day 9+).

---

## 11. Full Software Stack

### AI Engine
| Library | Version | Purpose |
|---------|---------|---------|
| FastAPI | 0.115+ | REST API for AI service |
| Uvicorn | 0.34+ | ASGI server |
| OpenCV (cv2) | 4.x | Camera capture + image processing |
| NumPy | 2.x | Array math |
| Pillow | 11.x | Image format conversion |
| PyTorch | 2.x (CPU) | Load PatchCore model |
| torchvision | 0.21+ | Pretrained ResNet backbone |
| anomalib | 1.x | PatchCore training + export |
| onnxruntime | 1.20+ | Fast CPU inference |
| pyserial | 3.5+ | Rotary encoder via COM3 |
| imagehash | 4.x | Duplicate frame detection |
| scikit-learn | 1.6+ | Threshold tuning utilities |

### Backend
| Library | Version | Purpose |
|---------|---------|---------|
| FastAPI | 0.162+ | REST API |
| SQLAlchemy | 2.1+ | SQLite ORM |
| Pydantic | 2.14+ | Request/response validation |
| httpx | 0.28+ | Async HTTP client (calls AI engine) |
| Uvicorn | 0.34+ | ASGI server |

### Dashboard
| Library | Version | Purpose |
|---------|---------|---------|
| Next.js | 16 | React framework + routing |
| React | 19 | UI rendering |
| TypeScript | 5.x | Type safety |
| Tailwind CSS | 4.x | Utility styling |
| Turbopack | — | Fast dev bundler |
| Node.js | 24 | JavaScript runtime |

### Sync Service (Day 9)
| Library | Purpose |
|---------|---------|
| Node.js | JS runtime |
| axios | Push inspections to cloud API |
| better-sqlite3 | Read local DB |
| dotenv | Config from .env |

---

## 12. How to Run (Quick Reference)

### Start everything (run from project root):
```powershell
.\run.ps1
```
This kills anything on ports 8000/8001/3001, then opens 3 separate windows.

### Or manually (3 terminals):

**Terminal 1 — AI Engine:**
```powershell
cd ai-engine
.\venv\Scripts\Activate.ps1
$env:AI_MODE = "simulation"
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

**Terminal 2 — Backend:**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 3 — Dashboard:**
```powershell
cd dashboard
npm run dev
```

### URLs:
- Dashboard: http://localhost:3001
- Backend API docs: http://localhost:8000/docs
- AI Engine docs: http://localhost:8001/docs

### Stop everything:
```powershell
.\scripts\stop_all.ps1
```

---

## 13. Day-by-Day Roadmap

| Day | Work | Outcome | Accuracy |
|-----|------|---------|----------|
| 1 | ✅ Skeleton + mock engine | 3 services running, DB saves | 0% (mock) |
| 2 | Dataset + first PatchCore model | 50 images sorted, augmented, trained | 50–65% |
| 3 | Real inference end-to-end | Swap AI_MODE=real, ONNX in pipeline | 55–65% |
| 4 | Threshold tuning | evaluate.py + tune_thresholds.py | 65–72% |
| 5 | Dashboard v2 | Image viewer, defect overlay, filters | same |
| 6 | Camera integration | OpenCV dual USB capture | same |
| 7 | Rotation tracking | Encoder reading, 360° check | same |
| 8 | EfficientNet classifier | Defect type identification | 72–82% |
| 9 | Cloud sync + offline packaging | Node.js sync, installer | same |
| 10 | Demo prep | Full dry run, client presentation | 80–88% |

---

## 14. Human Feedback Loop (Active Learning)

The system is designed to improve itself from corrections:

```
Inspector sees FAIL result  →  actually it's a PASS
         │
         ▼
Dashboard  POST /feedback  {predicted: "FAIL", actual: "PASS"}
         │
         ▼
backend saves to corrections table + image saved to saved_images/
         │
         ▼
python ai-engine/src/data_tools/apply_corrections.py
         │
         ▼
Image moved to data/reviewed/good/ (or defective/)
         │
         ▼
Re-run augment.py + train_anomaly.py  →  improved model
```

Every correction makes the next model more accurate for your specific cooler.

---

## 15. Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| AI approach | Anomaly detection (PatchCore) not classification | Only have good images — no defect labels needed |
| Model format | ONNX for production | No PyTorch at runtime, smaller, faster on CPU |
| Storage | SQLite | Zero setup, offline-first, works without internet |
| Mode switching | Single env var AI_MODE | Zero code changes to swap mock ↔ real model |
| Mock engine first | Full pipeline works before any model exists | Validate dashboard + DB + API on Day 1 |
| Decision engine separate | Pure Python, no ML | Rules change without touching model code |
| 2 cameras | Side-by-side 90° apart | Catch defects on any face of the cooler |
| 15° rotation steps | 24 angles × 2 cams = 48 frames | Enough coverage, fast enough (< 30 sec) |
| Offline-first | SQLite + local services | Factory floor may have no internet |
| Feedback loop | corrections table + apply_corrections.py | Model improves from real factory data |

---

## 16. What is NOT Built Yet

| Gap | Impact | Planned |
|-----|--------|---------|
| Real USB cameras | Demo uses simulation | Day 6 |
| Rotary encoder (COM3) | No real 360° tracking | Day 7 |
| EfficientNet classifier | Can't name which defect | Day 8 |
| Cloud sync service | Inspections stay local | Day 9 |
| Dashboard image viewer | Can't see what triggered FAIL | Day 5 |
| Blur check on live frames | Bad frames not rejected | Day 6 |
| Operator login | All show "unknown" | Day 9 |
| Thresholds tuned to real cooler | Unknown false positive rate | After Day 4 |
