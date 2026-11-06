"""
PyTorch-based inference engine — loads directly from the anomalib checkpoint.
Used when ONNX export can't capture the PatchCore memory bank properly.
"""
import numpy as np
import cv2
from pathlib import Path

ROOT       = Path(__file__).parents[3]
CKPT_PATH  = (
    ROOT / "models" / "active" / "lightning" /
    "Patchcore" / "cooler" / "v0" / "weights" / "lightning" / "model.ckpt"
)

# With only good images in training:
#   score ~0.0–1.0 = within normal range (PASS)
#   score ~1.0–1.15 = slightly outside range (RECHECK)
#   score >1.15 = clearly anomalous (FAIL)
FAIL_THRESHOLD    = 1.15
RECHECK_THRESHOLD = 1.00
INPUT_SIZE        = (256, 256)


def _preprocess(image_bgr: np.ndarray) -> "torch.Tensor":
    import torch
    img = cv2.resize(image_bgr, INPUT_SIZE)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], np.float32)
    std  = np.array([0.229, 0.224, 0.225], np.float32)
    img  = (img - mean) / std
    tensor = torch.from_numpy(img.transpose(2, 0, 1)).unsqueeze(0)
    return tensor


def _anomaly_map_to_heatmap_b64(image_bgr, amap_np, score):
    try:
        import base64
        h, w = image_bgr.shape[:2]
        amap = (amap_np - amap_np.min()) / (amap_np.max() - amap_np.min() + 1e-8)
        amap_u8 = cv2.resize((amap * 255).astype(np.uint8), (w, h))
        colored = cv2.applyColorMap(amap_u8, cv2.COLORMAP_JET)
        alpha = min(score * 0.7, 0.65)
        blended = cv2.addWeighted(image_bgr, 1 - alpha, colored, alpha, 0)
        peak_idx = np.unravel_index(np.argmax(amap_u8), amap_u8.shape)
        py, px = int(peak_idx[0]), int(peak_idx[1])
        cv2.circle(blended, (px, py), 14, (0, 0, 255), 3)
        cv2.circle(blended, (px, py), 5,  (255, 255, 255), -1)
        _, buf = cv2.imencode(".jpg", blended, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()
    except Exception:
        return ""


def _region_label(cx_frac, cy_frac):
    col = "left" if cx_frac < 0.35 else ("right" if cx_frac > 0.65 else "center")
    row = "top"  if cy_frac < 0.35 else ("bottom" if cy_frac > 0.65 else "middle")
    return f"{row}-{col}"


class TorchInferenceEngine:
    """Runs PatchCore inference using the anomalib PyTorch checkpoint."""

    def __init__(self, ckpt_path: str = None):
        import torch
        from anomalib.models import Patchcore

        path = Path(ckpt_path) if ckpt_path else CKPT_PATH
        if not path.exists():
            raise FileNotFoundError(
                f"Checkpoint not found: {path}\n"
                "Run: python src/train_anomaly.py"
            )
        print(f"TorchInferenceEngine: loading {path.name} ...")
        self._model = Patchcore.load_from_checkpoint(str(path))
        self._model.eval()
        mb = getattr(self._model.model, 'memory_bank', None)
        print(f"  Memory bank: {mb.shape if mb is not None else 'NOT FOUND'}")

    def _run(self, image_bgr):
        import torch
        tensor = _preprocess(image_bgr)

        # Use model.model() to get RAW (unnormalized) anomaly scores.
        # model() applies normalization that collapses all scores to 1.0 when
        # trained without defective images. Raw scores are reliable distances.
        with torch.no_grad():
            raw_out = self._model.model(tensor)

        # Anomaly map: shape (1, 1, H, W) or (1, H, W)
        if hasattr(raw_out, 'anomaly_map') and raw_out.anomaly_map is not None:
            amap_t = raw_out.anomaly_map
            if amap_t.ndim == 4:
                amap = amap_t[0, 0].cpu().numpy()
            else:
                amap = amap_t[0].cpu().numpy()
            raw_score = float(amap.max())
        elif hasattr(raw_out, 'pred_score') and raw_out.pred_score is not None:
            raw_score = float(raw_out.pred_score[0])
            amap = None
        else:
            raw_score = 0.5
            amap = None

        # Normalize using training distribution stats stored in post_processor
        pp = self._model.post_processor
        img_min = float(getattr(pp, 'image_min', 0.0))
        img_max = float(getattr(pp, 'image_max', 1.0))
        # Score 0.0 = best good image, 1.0 = worst good image,  >1.0 = anomalous
        if img_max > img_min:
            score = (raw_score - img_min) / (img_max - img_min)
        else:
            score = raw_score
        # Clip to [0, 1.5] so values above training max are visible (not clamped to 1.0)
        score = float(np.clip(score, 0.0, 1.5))
        # Normalize anomaly map the same way
        if amap is not None:
            pix_min = float(getattr(pp, 'pixel_min', 0.0))
            pix_max = float(getattr(pp, 'pixel_max', 1.0))
            if pix_max > pix_min:
                amap = (amap - pix_min) / (pix_max - pix_min)
            amap = np.clip(amap, 0.0, 1.5)
        return score, amap

    def analyse(self, image_bgr=None, camera_id: int = 1, angle: float = 0.0) -> dict:
        if image_bgr is None:
            return {
                "is_defective": False, "anomaly_score": 0.0,
                "defect_type": None,   "confidence": 0.0,
                "recheck": False,      "reason": "no_image",
            }
        score, _ = self._run(image_bgr)
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
        if image_bgr is None:
            return {"result": "RECHECK", "anomaly_score": 0.0,
                    "explanation": "No image", "heatmap_b64": "", "mode": "real"}

        score, amap = self._run(image_bgr)

        is_defective = score >= FAIL_THRESHOLD
        is_recheck   = RECHECK_THRESHOLD <= score < FAIL_THRESHOLD

        if amap is not None:
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
            explanation = f"Low-confidence anomaly in {region} — manual check needed"
        else:
            result = "PASS"
            explanation = f"No anomalies detected (score {score:.2f})"

        heatmap_b64 = _anomaly_map_to_heatmap_b64(image_bgr, amap, score) if amap is not None else ""

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
