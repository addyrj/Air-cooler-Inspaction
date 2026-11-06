"""
Run from ai-engine/:  python src/utils/inspect_dataset.py
Prints a summary table of images in data/reviewed/ so you can confirm the
dataset is ready before augmentation or training.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import cv2
import numpy as np
from pathlib import Path

ROOT = Path(__file__).parents[3] / "data" / "reviewed"
EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def _scan(folder: Path):
    files = [p for p in folder.rglob("*") if p.suffix.lower() in EXTS]
    if not files:
        return {"count": 0, "avg_w": 0, "avg_h": 0, "avg_bright": 0}
    widths, heights, brights = [], [], []
    for p in files:
        img = cv2.imread(str(p))
        if img is None:
            continue
        h, w = img.shape[:2]
        widths.append(w)
        heights.append(h)
        brights.append(float(np.mean(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))))
    return {
        "count": len(files),
        "avg_w": int(np.mean(widths)) if widths else 0,
        "avg_h": int(np.mean(heights)) if heights else 0,
        "avg_bright": round(float(np.mean(brights)), 1) if brights else 0,
    }


def main():
    if not ROOT.exists():
        print(f"ERROR: {ROOT} not found")
        return

    print(f"\nDataset report — {ROOT}\n")
    print(f"{'Folder':<40} {'Images':>7} {'Avg W':>7} {'Avg H':>7} {'Brightness':>10}")
    print("-" * 74)

    total = 0
    for folder in sorted(ROOT.rglob("*")):
        if not folder.is_dir():
            continue
        rel = folder.relative_to(ROOT)
        stats = _scan(folder)
        if stats["count"] == 0:
            continue
        total += stats["count"]
        print(
            f"{str(rel):<40} {stats['count']:>7} "
            f"{stats['avg_w']:>7} {stats['avg_h']:>7} "
            f"{stats['avg_bright']:>10}"
        )

    print("-" * 74)
    print(f"{'TOTAL':<40} {total:>7}")

    if total == 0:
        print("\n⚠  No images found. Copy cooler photos to data/reviewed/good/ first.")
    elif total < 10:
        print(f"\n⚠  Only {total} images. Aim for 10+ good images before training.")
    else:
        print(f"\n✓  Dataset looks ready. Run augment.py next.")


if __name__ == "__main__":
    main()
