cd $HOME\Desktop\air-cooler-inspection

@'
# HOW.md — How This Project Works

**Project:** Air Cooler Inspection System
**Cooler:** Brize Glacier 110
**Stack:** Python + FastAPI + SQLite + Next.js + Node.js
**Goal:** Automated 360° visual inspection of air coolers with PASS / FAIL / RECHECK verdict

---

## 🎯 What This System Does

A cooler is placed on a rotating turntable. Two cameras capture images every 15° (24 angles × 2 cameras = 48 frames per inspection). The AI analyses each frame, detects missing components / defects, and returns one of:

| Result | Meaning |
|--------|---------|
| **PASS** | All frames clean, full rotation, no defects |
| **FAIL** | Defect found with high confidence |
| **RECHECK** | Ambiguous — human must review |

Every inspection is stored in SQLite, shown on the Next.js dashboard, and eventually synced to the cloud when internet is available.

---

## 🏗️ System Architecture (3 Services + 1 DB)


--- 

## 🛠️ Technologies Used

### Backend Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Web Framework | **FastAPI** | 0.162+ | REST API for inspections |
| ORM | **SQLAlchemy** | 2.1+ | SQLite database access |
| Database | **SQLite** | built-in | Offline-first storage |
| Data validation | **Pydantic** | 2.14+ | Request/response schemas |
| HTTP client | **httpx** | 0.28+ | Backend → AI Engine calls |
| Server | **Uvicorn** | 0.54+ | ASGI server |

### AI Engine Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Web Framework | FastAPI | AI service (port 8001) |
| Image I/O | **OpenCV** (`cv2`) | Read/write camera frames |
| Array math | **NumPy** | Image processing |
| Image format | **Pillow** | Convert between formats |
| ML framework | **PyTorch** | Load & run models |
| Vision models | **torchvision** | Pretrained backbones |
| Anomaly detection | **PatchCore** (via `anomalib`) | Learn "normal", flag anything else |
| Inference runtime | **ONNX Runtime** | Fast CPU inference in production |
| Serial comms | **pyserial** | Read rotary encoder |
| Hashing | **imagehash** | Duplicate detection |

### Frontend Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Framework | **Next.js 16** | React + SSR + routing |
| Language | **TypeScript** | Type-safe UI |
| Styling | **Tailwind CSS** | Utility-first classes |
| Bundler | **Turbopack** | Fast dev reload |
| Runtime | Node.js 24 | JS execution |

### Sync Service (planned)

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Runtime | **Node.js** | JS execution |
| HTTP | **axios** | Push to cloud |
| Database | **better-sqlite3** | Read local inspections |
| Env | **dotenv** | Config |

### Why these choices?

- **FastAPI** — you already know it, best-in-class async, auto OpenAPI docs
- **SQLite** — zero setup, offline-first, perfect for 10-day demo, easy to migrate to PostgreSQL later
- **PatchCore** — learns from *good* images only (no defect labels needed), which is exactly your situation with 3 images
- **ONNX Runtime** — deploy model without PyTorch bloat, works offline
- **Next.js** — you know it, ships production-ready UI in hours
- **Simulation mode first** — mock engine lets you build the full pipeline before any model exists

---

## 🔄 How an Inspection Runs (Step by Step)

### Current (Day 1 — Simulation)

1. User types `COOL-001` on dashboard, clicks **Start Inspection**
2. Dashboard `POST /inspection/start` → Backend
3. Backend creates `coolers` row (if new), `inspections` row with `result="IN_PROGRESS"`
4. Backend `POST /inspect` → AI Engine
5. AI Engine's `InspectionRunner.run()`:
   - Loops 24 angles (0° to 345°)
   - For each angle, runs `MockInferenceEngine` twice (cam 1 + cam 2)
   - Collects "defects" (8% random chance per frame)
   - Passes all results to `DecisionEngine.decide()`
6. `DecisionEngine` applies 6 rules (coverage, cameras, frames, missing components, defect confidence, recheck ratio)
7. Returns `PASS` / `FAIL` / `RECHECK` + defects list
8. Backend updates `inspections` row + inserts `defects` rows
9. Dashboard shows result + updates table

### Day 6+ (Real Cameras)

Same flow, but step 5 becomes:
- Turntable spins → encoder sends angle to AI Engine
- At every 15°, both USB cameras capture one frame each
- Frame → `blur_score()` → skip if < 50
- Frame → `InferenceEngine.analyse()` → anomaly score + defect type
- Same `DecisionEngine` decides

### Day 8+ (Real Trained Model)

Step 5 uses:
- `PatchCore` ONNX model → anomaly score (0.0 to 1.0)
- `EfficientNet` ONNX model → defect class + confidence
- Replaces `MockInferenceEngine`

No other service changes. That's the power of the modular design.

---

## 🗄️ Database Schema (SQLite)

### `coolers`
| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER PK | |
| serial_no | VARCHAR UNIQUE | e.g. COOL-001 |
| model | VARCHAR | "Brize Glacier 110" |
| created_at | DATETIME | |

### `inspections`
| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER PK | |
| cooler_id | INTEGER FK | |
| started_at | DATETIME | |
| completed_at | DATETIME | |
| result | VARCHAR | PASS/FAIL/RECHECK/IN_PROGRESS |
| rotation_completed | FLOAT | 0–360 |
| frames_analysed | INTEGER | usually 48 |
| fail_reasons | JSON | list of defect types |
| synced_cloud | BOOLEAN | false until synced |
| duration_seconds | FLOAT | |

