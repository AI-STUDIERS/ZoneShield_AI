"""
ZoneShield AI — Competition-Grade YOLOv8 Conveyor Belt Training Pipeline
=========================================================================
Trains YOLOv8 segmentation models for conveyor belt object detection.
Handles the severe class imbalance (kartonbox: 8 samples) through heavy
augmentation, and exports the best model to ONNX for OpenCV DNN inference.

Usage:
    python train_yolov8.py                      # Full training pipeline
    python train_yolov8.py --mode quick          # Quick 50-epoch test run
    python train_yolov8.py --mode competition    # Competition-grade (300 epochs)
    python train_yolov8.py --mode export-only    # Export existing best.pt to ONNX
"""

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# ─── Configuration ──────────────────────────────────────────────────────────────

DATASET_DIR = Path(r"C:\Users\Alence\Downloads\conveyor.v3i.yolov8")
PROJECT_DIR = Path(r"C:\Users\Alence\Downloads\BUILDWITHGEMINI\OpenCV PRoject\zoneshield-ai")
TRAINING_DIR = PROJECT_DIR / "training"
CONFIG_DIR = TRAINING_DIR / "configs"
RUNS_DIR = TRAINING_DIR / "runs"
DATA_YAML = CONFIG_DIR / "conveyor_data.yaml"

CLASS_NAMES = {0: "cardboard_box", 1: "conveyor", 2: "kartonbox"}

# ─── Training Profiles ─────────────────────────────────────────────────────────

PROFILES = {
    "quick": {
        "model": "yolov8n-seg.pt",      # Nano — fastest
        "epochs": 50,
        "imgsz": 640,
        "batch": 8,
        "patience": 15,
        "lr0": 0.01,
        "lrf": 0.01,
        "warmup_epochs": 3,
        "cos_lr": True,
        "optimizer": "AdamW",
        "weight_decay": 0.0005,
        "name": "conveyor-quick",
        "description": "Quick validation run (50 epochs, nano model)",
    },
    "standard": {
        "model": "yolov8s-seg.pt",      # Small — good balance
        "epochs": 150,
        "imgsz": 640,
        "batch": 8,
        "patience": 30,
        "lr0": 0.01,
        "lrf": 0.001,
        "warmup_epochs": 5,
        "cos_lr": True,
        "optimizer": "AdamW",
        "weight_decay": 0.0005,
        "name": "conveyor-standard",
        "description": "Standard training (150 epochs, small model)",
    },
    "competition": {
        "model": "yolov8m-seg.pt",      # Medium — competition grade
        "epochs": 300,
        "imgsz": 640,
        "batch": 4,                      # Lower batch for GPU memory on CPU
        "patience": 50,
        "lr0": 0.005,
        "lrf": 0.0005,
        "warmup_epochs": 10,
        "cos_lr": True,
        "optimizer": "AdamW",
        "weight_decay": 0.001,
        "name": "conveyor-competition",
        "description": "Competition-grade (300 epochs, medium model)",
    },
}


