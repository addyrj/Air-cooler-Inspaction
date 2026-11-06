"""
Extract training frames from a cooler rotation video.

Usage:
  python src/data_tools/extract_frames.py --video path/to/video.mp4 --label good
  python src/data_tools/extract_frames.py --video path/to/defective.mp4 --label missing_knob

Arguments:
  --video     Path to your .mp4 / .avi / .mov file
  --label     "good"  OR  defect folder name:
              missing_knob | broken_grill | missing_wheel | cable_damage
  --every     Extract 1 frame every N frames (default: 15 — good for 30fps video)
  --quality   Skip blurry frames below this score (default: 80, set 0 to keep all)

Output:
  data/reviewed/good/           if --label good
  data/reviewed/defective/XXX/  if --label is a defect name
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import cv2
from pathlib import Path

REVIEWED = Path(__file__).parents[3] / "data" / "reviewed"
VALID_LABELS = {"good", "missing_knob", "broken_grill", "missing_wheel", "cable_damage"}


def blur_score(frame) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def extract(video_path: str, label: str, every: int, min_blur: float):
    if label not in VALID_LABELS:
        print(f"ERROR: --label must be one of: {', '.join(sorted(VALID_LABELS))}")
        sys.exit(1)

    out_dir = REVIEWED / ("good" if label == "good" else f"defective/{label}")
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"ERROR: Cannot open video: {video_path}")
        sys.exit(1)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps          = cap.get(cv2.CAP_PROP_FPS)
    duration_s   = total_frames / fps if fps > 0 else 0
    print(f"\nVideo: {video_path}")
    print(f"  Frames: {total_frames}  FPS: {fps:.1f}  Duration: {duration_s:.1f}s")
    print(f"  Extracting every {every} frames → ~{total_frames // every} candidates")
    print(f"  Output: {out_dir}\n")

    saved = skipped_blur = 0
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % every == 0:
            score = blur_score(frame)
            if score < min_blur:
                skipped_blur += 1
            else:
                fname = out_dir / f"{label}_f{frame_idx:05d}.jpg"
                cv2.imwrite(str(fname), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                saved += 1
                if saved % 10 == 0:
                    print(f"  Saved {saved} frames...", end="\r")
        frame_idx += 1

    cap.release()
    print(f"\n✓ Saved {saved} frames to {out_dir}")
    if skipped_blur:
        print(f"  Skipped {skipped_blur} blurry frames (blur score < {min_blur})")
    print(f"\nNext step: python src/data_tools/augment.py")


def main():
    parser = argparse.ArgumentParser(description="Extract frames from cooler video")
    parser.add_argument("--video",   required=True, help="Path to video file")
    parser.add_argument("--label",   required=True, help="good | missing_knob | broken_grill | missing_wheel | cable_damage")
    parser.add_argument("--every",   type=int,   default=15,  help="Extract 1 frame every N (default 15)")
    parser.add_argument("--quality", type=float, default=80.0, help="Min blur score to keep frame (default 80)")
    args = parser.parse_args()
    extract(args.video, args.label, args.every, args.quality)


if __name__ == "__main__":
    main()