### `defects`
| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER PK | |
| inspection_id | INTEGER FK | |
| camera_id | INTEGER | 1 or 2 |
| rotation_angle | FLOAT | 0–360 |
| defect_type | VARCHAR | "missing_knob" etc |
| anomaly_score | FLOAT | PatchCore score |
| confidence | FLOAT | Classifier confidence |
| image_path | VARCHAR | saved frame path |
| bbox | JSON | bounding box |

### `sensor_readings`
Reserved for water level, motor current, temperature sensors (Day 9+).

---

## 🧠 The Decision Engine (Most Important Logic)

`ai-engine/src/decision/engine.py` — apply rules in this order:

| Rule | Condition | Result |
|------|-----------|--------|
| 1 | Coverage < 90% | RECHECK — did not see full cooler |
| 2 | Both cameras failed | RECHECK — hardware problem |
| 3 | < 10 frames analysed | RECHECK — lighting/camera issue |
| 4 | Missing critical component | FAIL |
| 5a | Defect, anomaly ≥ 0.65, confidence ≥ 0.60 | FAIL |
| 5b | Defect, anomaly ≥ 0.65, confidence < 0.60 | RECHECK |
| 5c | Anomaly 0.45–0.65 | RECHECK |
| 6 | > 30% frames need recheck | RECHECK |
| Default | All checks pass | PASS |

**Never gives PASS if inspection incomplete.** This is critical for safety.

---

## 🎚️ Thresholds (in `configs/settings.yaml`)

| Name | Default | Meaning |
|------|---------|---------|
| `anomaly_score_fail` | 0.65 | Above → candidate defect |
| `anomaly_score_recheck` | 0.45 | Between this and fail → human review |
| `classify_min_confidence` | 0.60 | Classifier must be this sure |
| `min_coverage_percent` | 90.0 | Must rotate at least 324° |
| `blur_score_minimum` | 80.0 | Reject blurry frames |

Tune these after Day 8 when you have real accuracy data.

---

## 🚦 Operating Modes

The AI Engine has 2 modes controlled by `AI_MODE` env var:

| Mode | Uses | When |
|------|------|------|
| `simulation` | `MockInferenceEngine` | Day 1–7 (no model needed) |
| `production` | Real `InferenceEngine` (ONNX) | Day 8+ (real model) |

**Switch by changing one env var + restarting AI Engine.** No code changes.

---

## 🖥️ How to Run

### Every session (3 terminals)

**Terminal 1 — AI Engine:**
```powershell
cd $HOME\Desktop\air-cooler-inspection\ai-engine
.\venv\Scripts\Activate.ps1
$env:AI_MODE = "simulation"
python main.py

air-cooler-inspection/
│
├── ai-engine/ ← Python: cameras + AI models
│ ├── main.py ← FastAPI entry, port 8001
│ ├── requirements.txt
│ ├── venv/ ← virtual environment (Python 3.12)
│ └── src/
│ ├── camera/
│ │ ├── capture.py ← OpenCV single camera reader
│ │ ├── quality.py ← blur + brightness check
│ │ └── dual_capture.py ← 2 cameras simultaneously
│ ├── rotation/
│ │ └── encoder.py ← read turntable angle via serial
│ ├── inference/
│ │ ├── mock_engine.py ← placeholder (works without model)
│ │ ├── engine.py ← real ONNX inference
│ │ └── (future: classifier.py)
│ ├── decision/
│ │ └── engine.py ← PASS/FAIL/RECHECK rules
│ ├── pipeline/
│ │ └── inspection_runner.py ← orchestrates full inspection
│ └── utils/
│ ├── logger.py
│ └── inspect_dataset.py ← Day 2 dataset inspector
│
├── backend/ ← Python: FastAPI + SQLite
│ ├── app/
│ │ ├── main.py ← FastAPI entry, port 8000
│ │ ├── database/
│ │ │ └── models.py ← SQLAlchemy tables
│ │ └── schemas/
│ │ └── inspection.py ← (future) Pydantic schemas
│ ├── inspection.db ← SQLite file (auto-created)
│ ├── requirements.txt
│ └── venv/
│
├── dashboard/ ← Next.js: UI
│ ├── app/
│ │ ├── page.tsx ← main dashboard
│ │ └── layout.tsx
│ ├── package.json
│ └── (runs on port 3001)
│
├── sync-service/ ← Node.js: cloud sync (future)
│ ├── src/
│ │ └── sync.js
│ └── package.json
│
├── data/
│ ├── raw/ ← 3 original cooler images
│ ├── reviewed/
│ │ ├── good/ ← confirmed working coolers
│ │ └── defective/ ← known defects (future)
│ ├── augmented/ ← after augmentation (Day 4)
│ └── test_inspection/ ← test images for simulation
│
├── models/
│ └── active/ ← trained ONNX models
│
├── saved_images/ ← defect evidence (future)
├── logs/
│ └── inspection.log
│
├── configs/
│ └── settings.yaml ← thresholds, ports, paths
│
├── scripts/
│ ├── start_all.ps1 ← launch 3 services
│ └── stop_all.ps1
│
├── HOW.md ← this file
├── NEXT_CHALLENGE.md ← roadmap
└── README.md
