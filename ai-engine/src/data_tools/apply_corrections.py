"""
Move images flagged as wrong by the feedback system into the correct training folders.

Run this after collecting several corrections, then retrain:
    python src/data_tools/apply_corrections.py
    python src/data_tools/augment.py
    python src/train_anomaly.py
"""
import sys
import os
import shutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parents[3]))

ROOT = Path(__file__).parents[3]
DB_PATH = ROOT / "backend" / "inspection.db"
GOOD_DIR = ROOT / "data" / "reviewed" / "good"
DEFECTIVE_DIR = ROOT / "data" / "reviewed" / "defective" / "corrected"

GOOD_DIR.mkdir(parents=True, exist_ok=True)
DEFECTIVE_DIR.mkdir(parents=True, exist_ok=True)


def apply_corrections():
    try:
        import sqlalchemy
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
    except ImportError:
        print("ERROR: sqlalchemy not installed. Run: pip install sqlalchemy")
        return

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Start the backend once to create it.")
        return

    engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        rows = db.execute(text(
            "SELECT id, image_id, image_path, predicted, actual, correct_type "
            "FROM corrections WHERE applied = 0"
        )).fetchall()
    except Exception as e:
        print(f"ERROR reading corrections: {e}")
        db.close()
        return

    if not rows:
        print("No unapplied corrections found.")
        db.close()
        return

    moved_good = 0
    moved_defective = 0
    skipped = 0

    for row in rows:
        cid, image_id, image_path, predicted, actual, correct_type = row

        if not image_path or not Path(image_path).exists():
            print(f"  [{cid}] SKIP — image not found: {image_path}")
            skipped += 1
            continue

        src = Path(image_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_name = f"{timestamp}_{image_id[:8]}.jpg"

        # Model said FAIL but it was actually PASS → false positive → goes to good/
        # Model said PASS but it was actually FAIL → false negative → goes to defective/
        if actual == "PASS":
            dest = GOOD_DIR / dest_name
            shutil.copy2(src, dest)
            moved_good += 1
            print(f"  [{cid}] PASS: copied to good/ (was predicted {predicted})")
        elif actual == "FAIL":
            dest = DEFECTIVE_DIR / dest_name
            shutil.copy2(src, dest)
            moved_defective += 1
            label = f"correct_type={correct_type}" if correct_type else "unknown defect"
            print(f"  [{cid}] FAIL: copied to defective/corrected/ ({label}, was predicted {predicted})")
        else:
            print(f"  [{cid}] SKIP — actual={actual} (not PASS or FAIL)")
            skipped += 1
            continue

        db.execute(text("UPDATE corrections SET applied = 1 WHERE id = :id"), {"id": cid})

    db.commit()
    db.close()

    print(f"\nDone: {moved_good} → good/, {moved_defective} → defective/corrected/, {skipped} skipped")

    if moved_good + moved_defective > 0:
        print("\nNext steps:")
        print("  1. python src/data_tools/augment.py      # re-augment with new images")
        print("  2. python src/train_anomaly.py            # retrain model")
        print("  3. Restart AI engine with AI_MODE=real")


if __name__ == "__main__":
    apply_corrections()
