"""AI Engine — runs on port 8001."""
from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from src.pipeline.inspection_runner import InspectionRunner

app = FastAPI(title="AI Engine", version="1.0.0")
runner: Optional[InspectionRunner] = None


@app.on_event("startup")
async def startup():
    global runner
    runner = InspectionRunner()
    print("AI Engine ready at http://localhost:8001")


class InspectRequest(BaseModel):
    inspection_id: int
    cooler_serial: str


@app.get("/health")
async def health():
    return {
        "status": "ready" if runner else "not_ready",
        "mode": runner.mode if runner else "unknown",
    }


@app.post("/inspect")
async def inspect(req: InspectRequest):
    return runner.run(
        inspection_id=req.inspection_id,
        cooler_serial=req.cooler_serial,
    )


@app.post("/analyse-image")
async def analyse_image(file: UploadFile = File(...)):
    if not runner:
        raise HTTPException(503, "AI engine not ready")
    contents = await file.read()
    try:
        import cv2
        arr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(400, "Could not decode image")
    except Exception as e:
        raise HTTPException(400, f"Image error: {e}")
    return runner.analyse_image(img)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
