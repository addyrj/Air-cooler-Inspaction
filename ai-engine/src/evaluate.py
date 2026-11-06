"""
Measure model accuracy on the reviewed dataset.

Usage (after training with AI_MODE=real and model in models/active/model.onnx):
    python src/evaluate.py

Prints per-class results and overall accuracy.
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "ai-engine"))

MODEL_PATH = ROOT / "models" / "active" / "model.onnx"
GOOD_DIR   = ROOT / "data" / "reviewed" / "good"
DEFECT_DIR = ROOT / "data" / "reviewed" / "defective"


def evaluate():
    if not MODEL_PATH.exists():
        print(f"ERROR: No model at {MODEL_PATH}")
        print("Train first: python src/train_anomaly.py")
        return

    try:
        import cv2
        import numpy as np
        from src.inference.engine import RealInferenceEngine
    except ImportError as e:
        print(f"ERROR: {e}")
        return

    engine = RealInferenceEngine()

    results = {"TP": 0, "TN": 0, "FP": 0, "FN": 0}
    errors = []

    good_images = list(GOOD_DIR.glob("*.jpg")) + list(GOOD_DIR.glob("*.png"))
    print(f"\nEvaluating {len(good_images)} GOOD images...")
    for img_path in good_images:
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        r = engine.analyse_image(img)
        if r.get("result") == "PASS":
            results["TN"] += 1
        else:
            results["FP"] += 1
            errors.append(f"  FALSE POSITIVE: {img_path.name} (score={r.get('anomaly_score', '?'):.3f})")

    defect_images = []
    if DEFECT_DIR.exists():
        for sub in DEFECT_DIR.iterdir():
            if sub.is_dir():
                defect_images.extend(sub.glob("*.jpg"))
                defect_images.extend(sub.glob("*.png"))

    print(f"Evaluating {len(defect_images)} DEFECTIVE images...")
    for img_path in defect_images:
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        r = engine.analyse_image(img)
        if r.get("result") in ("FAIL", "RECHECK"):
            results["TP"] += 1
        else:
            results["FN"] += 1
            errors.append(f"  FALSE NEGATIVE: {img_path.name} (score={r.get('anomaly_score', '?'):.3f})")

    total = sum(results.values())
    correct = results["TP"] + results["TN"]
    accuracy = correct / total * 100 if total else 0

    tp, tn, fp, fn = results["TP"], results["TN"], results["FP"], results["FN"]
    precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
    recall    = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"\n{'='*50}")
    print(f"  Total images : {total}")
    print(f"  Correct      : {correct}")
    print(f"  Accuracy     : {accuracy:.1f}%")
    print(f"  Precision    : {precision:.1f}%  (of predicted defects, how many were real)")
    print(f"  Recall       : {recall:.1f}%   (of real defects, how many were caught)")
    print(f"  F1 Score     : {f1:.1f}%")
    print(f"{'='*50}")
    print(f"  True Positives  (defect caught)  : {tp}")
    print(f"  True Negatives  (good accepted)  : {tn}")
    print(f"  False Positives (good rejected)  : {fp}  ← wrongly failed good cooler")
    print(f"  False Negatives (defect missed)  : {fn}  ← missed defect")
    print(f"{'='*50}")

    if errors:
        print(f"\nMisclassified images ({len(errors)}):")
        for e in errors:
            print(e)
        print("\nTip: run python src/tune_thresholds.py to adjust PASS/FAIL thresholds.")
    else:
        print("\nPerfect score on current dataset!")


if __name__ == "__main__":
    evaluate()
