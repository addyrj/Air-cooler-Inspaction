"""Full inspection pipeline — simulated until cameras arrive."""
import os
from pathlib import Path
from typing import List, Dict

from src.inference.mock_engine import MockInferenceEngine
from src.decision.engine import DecisionEngine

_ROOT = Path(__file__).parents[3]   # air-cooler-inspection/
_CKPT_PATH  = (
    _ROOT / "models" / "active" / "lightning" /
    "Patchcore" / "cooler" / "v0" / "weights" / "lightning" / "model.ckpt"
)
_MODEL_PATH = _ROOT / "models" / "active" / "model.onnx"


def _build_engine(mode: str):
    if mode == "real":
        # Prefer PyTorch checkpoint (memory bank intact)
        if _CKPT_PATH.exists():
            try:
                from src.inference.torch_engine import TorchInferenceEngine
                return TorchInferenceEngine()
            except Exception as e:
                print(f"WARNING: TorchInferenceEngine failed ({e}). Trying ONNX...")
        # Fallback: ONNX
        if _MODEL_PATH.exists():
            try:
                from src.inference.engine import RealInferenceEngine
                return RealInferenceEngine()
            except Exception as e:
                print(f"WARNING: RealInferenceEngine failed ({e}). Using mock.")
        else:
            print(f"WARNING: AI_MODE=real but no model found. Run src/train_anomaly.py first.")
    return MockInferenceEngine()


class InspectionRunner:
    def __init__(self):
        self.mode = os.getenv("AI_MODE", "simulation")
        self.inference = _build_engine(self.mode)
        self.decision = DecisionEngine({
            "min_coverage_percent": 90.0,
            "classify_min_confidence": 0.60,
            "anomaly_score_fail": 0.65,
            "anomaly_score_recheck": 0.45,
        })

    def run(self, inspection_id: int, cooler_serial: str) -> dict:
        print(f"Inspection #{inspection_id} for {cooler_serial}")
        total_degrees, step = 360.0, 15.0
        angles = [i * step for i in range(int(total_degrees / step))]

        defects: List[Dict] = []
        recheck_count = 0
        frames_analysed = 0

        for angle in angles:
            for cam_id in (1, 2):
                result = self.inference.analyse(camera_id=cam_id, angle=angle)
                frames_analysed += 1
                if result["recheck"]:
                    recheck_count += 1
                elif result["is_defective"]:
                    defects.append({
                        "camera_id": cam_id,
                        "angle": angle,
                        "type": result["defect_type"],
                        "anomaly_score": result["anomaly_score"],
                        "confidence": result["confidence"],
                        "image_path": None,
                    })

        decision = self.decision.decide(
            rotation_completed=360.0,
            camera1_ok=True,
            camera2_ok=True,
            defects_found=defects,
            frames_analysed=frames_analysed,
            recheck_frames=recheck_count,
        )
        print(f"Result: {decision.result} "
              f"({len(defects)} defects, {frames_analysed} frames)")

        return {
            "inspection_id": inspection_id,
            "cooler_serial": cooler_serial,
            "result": decision.result,
            "defects": defects,
            "rotation_completed": 360.0,
            "frames_captured": frames_analysed,
            "frames_analysed": frames_analysed,
            "fail_reasons": decision.fail_reasons,
            "explanation": decision.explanation,
        }

    def analyse_image(self, image_bgr) -> dict:
        """Analyse a single uploaded image and return result + heatmap."""
        return self.inference.analyse_image(image_bgr)
