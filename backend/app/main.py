"""FastAPI backend — bridges dashboard <-> AI engine <-> DB."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import datetime
from pathlib import Path
import httpx
import uuid as uuid_module

from app.database.models import (
    get_db, create_tables,
    Cooler, Inspection, Defect, SensorReading, Correction,
)

SAVED_IMAGES_DIR = Path(__file__).parents[1] / "saved_images"
SAVED_IMAGES_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="Air Cooler Inspection API",
    description="Brize Glacier 110 — local inspection",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AI_ENGINE_URL = os.getenv("AI_ENGINE_URL", "http://localhost:8001")


@app.on_event("startup")
async def startup():
    create_tables()
    print("Backend ready at http://localhost:8000")
    print("Docs at        http://localhost:8000/docs")


class StartInspectionRequest(BaseModel):
    cooler_serial: str
    operator_id: Optional[str] = "unknown"
    model: Optional[str] = "Brize Glacier 110"


@app.get("/health")
async def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    ai_status = "not_running"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{AI_ENGINE_URL}/health")
            ai_status = "ready" if r.status_code == 200 else "error"
    except Exception:
        pass

    return {
        "status": "running",
        "database": db_status,
        "ai_engine": ai_status,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "offline_capable": True,
    }


@app.post("/inspection/start")
async def start_inspection(
    data: StartInspectionRequest,
    db: Session = Depends(get_db),
):
    cooler = db.query(Cooler).filter(
        Cooler.serial_no == data.cooler_serial
    ).first()
    if not cooler:
        cooler = Cooler(serial_no=data.cooler_serial, model=data.model)
        db.add(cooler)
        db.commit()
        db.refresh(cooler)

    inspection = Inspection(
        cooler_id=cooler.id,
        result="IN_PROGRESS",
        operator_id=data.operator_id,
        started_at=datetime.utcnow(),
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{AI_ENGINE_URL}/inspect",
                json={
                    "inspection_id": inspection.id,
                    "cooler_serial": data.cooler_serial,
                },
            )
        ai_result = resp.json()
    except httpx.ConnectError:
        inspection.result = "RECHECK"
        inspection.fail_reasons = ["ai_engine_not_running"]
        inspection.completed_at = datetime.utcnow()
        db.commit()
        raise HTTPException(
            503,
            "AI engine not running. Start it: "
            "cd ai-engine; .\venv\Scripts\Activate.ps1; python main.py",
        )

    inspection.result = ai_result.get("result", "RECHECK")
    inspection.rotation_completed = ai_result.get("rotation_completed", 0)
    inspection.frames_captured = ai_result.get("frames_captured", 0)
    inspection.frames_analysed = ai_result.get("frames_analysed", 0)
    inspection.fail_reasons = ai_result.get("fail_reasons", [])
    inspection.completed_at = datetime.utcnow()
    inspection.duration_seconds = (
        inspection.completed_at - inspection.started_at
    ).total_seconds()

    for d in ai_result.get("defects", []):
        db.add(Defect(
            inspection_id=inspection.id,
            camera_id=d.get("camera_id"),
            rotation_angle=d.get("angle"),
            defect_type=d.get("type"),
            anomaly_score=d.get("anomaly_score"),
            confidence=d.get("confidence"),
            image_path=d.get("image_path"),
            bbox=d.get("bbox"),
        ))

    db.commit()
    db.refresh(inspection)

    defects = db.query(Defect).filter(
        Defect.inspection_id == inspection.id
    ).all()

    return {
        "inspection_id": inspection.id,
        "cooler_serial": data.cooler_serial,
        "result": inspection.result,
        "defects": [
            {
                "type": d.defect_type,
                "confidence": d.confidence,
                "camera": d.camera_id,
                "angle": d.rotation_angle,
                "image_path": d.image_path,
            }
            for d in defects
        ],
        "rotation_completed": inspection.rotation_completed,
        "duration_seconds": inspection.duration_seconds,
        "model_version": inspection.model_version,
        "fail_reasons": inspection.fail_reasons or [],
        "frames_analysed": inspection.frames_analysed,
    }


@app.get("/inspection/{inspection_id}")
async def get_inspection(inspection_id: int, db: Session = Depends(get_db)):
    inspection = db.query(Inspection).filter(
        Inspection.id == inspection_id
    ).first()
    if not inspection:
        raise HTTPException(404, "Inspection not found")

    cooler = db.query(Cooler).filter(
        Cooler.id == inspection.cooler_id
    ).first()
    defects = db.query(Defect).filter(
        Defect.inspection_id == inspection_id
    ).all()

    return {
        "id": inspection.id,
        "cooler_serial": cooler.serial_no if cooler else None,
        "result": inspection.result,
        "started_at": inspection.started_at,
        "completed_at": inspection.completed_at,
        "duration_seconds": inspection.duration_seconds,
        "rotation_completed": inspection.rotation_completed,
        "frames_analysed": inspection.frames_analysed,
        "fail_reasons": inspection.fail_reasons or [],
        "synced_cloud": inspection.synced_cloud,
        "defects": [
            {
                "type": d.defect_type,
                "confidence": d.confidence,
                "camera": d.camera_id,
                "angle": d.rotation_angle,
                "anomaly_score": d.anomaly_score,
                "image_path": d.image_path,
                "bbox": d.bbox,
            }
            for d in defects
        ],
    }


@app.get("/history")
async def get_history(
    limit: int = 50,
    offset: int = 0,
    result_filter: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Inspection, Cooler).join(
        Cooler, Cooler.id == Inspection.cooler_id
    )
    if result_filter:
        q = q.filter(Inspection.result == result_filter)
    total = q.count()
    rows = q.order_by(
        Inspection.started_at.desc()
    ).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": i.id,
                "cooler_serial": c.serial_no,
                "result": i.result,
                "started_at": i.started_at,
                "duration_seconds": i.duration_seconds,
                "model_version": i.model_version,
                "synced_cloud": i.synced_cloud,
                "rotation_completed": i.rotation_completed,
            }
            for i, c in rows
        ],
    }


@app.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Inspection.id)).scalar()
    passed = db.query(func.count(Inspection.id)).filter(
        Inspection.result == "PASS"
    ).scalar()
    failed = db.query(func.count(Inspection.id)).filter(
        Inspection.result == "FAIL"
    ).scalar()
    recheck = db.query(func.count(Inspection.id)).filter(
        Inspection.result == "RECHECK"
    ).scalar()
    unsynced = db.query(func.count(Inspection.id)).filter(
        Inspection.synced_cloud == False
    ).scalar()
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "recheck": recheck,
        "unsynced": unsynced,
        "pass_rate_percent": round(passed / total * 100, 1) if total else 0,
    }


@app.post("/analyse-image")
async def analyse_image(file: UploadFile = File(...)):
    """Forward uploaded image to AI engine; save image and return image_id for feedback."""
    contents = await file.read()
    image_id = str(uuid_module.uuid4())
    img_path = SAVED_IMAGES_DIR / f"{image_id}.jpg"
    img_path.write_bytes(contents)

    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            resp = await c.post(
                f"{AI_ENGINE_URL}/analyse-image",
                files={"file": (file.filename or "image.jpg", contents, file.content_type or "image/jpeg")},
            )
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, resp.text)
        data = resp.json()
        data["image_id"] = image_id
        return data
    except httpx.ConnectError:
        img_path.unlink(missing_ok=True)
        raise HTTPException(503, "AI engine not running on port 8001")


class FeedbackRequest(BaseModel):
    image_id: str
    predicted: str       # what the model said (PASS/FAIL/RECHECK)
    actual: str          # what it really is (PASS/FAIL)
    correct_type: Optional[str] = None   # correct defect type if model got it wrong
    anomaly_score: Optional[float] = None
    notes: Optional[str] = None


@app.post("/feedback")
async def submit_feedback(req: FeedbackRequest, db: Session = Depends(get_db)):
    """Record a human correction on a model prediction."""
    img_path = SAVED_IMAGES_DIR / f"{req.image_id}.jpg"
    correction = Correction(
        image_id=req.image_id,
        image_path=str(img_path) if img_path.exists() else None,
        predicted=req.predicted,
        actual=req.actual,
        correct_type=req.correct_type,
        anomaly_score=req.anomaly_score,
        notes=req.notes,
        applied=False,
    )
    db.add(correction)
    db.commit()
    db.refresh(correction)
    return {
        "id": correction.id,
        "image_id": correction.image_id,
        "message": "Feedback saved. Run apply_corrections.py to move image to training set.",
    }


@app.get("/corrections")
async def list_corrections(
    limit: int = 50,
    unapplied_only: bool = False,
    db: Session = Depends(get_db),
):
    """List all recorded corrections."""
    q = db.query(Correction)
    if unapplied_only:
        q = q.filter(Correction.applied == False)
    total = q.count()
    rows = q.order_by(Correction.created_at.desc()).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "image_id": r.image_id,
                "predicted": r.predicted,
                "actual": r.actual,
                "correct_type": r.correct_type,
                "anomaly_score": r.anomaly_score,
                "notes": r.notes,
                "applied": r.applied,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

