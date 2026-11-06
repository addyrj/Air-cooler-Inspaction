"""
Run from ai-engine/:  python src/data_tools/augment.py
Reads every image from data/reviewed/<subfolder>/ and writes 6 augmented
variants into data/augmented/<subfolder>/.  Originals are also copied.
Total output: ~7× the input count per folder.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import cv2
import numpy as np
import shutil
from pathlib import Path

REVIEWED = Path(__file__).parents[3] / "data" / "reviewed"
AUGMENTED = Path(__file__).parents[3] / "data" / "augmented"
EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def _rotate(img, angle):
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)


def augment_folder(src: Path, dst: Path) -> int:
    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for p in sorted(src.iterdir()):
        if p.suffix.lower() not in EXTS:
            continue
        img = cv2.imread(str(p))
        if img is None:
            print(f"  skip (unreadable): {p.name}")
            continue
        shutil.copy(p, dst / p.name)
        count += 1
        variants = [
            ("flip",   cv2.flip(img, 1)),
            ("dark",   np.clip(img.astype(np.float32) * 0.75, 0, 255).astype(np.uint8)),
            ("bright", np.clip(img.astype(np.float32) * 1.25, 0, 255).astype(np.uint8)),
            ("blur",   cv2.GaussianBlur(img, (5, 5), 0)),
            ("rot_m8", _rotate(img, -8)),
            ("rot_p8", _rotate(img, 8)),
        ]
        for tag, variant in variants:
            out_name = f"{p.stem}_{tag}{p.suffix}"
            cv2.imwrite(str(dst / out_name), variant)
            count += 1
    return count


def main():
    if not REVIEWED.exists():
        print(f"ERROR: {REVIEWED} not found")
        return

    print(f"\nAugmenting from: {REVIEWED}")
    print(f"Writing to:      {AUGMENTED}\n")

    total = 0
    found_any = False
    for src_folder in sorted(REVIEWED.rglob("*")):
        if not src_folder.is_dir():
            continue
        images = [p for p in src_folder.iterdir() if p.suffix.lower() in EXTS]
        if not images:
            continue
        found_any = True
        rel = src_folder.relative_to(REVIEWED)
        dst_folder = AUGMENTED / rel
        n = augment_folder(src_folder, dst_folder)
        total += n
        print(f"  {rel}: {len(images)} → {n} images")

    if not found_any:
        print("⚠  No images found in data/reviewed/. Copy images there first.")
        return

    print(f"\n✓  Total augmented images: {total}")
    print(f"   Run python src/train_anomaly.py next.")


if __name__ == "__main__":
    main()
