# CREDENTIALS.md — All Credentials & New Laptop Setup Guide

**Project:** Air Cooler Inspection System
**Repo:** https://github.com/addyrj/Air-cooler-Inspaction
**Purpose:** Public learning project — no production secrets

---

## Credentials & Config Values

### GitHub
| Field | Value |
|-------|-------|
| Repo URL | https://github.com/addyrj/Air-cooler-Inspaction.git |
| Visibility | Public |
| Owner | addyrj |

### Ports (localhost)
| Service | Port | URL |
|---------|------|-----|
| Backend API | 8000 | http://localhost:8000 |
| AI Engine | 8001 | http://localhost:8001 |
| Dashboard | 3001 | http://localhost:3001 |

### Database
| Field | Value |
|-------|-------|
| Type | SQLite (file-based, no server) |
| File path | `backend\inspection.db` |
| Auto-created | Yes — on first backend start |
| Password | None |

### Hardware (when cameras are connected)
| Field | Value |
|-------|-------|
| Camera 1 index | 0 (first USB camera) |
| Camera 2 index | 1 (second USB camera) |
| Rotary encoder port | COM3 |
| Camera resolution | 1280 × 720 |

### AI Thresholds (`configs/settings.yaml`)
| Setting | Value | Meaning |
|---------|-------|---------|
| `anomaly_score_fail` | 0.65 | Anomaly score above this = FAIL |
| `anomaly_score_recheck` | 0.45 | Between 0.45–0.65 = RECHECK |
| `classify_min_confidence` | 0.60 | Classifier must be ≥ 60% confident |
| `blur_score_minimum` | 80.0 | Reject frames blurrier than this |
| `min_coverage_percent` | 90.0 | Must complete ≥ 90% rotation |

### Cloud Sync (future — not active yet)
| Field | Value |
|-------|-------|
| Cloud URL | https://your-cloud-server.com |
| Auth token | not set yet |
| Interval | 60 seconds |

---

## New Laptop Setup — Step by Step

### Requirements
- Windows 10/11
- Python 3.12 (https://python.org/downloads)
- Node.js 20+ (https://nodejs.org)
- Git (https://git-scm.com)

---

### Step 1 — Clone the repo

```powershell
cd $HOME\Desktop
git clone https://github.com/addyrj/Air-cooler-Inspaction.git air-cooler-inspection
cd air-cooler-inspection
```

---

### Step 2 — Set up AI Engine venv

```powershell
cd ai-engine
python -m venv venv
.\venv\Scripts\Activate.ps1

pip install fastapi uvicorn opencv-python numpy pillow
pip install pyserial imagehash scikit-learn
pip install anomalib==1.1.0
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install onnx onnxruntime

cd ..
```

> Note: `torch` install takes 5–10 minutes on first run. Use the `--index-url` flag shown above — without it you get the CUDA version (2 GB).

---

### Step 3 — Set up Backend venv

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1

pip install fastapi uvicorn sqlalchemy pydantic httpx python-multipart aiofiles

cd ..
```

---

### Step 4 — Set up Dashboard

```powershell
cd dashboard
npm install
cd ..
```

---

### Step 5 — Run the project

```powershell
# From project root (air-cooler-inspection folder):
.\run.ps1
```

This opens 3 separate PowerShell windows and starts:
- AI Engine on http://localhost:8001
- Backend on http://localhost:8000
- Dashboard on http://localhost:3001

Wait 10–15 seconds, then open http://localhost:3001 in your browser.

---

### Step 6 — Test it works

1. Open http://localhost:3001
2. Type any serial number e.g. `COOL-001`
3. Click **Start Inspection**
4. You should see PASS, FAIL, or RECHECK within a few seconds
5. The result saves automatically to `backend\inspection.db`

Check health endpoints:
- http://localhost:8000/health — should show `"status": "running"`
- http://localhost:8001/health — should show AI engine status
- http://localhost:8000/docs — interactive API docs (Swagger UI)

---

### Step 7 — Train a real model (when you have images)

Sort your cooler images into:
```
data\reviewed\good\           ← 40+ good cooler images
data\reviewed\defective\missing_knob\   ← 3–5 images
data\reviewed\defective\broken_grill\   ← 3–5 images
```

Then run (in ai-engine venv):
```powershell
.\ai-engine\venv\Scripts\Activate.ps1

# Check dataset
python ai-engine\src\utils\inspect_dataset.py

# Augment (~40 images → ~280)
python ai-engine\src\data_tools\augment.py

# Train PatchCore (~10–20 min on CPU)
python ai-engine\src\train_anomaly.py
```

Switch to real model by changing the env var in `run.ps1` from `simulation` to `real`:
```powershell
# In run.ps1, change:
$env:AI_MODE='simulation'
# to:
$env:AI_MODE='real'
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `.\venv\Scripts\Activate.ps1` blocked | Run: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Port already in use | Run `.\run.ps1` — it clears ports automatically |
| Dashboard blank / API error | Make sure backend (8000) and AI engine (8001) are running first |
| `torch` install fails | Use the `--index-url` flag for CPU version (see Step 2) |
| `anomalib` version error | Pin version: `pip install anomalib==1.1.0` |
| No model found (AI_MODE=real) | Run `train_anomaly.py` first, or set `AI_MODE=simulation` |
| Camera not found | Check camera index in `configs/settings.yaml` (try 0 and 1) |
| COM3 not found | Change `encoder_port` in `configs/settings.yaml` to your COM port |

---

## Project Contact

- GitHub: https://github.com/addyrj
- Email: addyrj20@gmail.com
