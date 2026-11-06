"""
Run from ai-engine/:  python src/train_anomaly.py
Trains a PatchCore anomaly detector on data/augmented/good/ (normal images).
Exports to models/active/model.onnx when done.
Compatible with anomalib 2.x.
"""
import sys
import os
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

BASE      = Path(__file__).parents[2]   # air-cooler-inspection/
AUGMENTED = BASE / "data" / "augmented"
MODEL_DIR = BASE / "models" / "active"


def _check_data():
    good = AUGMENTED / "good"
    imgs = list(good.rglob("*.jpg")) + list(good.rglob("*.jpeg")) + list(good.rglob("*.png"))
    if not good.exists() or not imgs:
        print("ERROR: No images in data/augmented/good/")
        print("Run:  python src/data_tools/augment.py")
        sys.exit(1)
    print(f"✓ {len(imgs)} good images in data/augmented/good/")
    return len(imgs)


def main():
    n = _check_data()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from anomalib.data import Folder
        from anomalib.models import Patchcore
        from anomalib.engine import Engine
        from anomalib.deploy import ExportType
    except ImportError as e:
        print(f"ERROR: {e}")
        print("Run: pip install anomalib")
        sys.exit(1)

    defective_dir = AUGMENTED / "defective"
    has_defects = defective_dir.exists() and any(defective_dir.rglob("*.*"))

    print(f"Defective images: {'yes' if has_defects else 'none (train-only mode)'}")
    print("\nConfiguring datamodule...")

    datamodule = Folder(
        name="cooler",
        root=AUGMENTED,
        normal_dir="good",
        abnormal_dir="defective" if has_defects else None,
        normal_split_ratio=0.2,      # 20% of good → validation/test
        train_batch_size=8,
        eval_batch_size=8,
        num_workers=0,
        seed=42,
    )

    print("Building PatchCore model (resnet18, CPU — fast first run)...")
    model = Patchcore(
        backbone="resnet18",          # faster than wide_resnet50_2 for first run
        layers=["layer2", "layer3"],
        coreset_sampling_ratio=0.1,
        num_neighbors=9,
    )

    lightning_dir = str(MODEL_DIR / "lightning")
    print(f"Training... (logs → {lightning_dir})")
    print("Expected time: 5–15 min on CPU\n")

    engine = Engine(
        default_root_dir=lightning_dir,
        max_epochs=1,
        accelerator="cpu",
        devices=1,
        enable_progress_bar=True,
        enable_model_summary=False,
        logger=False,
    )
    engine.fit(model=model, datamodule=datamodule)
    print("\n✓ Training complete")

    if has_defects:
        print("Evaluating on test set...")
        results = engine.test(model=model, datamodule=datamodule)
        print(f"Test results: {results}")

    # ── Export to ONNX ──────────────────────────────────────────────────────
    print("\nExporting ONNX model...")
    try:
        engine.export(
            model=model,
            export_type=ExportType.ONNX,
            export_root=MODEL_DIR,
        )
    except Exception as e:
        print(f"  Export warning: {e}")
        # Fallback: try torch.onnx directly
        try:
            import torch
            dummy = torch.zeros(1, 3, 256, 256)
            model.eval()
            torch.onnx.export(
                model, dummy,
                str(MODEL_DIR / "model.onnx"),
                opset_version=14,
                input_names=["input"],
                output_names=["output"],
            )
            print("  Exported via torch.onnx fallback")
        except Exception as e2:
            print(f"  Fallback also failed: {e2}")

    # ── Locate and normalise the output file ────────────────────────────────
    target = MODEL_DIR / "model.onnx"
    candidates = [p for p in MODEL_DIR.rglob("*.onnx") if p != target]
    if not target.exists() and candidates:
        import shutil
        best = sorted(candidates, key=lambda p: p.stat().st_size, reverse=True)[0]
        shutil.copy(best, target)
        print(f"  Copied {best.name} → model.onnx")

    if target.exists():
        size_mb = target.stat().st_size / 1_048_576
        print(f"\n✓ Model saved: {target}  ({size_mb:.1f} MB)")
        print("\nNext step:")
        print("  Set AI_MODE=real and restart ai-engine:")
        print("  $env:AI_MODE = 'real'")
        print("  python main.py")
    else:
        print("\nWARNING: model.onnx not found after export.")
        print(f"Check: {MODEL_DIR}")


if __name__ == "__main__":
    main()
