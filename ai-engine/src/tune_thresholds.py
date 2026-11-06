"""
Find the best PASS/FAIL anomaly score threshold for your dataset.

Usage:
    python src/tune_thresholds.py

Prints a table of threshold vs. accuracy and recommends the best one.
Set the recommended threshold in ai-engine/src/inference/engine.py FAIL_THRESHOLD.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "ai-engine"))

MODEL_PATH = ROOT / "models" / "active" / "model.onnx"
GOOD_DIR   = ROOT / "data" / "reviewed" / "good"
DEFECT_DIR = ROOT / "data" / "reviewed" / "defective"


def collect_scores():
    try:
        import cv2
        from src.inference.engine import RealInferenceEngine
    except ImportError as e:
        print(f"ERROR: {e}")
        return [], []

    engine = RealInferenceEngine()
    good_scores, bad_scores = [], []

    good_images = list(GOOD_DIR.glob("*.jpg")) + list(GOOD_DIR.glob("*.png"))
    print(f"Scoring {len(good_images)} good images...")
    for p in good_images:
        import cv2 as _cv2
        img = _cv2.imread(str(p))
        if img is not None:
            r = engine.analyse_image(img)
            good_scores.append(r.get("anomaly_score", 0))

    defect_images = []
    if DEFECT_DIR.exists():
        for sub in DEFECT_DIR.iterdir():
            if sub.is_dir():
                defect_images.extend(sub.glob("*.jpg"))
                defect_images.extend(sub.glob("*.png"))
    print(f"Scoring {len(defect_images)} defective images...")
    for p in defect_images:
        import cv2 as _cv2
        img = _cv2.imread(str(p))
        if img is not None:
            r = engine.analyse_image(img)
            bad_scores.append(r.get("anomaly_score", 0))

    return good_scores, bad_scores


def tune():
    if not MODEL_PATH.exists():
        print(f"ERROR: No model at {MODEL_PATH}")
        return

    good_scores, bad_scores = collect_scores()

    if not good_scores and not bad_scores:
        print("No images found.")
        return

    all_scores = good_scores + bad_scores
    min_s, max_s = min(all_scores), max(all_scores)
    step = (max_s - min_s) / 20 if max_s > min_s else 0.05

    print(f"\nScore range: {min_s:.3f} — {max_s:.3f}")
    print(f"\n{'Threshold':>10}  {'Accuracy':>10}  {'FP':>6}  {'FN':>6}  {'Note'}")
    print("-" * 55)

    best_acc, best_thresh = 0, 0.5
    for i in range(21):
        thresh = min_s + i * step
        fp = sum(1 for s in good_scores if s >= thresh)
        fn = sum(1 for s in bad_scores if s < thresh)
        tp = len(bad_scores) - fn
        tn = len(good_scores) - fp
        total = len(good_scores) + len(bad_scores)
        acc = (tp + tn) / total * 100 if total else 0
        note = " ← best" if acc > best_acc else ""
        if acc > best_acc:
            best_acc = acc
            best_thresh = thresh
        print(f"{thresh:>10.3f}  {acc:>9.1f}%  {fp:>6}  {fn:>6}{note}")

    print(f"\nRecommended threshold: {best_thresh:.3f}  (accuracy {best_acc:.1f}%)")
    print(f"\nTo apply, edit ai-engine/src/inference/engine.py:")
    print(f"  FAIL_THRESHOLD = {best_thresh:.3f}")

    if good_scores:
        avg_g = sum(good_scores) / len(good_scores)
        print(f"\nGood image  avg score: {avg_g:.3f}  (range {min(good_scores):.3f}–{max(good_scores):.3f})")
    if bad_scores:
        avg_b = sum(bad_scores) / len(bad_scores)
        print(f"Defect image avg score: {avg_b:.3f}  (range {min(bad_scores):.3f}–{max(bad_scores):.3f})")

    if good_scores and bad_scores:
        overlap = sum(1 for s in good_scores if s >= min(bad_scores))
        if overlap:
            print(f"\nWARNING: {overlap} good images score above the lowest defect score — classes overlap.")
            print("Consider adding more defective examples or using a 2-stage classifier.")


if __name__ == "__main__":
    tune()
