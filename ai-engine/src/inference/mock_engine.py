"""Mock inference — returns realistic random results + synthetic heatmap."""
import random
import time
import base64
import numpy as np


# Approximate component locations (cx%, cy%, name) for front-view cooler
_COMPONENT_REGIONS = [
    (0.50, 0.30, "fan_grill"),
    (0.50, 0.40, "fan_assembly"),
    (0.50, 0.45, "motor_hub"),
    (0.35, 0.65, "pump_knob"),
    (0.65, 0.65, "speed_knob"),
    (0.50, 0.70, "control_panel"),
    (0.20, 0.85, "caster_wheel"),
    (0.80, 0.85, "caster_wheel"),
    (0.15, 0.50, "water_level_indicator"),
    (0.85, 0.20, "electric_cable"),
    (0.50, 0.10, "water_inlet_label"),
]


def _make_heatmap_b64(image_bgr, anomaly_score: float, cx: float, cy: float) -> str:
    """Overlay a gaussian heatmap blob on the image and return as base64 JPEG."""
    try:
        import cv2
        h, w = image_bgr.shape[:2]
        # Build float heatmap
        heat = np.zeros((h, w), dtype=np.float32)
        px, py = int(cx * w), int(cy * h)
        radius = max(40, int(min(w, h) * 0.18))
        y_grid, x_grid = np.ogrid[:h, :w]
        dist2 = (x_grid - px) ** 2 + (y_grid - py) ** 2
        heat = np.exp(-dist2 / (2 * (radius / 2) ** 2)).astype(np.float32)
        heat *= anomaly_score

        # Colormap: low→blue, high→red
        heat_u8 = (heat * 255).astype(np.uint8)
        colored = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)

        # Blend with original
        alpha = min(anomaly_score * 0.7, 0.6)
        blended = cv2.addWeighted(image_bgr, 1 - alpha, colored, alpha, 0)

        # Mark peak
        cv2.circle(blended, (px, py), 12, (0, 0, 255), 3)
        cv2.circle(blended, (px, py), 4,  (255, 255, 255), -1)

        _, buf = cv2.imencode(".jpg", blended, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()
    except Exception:
        return ""


class MockInferenceEngine:
    def analyse(self, image_bgr=None, camera_id: int = 1, angle: float = 0.0) -> dict:
        time.sleep(0.05)
        is_defective = random.random() < 0.08
        if not is_defective:
            return {
                "is_defective": False,
                "anomaly_score": round(random.uniform(0.1, 0.4), 3),
                "defect_type": None, "confidence": 0.0,
                "recheck": False, "reason": "OK",
            }
        defects = ["missing_knob", "broken_grill", "missing_wheel", "cable_damage"]
        return {
            "is_defective": True,
            "anomaly_score": round(random.uniform(0.55, 0.95), 3),
            "defect_type": random.choice(defects),
            "confidence":  round(random.uniform(0.65, 0.95), 3),
            "recheck": False,
            "reason": f"defect at {angle:.0f}deg cam{camera_id}",
        }

    def analyse_image(self, image_bgr) -> dict:
        """Single-image analysis with heatmap. Used by /analyse-image endpoint."""
        score = round(random.uniform(0.05, 0.98), 3)
        is_defective = score >= 0.65
        is_recheck   = 0.45 <= score < 0.65

        # Pick a random component location as defect origin
        comp = random.choice(_COMPONENT_REGIONS)
        cx, cy, comp_name = comp

        # Add small jitter
        cx = max(0.05, min(0.95, cx + random.uniform(-0.08, 0.08)))
        cy = max(0.05, min(0.95, cy + random.uniform(-0.08, 0.08)))

        if is_defective:
            result = "FAIL"
            defect_type  = f"missing_{comp_name}" if random.random() > 0.5 else "damaged_" + comp_name
            explanation  = f"Anomaly detected near {comp_name.replace('_', ' ')} (score {score:.2f})"
        elif is_recheck:
            result = "RECHECK"
            defect_type  = None
            explanation  = f"Low-confidence anomaly near {comp_name.replace('_', ' ')} — manual check needed"
        else:
            result = "PASS"
            defect_type  = None
            explanation  = "No anomalies detected"
            cx, cy = 0.5, 0.5   # heatmap not visible at low score

        heatmap_b64 = _make_heatmap_b64(image_bgr, score, cx, cy) if image_bgr is not None else ""

        return {
            "result":        result,
            "anomaly_score": score,
            "defect_type":   defect_type,
            "confidence":    score if is_defective else 0.0,
            "component":     comp_name if (is_defective or is_recheck) else None,
            "location":      {"cx": round(cx, 3), "cy": round(cy, 3)},
            "explanation":   explanation,
            "heatmap_b64":   heatmap_b64,
            "mode":          "simulation",
        }