def check_environment():
    """Verify all dependencies and dataset integrity."""
    print("=" * 70)
    print("  ZoneShield AI — YOLOv8 Training Environment Check")
    print("=" * 70)

    # Python
    print(f"\n[✓] Python:  {sys.version.split()[0]}")

    # PyTorch
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        device_name = torch.cuda.get_device_name(0) if cuda_available else "CPU"
        print(f"[✓] PyTorch: {torch.__version__}")
        print(f"[✓] Device:  {device_name} {'(CUDA)' if cuda_available else '(CPU-only — training will be slow)'}")
        if cuda_available:
            mem_gb = torch.cuda.get_device_properties(0).total_mem / (1024**3)
            print(f"    GPU Mem: {mem_gb:.1f} GB")
    except ImportError:
        print("[✗] PyTorch not installed!")
        sys.exit(1)

    # Ultralytics
    try:
        import ultralytics
        print(f"[✓] Ultralytics: {ultralytics.__version__}")
    except ImportError:
        print("[✗] Ultralytics not installed! Run: pip install ultralytics")
        sys.exit(1)

    # OpenCV
    try:
        import cv2
        print(f"[✓] OpenCV:  {cv2.__version__}")
    except ImportError:
        print("[!] OpenCV not installed (needed for ONNX export validation)")

    # Dataset
    print(f"\n--- Dataset Validation ---")
    if not DATASET_DIR.exists():
        print(f"[✗] Dataset not found: {DATASET_DIR}")
        sys.exit(1)

    splits = {"train": 0, "valid": 0, "test": 0}
    for split_name in splits:
        img_dir = DATASET_DIR / split_name / "images"
        lbl_dir = DATASET_DIR / split_name / "labels"
        if img_dir.exists():
            imgs = list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png"))
            splits[split_name] = len(imgs)
            lbls = list(lbl_dir.glob("*.txt")) if lbl_dir.exists() else []
            orphans = len(imgs) - len(lbls)
            status = "✓" if orphans == 0 else f"! ({orphans} images missing labels)"
            print(f"[{status}] {split_name:5s}: {len(imgs)} images, {len(lbls)} labels")
        else:
            print(f"[✗] {split_name}: directory not found")

    # Class distribution
    print(f"\n--- Class Distribution (train) ---")
    class_counts = {}
    lbl_dir = DATASET_DIR / "train" / "labels"
    if lbl_dir.exists():
        for txt in lbl_dir.glob("*.txt"):
            for line in txt.read_text().strip().split("\n"):
                if line.strip():
                    cls_id = int(line.strip().split()[0])
                    class_counts[cls_id] = class_counts.get(cls_id, 0) + 1

    total = sum(class_counts.values())
    for cls_id in sorted(class_counts.keys()):
        name = CLASS_NAMES.get(cls_id, f"class_{cls_id}")
        count = class_counts[cls_id]
        pct = (count / total * 100) if total > 0 else 0
        bar = "█" * int(pct / 2)
        imbalance = " ⚠️  SEVERE IMBALANCE" if count < 20 else ""
        print(f"  {cls_id} ({name:15s}): {count:5d} ({pct:5.1f}%) {bar}{imbalance}")

    print(f"\n  Label format: {'Segmentation (polygon)' if is_segmentation_format() else 'Detection (bbox)'}")
    print("=" * 70)

    return cuda_available


def is_segmentation_format():
    """Check if labels use segmentation (polygon) format vs detection (bbox)."""
    lbl_dir = DATASET_DIR / "train" / "labels"
    for txt in list(lbl_dir.glob("*.txt"))[:5]:
        for line in txt.read_text().strip().split("\n"):
            parts = line.strip().split()
            if len(parts) > 5:  # More than class + 4 bbox values = polygon
                return True
    return False


