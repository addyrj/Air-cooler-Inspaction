"""
Real ONNX inference engine — drop-in replacement for MockInferenceEngine.
Works with anomalib 2.x exported PatchCore models.
"""
import numpy as np
import cv2
from pathlib import Path

MODEL_PATH = Path(__file__).parents[4] / "models" / "active" / "model.onnx"

FAIL_THRESHOLD    = 0.65
RECHECK_THRESHOLD = 0.45
INPUT_SIZE        = (256, 256)


def _load_session(path: str):
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 4
    opts.inter_op_num_threads = 2
    opts.log_severity_level = 3   # suppress INFO/WARNING from ort
    return ort.InferenceSession(str(path), sess_options=opts)


def _preprocess(image_bgr: np.ndarray) -> np.ndarray:
    img = cv2.resize(image_bgr, INPUT_SIZE)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], np.float32)
    std  = np.array([0.229, 0.224, 0.225], np.float32)
    img  = (img - mean) / std
    return img.transpose(2, 0, 1)[np.newaxis]  # (1, 3, H, W)


def _extract_score(outputs: list) -> float:
    """
    Handle different anomalib 2.x ONNX output shapes:
      - (1,)            → single image score already normalised
      - (1, 1, H, W)    → anomaly map → take max
      - (1, H, W)       → anomaly map → take max
    Returns float in [0, 1].
    """
    arr = np.array(outputs[0]).flatten()

    # If the model outputs multiple values, take the max (worst patch)
    raw = float(np.max(arr))

    # anomalib min-max normalises scores to [0,1] during export,
    # but raw patch distances can be large — clamp defensively.
    return float(np.clip(raw, 0.0, 1.0))


def _anomaly_map_to_heatmap_b64(image_bgr: np.ndarray, outputs: list, score: float) -> str:
    """Blend the PatchCore anomaly map onto the original image, return base64 JPEG."""
    try:
        import cv2, base64
        h, w = image_bgr.shape[:2]
        raw = np.array(outputs[0])

        if raw.size > 1:
            # Anomaly map — resize to image dimensions
            amap = raw.reshape(raw.shape[-2], raw.shape[-1]) if raw.ndim >= 2 else raw
            amap = (amap - amap.min()) / (amap.max() - amap.min() + 1e-8)
            amap_u8 = cv2.resize((amap * 255).astype(np.uint8), (w, h))
        else:
            # Scalar score — make a uniform map
            amap_u8 = np.full((h, w), int(score * 255), np.uint8)

        colored = cv2.applyColorMap(amap_u8, cv2.COLORMAP_JET)
        alpha = min(score * 0.7, 0.65)
        blended = cv2.addWeighted(image_bgr, 1 - alpha, colored, alpha, 0)

        # Mark peak location
        peak_idx = np.unravel_index(np.argmax(amap_u8), amap_u8.shape)
        py, px = int(peak_idx[0]), int(peak_idx[1])
        cv2.circle(blended, (px, py), 14, (0, 0, 255), 3)
        cv2.circle(blended, (px, py), 5,  (255, 255, 255), -1)

        _, buf = cv2.imencode(".jpg", blended, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()
    except Exception:
        return ""


def _region_label(cx_frac: float, cy_frac: float) -> str:
    col = "left" if cx_frac < 0.35 else ("right" if cx_frac > 0.65 else "center")
    row = "top"  if cy_frac < 0.35 else ("bottom" if cy_frac > 0.65 else "middle")
    return f"{row}-{col}"


class RealInferenceEngine:
    def __init__(self, model_path: str = None):
        path = model_path or str(MODEL_PATH)
        if not Path(path).exists():
            raise FileNotFoundError(
                f"ONNX model not found: {path}\n"
                "Run: python src/train_anomaly.py"
            )
        self._session      = _load_session(path)
        self._input_name   = self._session.get_inputs()[0].name
        self._output_names = [o.name for o in self._session.get_outputs()]
        print(f"RealInferenceEngine loaded: {Path(path).name} "
              f"({Path(path).stat().st_size // 1024} KB)")

    def analyse(self, image_bgr=None, camera_id: int = 1, angle: float = 0.0) -> dict:
        if image_bgr is None:
            return {
                "is_defective": False, "anomaly_score": 0.0,
                "defect_type": None,   "confidence": 0.0,
                "recheck": False,      "reason": "no_image",
            }

        tensor  = _preprocess(image_bgr)
        outputs = self._session.run(self._output_names, {self._input_name: tensor})
        score   = _extract_score(outputs)

        is_defective = score >= FAIL_THRESHOLD
        is_recheck   = RECHECK_THRESHOLD <= score < FAIL_THRESHOLD

        return {
            "is_defective": is_defective,
            "anomaly_score": round(score, 4),
            "defect_type":   "anomaly" if is_defective else None,
            "confidence":    round(score, 4) if is_defective else 0.0,
            "recheck":       is_recheck,
            "reason":        f"score={score:.3f} cam{camera_id} {angle:.0f}°",
        }

    def analyse_image(self, image_bgr) -> dict:
        """Single-image analysis with heatmap overlay. Used by /analyse-image endpoint."""
        if image_bgr is None:
            return {"result": "RECHECK", "anomaly_score": 0.0, "explanation": "No image",
                    "heatmap_b64": "", "mode": "real"}

        tensor  = _preprocess(image_bgr)
        outputs = self._session.run(self._output_names, {self._input_name: tensor})
        score   = _extract_score(outputs)

        is_defective = score >= FAIL_THRESHOLD
        is_recheck   = RECHECK_THRESHOLD <= score < FAIL_THRESHOLD

        # Find peak anomaly location (for region label)
        raw = np.array(outputs[0])
        if raw.size > 1:
            amap = raw.reshape(raw.shape[-2], raw.shape[-1]) if raw.ndim >= 2 else raw
            peak = np.unravel_index(np.argmax(amap), amap.shape)
            cx_frac = peak[1] / amap.shape[1]
            cy_frac = peak[0] / amap.shape[0]
        else:
            cx_frac, cy_frac = 0.5, 0.5

        region = _region_label(cx_frac, cy_frac)

        if is_defective:
            result = "FAIL"
            explanation = f"Anomaly detected in {region} region (score {score:.2f})"
        elif is_recheck:
            result = "RECHECK"
            explanation = f"Low-confidence anomaly in {region} region — manual check"
        else:
            result = "PASS"
            explanation = f"No anomalies detected (score {score:.2f})"

        heatmap_b64 = _anomaly_map_to_heatmap_b64(image_bgr, outputs, score)

        return {
            "result":        result,
            "anomaly_score": round(score, 4),
            "defect_type":   "anomaly" if is_defective else None,
            "confidence":    round(score, 4) if is_defective else 0.0,
            "component":     None,
            "location":      {"cx": round(cx_frac, 3), "cy": round(cy_frac, 3)},
            "explanation":   explanation,
            "heatmap_b64":   heatmap_b64,
            "mode":          "real",
        }
