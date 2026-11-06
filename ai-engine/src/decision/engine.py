"""PASS / FAIL / RECHECK logic."""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class InspectionDecision:
    result: str
    fail_reasons: List[str]
    warnings: List[str]
    confidence: float
    explanation: str


class DecisionEngine:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.min_coverage = self.config.get("min_coverage_percent", 90.0)
        self.min_confidence = self.config.get("classify_min_confidence", 0.60)
        self.anomaly_fail = self.config.get("anomaly_score_fail", 0.65)
        self.anomaly_recheck = self.config.get("anomaly_score_recheck", 0.45)
        self.critical_components = [
            "pump_knob", "speed_knob", "fan_assembly",
            "fan_grill", "electric_cable",
        ]

    def decide(
        self,
        rotation_completed: float,
        camera1_ok: bool,
        camera2_ok: bool,
        defects_found: List[dict],
        frames_analysed: int,
        recheck_frames: int,
        missing_components: Optional[List[str]] = None,
    ) -> InspectionDecision:

        fail_reasons, warnings = [], []
        coverage_pct = (rotation_completed / 360.0) * 100

        if coverage_pct < self.min_coverage:
            return InspectionDecision(
                "RECHECK", [],
                [f"Only {coverage_pct:.0f}% coverage"],
                0.0,
                f"Incomplete rotation: {rotation_completed:.0f}/360",
            )

        if not camera1_ok and not camera2_ok:
            return InspectionDecision(
                "RECHECK", [], ["Both cameras failed"], 0.0,
                "Camera hardware problem",
            )
        if not camera1_ok:
            warnings.append("Camera 1 failed")
        if not camera2_ok:
            warnings.append("Camera 2 failed")

        if frames_analysed < 10:
            return InspectionDecision(
                "RECHECK", [],
                [f"Only {frames_analysed} frames analysed"], 0.0,
                "Too few frames",
            )

        if missing_components:
            for c in missing_components:
                if c in self.critical_components:
                    fail_reasons.append(f"missing_{c}")

        low_conf = []
        for d in defects_found:
            d_type = d.get("type", "unknown")
            conf = d.get("confidence", 0.0)
            score = d.get("anomaly_score", 0.0)
            if score >= self.anomaly_fail:
                if conf >= self.min_confidence:
                    fail_reasons.append(d_type)
                else:
                    low_conf.append(d_type)
                    warnings.append(f"Possible {d_type} (conf {conf:.0%})")
            elif score >= self.anomaly_recheck:
                low_conf.append(d_type)
                warnings.append(f"Anomaly {d_type} (score {score:.2f})")

        if recheck_frames / max(frames_analysed, 1) > 0.3:
            warnings.append(f"{recheck_frames}/{frames_analysed} need review")

        if fail_reasons:
            return InspectionDecision(
                "FAIL", fail_reasons, warnings,
                self._avg_conf(defects_found),
                f"FAIL: {', '.join(fail_reasons)}",
            )
        if low_conf or warnings:
            return InspectionDecision(
                "RECHECK", [], warnings,
                self._avg_conf(defects_found),
                f"RECHECK: {'; '.join(warnings)}",
            )
        return InspectionDecision(
            "PASS", [], [], 0.95,
            f"PASS: {frames_analysed} frames clean, full rotation",
        )

    def _avg_conf(self, defects):
        if not defects:
            return 0.0
        return sum(d.get("confidence", 0) for d in defects) / len(defects)