def train(profile_name: str, resume: bool = False):
    """Run YOLOv8 training with the specified profile."""
    from ultralytics import YOLO

    profile = PROFILES[profile_name]
    print(f"\n{'='*70}")
    print(f"  Starting Training: {profile['description']}")
    print(f"  Model: {profile['model']} | Epochs: {profile['epochs']} | Image Size: {profile['imgsz']}")
    print(f"{'='*70}\n")

    # Determine task based on label format
    task = "segment" if is_segmentation_format() else "detect"
    print(f"[INFO] Detected label format: {task}")

    # Load model
    model = YOLO(profile["model"])

    # Check if we should use GPU
    import torch
    device = "0" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("[WARNING] Training on CPU — this will be very slow.")
        print("         For competition-grade results, use a GPU (Google Colab, AWS, etc.)")
        # Reduce batch size for CPU
        batch = min(profile["batch"], 4)
    else:
        batch = profile["batch"]

    # ─── Heavy Augmentation to Combat Class Imbalance ───────────────────
    # The kartonbox class has only 8 samples. We use aggressive augmentation
    # to synthetically expand the effective training set.

    train_args = {
        "data": str(DATA_YAML),
        "epochs": profile["epochs"],
        "imgsz": profile["imgsz"],
        "batch": batch,
        "patience": profile["patience"],
        "device": device,
        "project": str(RUNS_DIR),
        "name": profile["name"],
        "exist_ok": True,
        "pretrained": True,
        "optimizer": profile["optimizer"],
        "lr0": profile["lr0"],
        "lrf": profile["lrf"],
        "warmup_epochs": profile["warmup_epochs"],
        "cos_lr": profile["cos_lr"],
        "weight_decay": profile["weight_decay"],
        "resume": resume,

        # ── Augmentation (aggressive for class imbalance) ──
        "hsv_h": 0.015,       # Hue shift
        "hsv_s": 0.7,         # Saturation variation
        "hsv_v": 0.4,         # Value/brightness variation
        "degrees": 15.0,      # Rotation ±15°
        "translate": 0.15,    # Translation
        "scale": 0.5,         # Scale variation (±50%)
        "shear": 5.0,         # Shear
        "perspective": 0.001, # Perspective distortion
        "flipud": 0.3,        # Vertical flip (conveyor might be vertical)
        "fliplr": 0.5,        # Horizontal flip
        "mosaic": 1.0,        # Mosaic augmentation (combines 4 images)
        "mixup": 0.15,        # MixUp augmentation (blends 2 images)
        "copy_paste": 0.2,    # Copy-paste augmentation (key for segmentation!)
        "erasing": 0.1,       # Random erasing
        "crop_fraction": 1.0, # Crop fraction for classification

        # ── Training stability ──
        "amp": True,           # Automatic mixed precision
        "seed": 42,            # Reproducibility
        "val": True,           # Run validation every epoch
        "plots": True,         # Generate training plots
        "save": True,          # Save checkpoints
        "save_period": 25,     # Save checkpoint every 25 epochs
        "verbose": True,
    }

    # Add close_mosaic for longer training
    if profile["epochs"] >= 100:
        train_args["close_mosaic"] = max(10, profile["epochs"] // 10)

    start = time.time()
    results = model.train(**train_args)
    elapsed = time.time() - start

    print(f"\n{'='*70}")
    print(f"  Training Complete!")
    print(f"  Duration: {elapsed/3600:.1f} hours ({elapsed/60:.0f} minutes)")
    print(f"  Results:  {RUNS_DIR / profile['name']}")
    print(f"{'='*70}")

    return results, model


def validate_model(model_path: str):
    """Run validation and print detailed metrics."""
    from ultralytics import YOLO

    print(f"\n--- Validating: {model_path} ---")
    model = YOLO(model_path)
    results = model.val(
        data=str(DATA_YAML),
        split="test",
        imgsz=640,
        batch=4,
        verbose=True,
        plots=True,
        save_json=True,
    )

    print("\n--- Validation Results ---")
    print(f"  mAP50:      {results.seg.map50:.4f}" if hasattr(results, 'seg') else f"  mAP50:      {results.box.map50:.4f}")
    print(f"  mAP50-95:   {results.seg.map:.4f}" if hasattr(results, 'seg') else f"  mAP50-95:   {results.box.map:.4f}")

    if hasattr(results, 'seg'):
        # Per-class metrics
        for i, name in CLASS_NAMES.items():
            if i < len(results.seg.ap50):
                print(f"  {name:15s}  AP50={results.seg.ap50[i]:.3f}  AP50-95={results.seg.ap[i]:.3f}")

    return results


def export_to_onnx(model_path: str, output_dir: Path = None):
    """Export the best model to ONNX for OpenCV DNN inference."""
    from ultralytics import YOLO

    print(f"\n{'='*70}")
    print(f"  Exporting to ONNX for OpenCV DNN Inference")
    print(f"{'='*70}")

    model = YOLO(model_path)

    # Export with settings optimized for OpenCV DNN
    onnx_path = model.export(
        format="onnx",
        imgsz=640,
        opset=12,          # OpenCV DNN supports opset 12 well
        simplify=True,     # Simplify ONNX graph
        dynamic=False,     # Static shapes for OpenCV DNN (faster)
        half=False,        # FP32 for CPU compatibility
    )

    print(f"\n[✓] ONNX exported: {onnx_path}")

    # Copy to the project data directory
    if output_dir is None:
        output_dir = PROJECT_DIR / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    dest = output_dir / "conveyor_yolov8_best.onnx"
    shutil.copy2(onnx_path, dest)
    print(f"[✓] Copied to:     {dest}")

    # Validate with OpenCV DNN
    try:
        import cv2
        net = cv2.dnn.readNetFromONNX(str(dest))
        print(f"[✓] OpenCV DNN load: SUCCESS (cv2 {cv2.__version__})")

        # Get layer info
        layer_names = net.getLayerNames()
        out_layers = net.getUnconnectedOutLayersNames()
        print(f"    Layers: {len(layer_names)} | Output layers: {out_layers}")
    except Exception as e:
        print(f"[!] OpenCV DNN validation failed: {e}")
        print("    The ONNX file may still work with a different OpenCV version.")

    # Also export to TorchScript for backup
    try:
        ts_path = model.export(format="torchscript", imgsz=640)
        ts_dest = output_dir / "conveyor_yolov8_best.torchscript"
        shutil.copy2(ts_path, ts_dest)
        print(f"[✓] TorchScript:   {ts_dest}")
    except Exception as e:
        print(f"[!] TorchScript export skipped: {e}")

    return dest


def generate_training_report(profile_name: str, results, elapsed_seconds: float):
    """Generate a JSON training report for competition submission."""
    report = {
        "project": "ZoneShield AI",
        "task": "Conveyor Belt Object Detection/Segmentation",
        "timestamp": datetime.now().isoformat(),
        "profile": profile_name,
        "profile_config": PROFILES[profile_name],
        "dataset": {
            "source": "Roboflow conveyor-hhrzw v3",
            "license": "CC BY 4.0",
            "format": "YOLOv8 segmentation (polygon)",
            "images": {"train": 837, "valid": 211, "test": 87},
            "classes": CLASS_NAMES,
            "class_distribution_train": {
                "cardboard_box": 596,
                "conveyor": 236,
                "kartonbox": 8,
            },
            "known_issues": [
                "Severe class imbalance: kartonbox has only 8 training samples",
                "Mitigated with copy-paste, mosaic, mixup augmentation",
            ],
        },
        "training_duration_seconds": elapsed_seconds,
        "training_duration_human": f"{elapsed_seconds/3600:.1f}h ({elapsed_seconds/60:.0f}m)",
        "augmentation_strategy": [
            "Mosaic 1.0 (combine 4 images per training sample)",
            "Copy-paste 0.2 (key for segmentation with class imbalance)",
            "MixUp 0.15",
            "HSV augmentation (h=0.015, s=0.7, v=0.4)",
            "Geometric: rotation ±15°, scale ±50%, shear 5°, perspective 0.001",
            "Flip: horizontal 50%, vertical 30%",
            "Random erasing 10%",
        ],
    }

    report_path = TRAINING_DIR / f"training_report_{profile_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"[✓] Training report: {report_path}")
    return report_path


def main():
    parser = argparse.ArgumentParser(description="ZoneShield AI YOLOv8 Training Pipeline")
    parser.add_argument(
        "--mode",
        choices=["quick", "standard", "competition", "validate", "export-only"],
        default="standard",
        help="Training profile or action",
    )
    parser.add_argument("--model-path", type=str, default=None,
                        help="Path to existing model (for validate/export-only)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last checkpoint")
    args = parser.parse_args()

    # Always run environment check
    has_gpu = check_environment()

    if args.mode == "validate":
        if not args.model_path:
            # Try to find the best model
            for profile in ["competition", "standard", "quick"]:
                best = RUNS_DIR / PROFILES[profile]["name"] / "weights" / "best.pt"
                if best.exists():
                    args.model_path = str(best)
                    break
        if not args.model_path:
            print("[✗] No model found. Train first or specify --model-path")
            sys.exit(1)
        validate_model(args.model_path)
        return

    if args.mode == "export-only":
        if not args.model_path:
            for profile in ["competition", "standard", "quick"]:
                best = RUNS_DIR / PROFILES[profile]["name"] / "weights" / "best.pt"
                if best.exists():
                    args.model_path = str(best)
                    break
        if not args.model_path:
            print("[✗] No model found. Train first or specify --model-path")
            sys.exit(1)
        export_to_onnx(args.model_path)
        return

    # Warn about CPU training
    if not has_gpu:
        print("\n" + "⚠" * 35)
        print("  WARNING: No GPU detected!")
        print(f"  '{args.mode}' profile will train {PROFILES[args.mode]['epochs']} epochs on CPU.")
        print("  Estimated time: VERY SLOW (hours to days)")
        print("")
        print("  For faster training, use:")
        print("  • Google Colab (free GPU)")
        print("  • AWS EC2 g4dn/p3 instance")
        print("  • Local NVIDIA GPU with CUDA")
        print("⚠" * 35)

        response = input("\n  Continue on CPU? [y/N]: ").strip().lower()
        if response != "y":
            print("\n  Generate a Colab notebook instead? Creating...")
            generate_colab_notebook(args.mode)
            return

    # Train
    start = time.time()
    results, model = train(args.mode, resume=args.resume)
    elapsed = time.time() - start

    # Validate on test set
    best_path = RUNS_DIR / PROFILES[args.mode]["name"] / "weights" / "best.pt"
    if best_path.exists():
        validate_model(str(best_path))
        export_to_onnx(str(best_path))

    # Generate report
    generate_training_report(args.mode, results, elapsed)

    print(f"\n{'='*70}")
    print("  TRAINING PIPELINE COMPLETE")
    print(f"  Best model: {best_path}")
    print(f"  ONNX model: {PROJECT_DIR / 'data' / 'conveyor_yolov8_best.onnx'}")
    print(f"{'='*70}")


def generate_colab_notebook(profile_name: str):
    """Generate a Google Colab notebook for GPU training."""
    profile = PROFILES[profile_name]

    notebook = {
        "nbformat": 4,
        "nbformat_minor": 0,
        "metadata": {
            "colab": {"provenance": [], "gpuType": "T4"},
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
            "accelerator": "GPU",
        },
        "cells": [
            {
                "cell_type": "markdown",
                "source": [
                    "# 🛡️ ZoneShield AI — YOLOv8 Conveyor Belt Training\n",
                    f"**Profile:** {profile['description']}\n\n",
                    "**Dataset:** Roboflow conveyor-hhrzw v3 (CC BY 4.0)\n\n",
                    "**Classes:** cardboard_box, conveyor, kartonbox\n\n",
                    "⚡ **Runtime → Change runtime type → T4 GPU**",
                ],
            },
            {
                "cell_type": "code",
                "source": [
                    "# 1. Install dependencies\n",
                    "!pip install ultralytics roboflow -q\n",
                    "\n",
                    "import torch\n",
                    "print(f'PyTorch: {torch.__version__}')\n",
                    "print(f'CUDA: {torch.cuda.is_available()}')\n",
                    "if torch.cuda.is_available():\n",
                    "    print(f'GPU: {torch.cuda.get_device_name(0)}')\n",
                ],
                "execution_count": None,
                "outputs": [],
            },
            {
                "cell_type": "code",
                "source": [
                    "# 2. Download dataset from Roboflow\n",
                    "from roboflow import Roboflow\n",
                    "rf = Roboflow(api_key='YOUR_ROBOFLOW_API_KEY')  # Get from roboflow.com/settings\n",
                    "project = rf.workspace('conveyor-550m0').project('conveyor-hhrzw')\n",
                    "version = project.version(3)\n",
                    "dataset = version.download('yolov8')\n",
                    "print(f'Dataset path: {dataset.location}')\n",
                ],
                "execution_count": None,
                "outputs": [],
            },
            {
                "cell_type": "code",
                "source": [
                    "# 2b. ALTERNATIVE: Upload your local dataset zip\n",
                    "# Upload conveyor.v3i.yolov8.zip via Colab sidebar, then:\n",
                    "# !unzip -q conveyor.v3i.yolov8.zip -d /content/conveyor_dataset\n",
                    "# dataset_location = '/content/conveyor_dataset'\n",
                ],
                "execution_count": None,
                "outputs": [],
            },
            {
                "cell_type": "code",
                "source": [
                    "# 3. Train YOLOv8 Segmentation Model\n",
                    "from ultralytics import YOLO\n",
                    "\n",
                    f"model = YOLO('{profile['model']}')\n",
                    "\n",
                    "results = model.train(\n",
                    f"    data=dataset.location + '/data.yaml',\n",
                    f"    epochs={profile['epochs']},\n",
                    f"    imgsz={profile['imgsz']},\n",
                    f"    batch={profile['batch'] * 2},  # Colab GPU can handle larger batch\n",
                    f"    patience={profile['patience']},\n",
                    f"    lr0={profile['lr0']},\n",
                    f"    lrf={profile['lrf']},\n",
                    f"    warmup_epochs={profile['warmup_epochs']},\n",
                    f"    cos_lr={profile['cos_lr']},\n",
                    f"    optimizer='{profile['optimizer']}',\n",
                    f"    weight_decay={profile['weight_decay']},\n",
                    "    device=0,\n",
                    "    amp=True,\n",
                    "    seed=42,\n",
                    "    # Heavy augmentation for class imbalance\n",
                    "    hsv_h=0.015, hsv_s=0.7, hsv_v=0.4,\n",
                    "    degrees=15.0, translate=0.15, scale=0.5,\n",
                    "    shear=5.0, perspective=0.001,\n",
                    "    flipud=0.3, fliplr=0.5,\n",
                    "    mosaic=1.0, mixup=0.15,\n",
                    "    copy_paste=0.2,  # Critical for seg with class imbalance\n",
                    "    erasing=0.1,\n",
                    f"    close_mosaic={max(10, profile['epochs']//10)},\n",
                    "    plots=True, save=True, val=True,\n",
                    f"    name='zoneshield-{profile_name}',\n",
                    ")\n",
                ],
                "execution_count": None,
                "outputs": [],
            },
            {
                "cell_type": "code",
                "source": [
                    "# 4. Validate on test set\n",
                    "best = YOLO('runs/segment/zoneshield-" + profile_name + "/weights/best.pt')\n",
                    "metrics = best.val(data=dataset.location + '/data.yaml', split='test')\n",
                    "print(f'mAP50: {metrics.seg.map50:.4f}')\n",
                    "print(f'mAP50-95: {metrics.seg.map:.4f}')\n",
                ],
                "execution_count": None,
                "outputs": [],
            },
            {
                "cell_type": "code",
                "source": [
                    "# 5. Export to ONNX (for OpenCV DNN)\n",
                    "onnx_path = best.export(\n",
                    "    format='onnx',\n",
                    "    imgsz=640,\n",
                    "    opset=12,\n",
                    "    simplify=True,\n",
                    "    dynamic=False,\n",
                    "    half=False,\n",
                    ")\n",
                    "print(f'ONNX exported: {onnx_path}')\n",
                ],
                "execution_count": None,
                "outputs": [],
            },
            {
                "cell_type": "code",
                "source": [
                    "# 6. Download the trained model\n",
                    "from google.colab import files\n",
                    "files.download('runs/segment/zoneshield-" + profile_name + "/weights/best.pt')\n",
                    "files.download(onnx_path)\n",
                    "\n",
                    "# Also zip all results\n",
                    "!zip -r zoneshield_results.zip runs/segment/zoneshield-" + profile_name + "/\n",
                    "files.download('zoneshield_results.zip')\n",
                ],
                "execution_count": None,
                "outputs": [],
            },
            {
                "cell_type": "code",
                "source": [
                    "# 7. Quick inference test\n",
                    "import cv2\n",
                    "import matplotlib.pyplot as plt\n",
                    "from pathlib import Path\n",
                    "import glob\n",
                    "\n",
                    "test_imgs = glob.glob(dataset.location + '/test/images/*.jpg')[:4]\n",
                    "fig, axes = plt.subplots(1, len(test_imgs), figsize=(20, 5))\n",
                    "for ax, img_path in zip(axes, test_imgs):\n",
                    "    results = best.predict(img_path, conf=0.25, verbose=False)\n",
                    "    annotated = results[0].plot()\n",
                    "    ax.imshow(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB))\n",
                    "    ax.axis('off')\n",
                    "    ax.set_title(Path(img_path).stem[:20])\n",
                    "plt.tight_layout()\n",
                    "plt.savefig('inference_preview.png', dpi=150)\n",
                    "plt.show()\n",
                ],
                "execution_count": None,
                "outputs": [],
            },
        ],
    }

    nb_path = TRAINING_DIR / f"ZoneShield_Train_{profile_name}_Colab.ipynb"
    nb_path.parent.mkdir(parents=True, exist_ok=True)
    nb_path.write_text(json.dumps(notebook, indent=2))
    print(f"\n[✓] Colab notebook created: {nb_path}")
    print(f"    Upload to Google Colab: https://colab.research.google.com/")
    print(f"    1. Upload the notebook")
    print(f"    2. Set Runtime → GPU (T4)")
    print(f"    3. Upload your dataset ZIP or use Roboflow API key")
    print(f"    4. Run all cells")
    print(f"    5. Download best.pt and ONNX model when done")


if __name__ == "__main__":
    main()
