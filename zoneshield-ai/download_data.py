#!/usr/bin/env python3
"""
ZoneShield AI — Dataset Downloader
====================================
Downloads the conveyor belt dataset from Roboflow into the workspace.
Run this on your EC2 Graviton instance after cloning the repository.

Usage:
    python download_data.py                             # Interactive (will prompt for API key)
    python download_data.py --api-key YOUR_KEY          # Non-interactive
    python download_data.py --local /path/to/zip        # From local ZIP archive
    
The dataset will be placed at: ./dataset/
"""

import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path

DATASET_DIR = Path("./dataset")
ROBOFLOW_WORKSPACE = "conveyor-550m0"
ROBOFLOW_PROJECT = "conveyor-hhrzw"
ROBOFLOW_VERSION = 3
EXPECTED_CLASSES = ["cardboard box", "conveyor", "kartonbox"]


def download_from_roboflow(api_key: str) -> Path:
    """Download dataset from Roboflow API."""
    try:
        from roboflow import Roboflow
    except ImportError:
        print("[!] roboflow package not installed. Installing...")
        os.system(f"{sys.executable} -m pip install roboflow -q")
        from roboflow import Roboflow

    print(f"[1/3] Connecting to Roboflow...")
    rf = Roboflow(api_key=api_key)
    project = rf.workspace(ROBOFLOW_WORKSPACE).project(ROBOFLOW_PROJECT)
    
    print(f"[2/3] Downloading dataset v{ROBOFLOW_VERSION} (YOLOv8 format)...")
    version = project.version(ROBOFLOW_VERSION)
    dataset = version.download("yolov8", location=str(DATASET_DIR))
    
    print(f"[3/3] Dataset downloaded to: {dataset.location}")
    return Path(dataset.location)


def setup_from_local_zip(zip_path: str) -> Path:
    """Extract dataset from a local ZIP archive."""
    zip_file = Path(zip_path)
    if not zip_file.exists():
        print(f"[!] ZIP file not found: {zip_path}")
        sys.exit(1)

    print(f"[1/2] Extracting {zip_file.name}...")
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(zip_file, 'r') as zf:
        zf.extractall(DATASET_DIR)
    
    print(f"[2/2] Extracted to: {DATASET_DIR}")
    return DATASET_DIR


def setup_from_local_dir(dir_path: str) -> Path:
    """Copy/symlink dataset from a local directory."""
    src = Path(dir_path)
    if not src.exists():
        print(f"[!] Directory not found: {dir_path}")
        sys.exit(1)

    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    # Copy data.yaml and directories
    for item in ["data.yaml", "train", "valid", "test"]:
        src_item = src / item
        dst_item = DATASET_DIR / item
        if src_item.exists():
            if src_item.is_dir():
                if dst_item.exists():
                    shutil.rmtree(dst_item)
                shutil.copytree(src_item, dst_item)
            else:
                shutil.copy2(src_item, dst_item)
            print(f"  Copied: {item}")

    return DATASET_DIR


def fix_data_yaml(dataset_path: Path):
    """Fix data.yaml paths to use relative paths from repository root."""
    yaml_path = dataset_path / "data.yaml"
    if not yaml_path.exists():
        # Search one level deeper
        for candidate in dataset_path.rglob("data.yaml"):
            yaml_path = candidate
            break
    
    if not yaml_path.exists():
        print("[!] data.yaml not found in dataset directory")
        return

    content = yaml_path.read_text()
    
    # Rewrite paths to be relative to dataset directory
    new_lines = []
    posix_path = dataset_path.resolve().as_posix()
    for line in content.split("\n"):
        if line.startswith("train:"):
            new_lines.append(f"train: {posix_path}/train/images")
        elif line.startswith("val:"):
            new_lines.append(f"val: {posix_path}/valid/images")
        elif line.startswith("test:"):
            new_lines.append(f"test: {posix_path}/test/images")
        else:
            new_lines.append(line)
    
    yaml_path.write_text("\n".join(new_lines))
    print(f"[OK] data.yaml paths updated to absolute paths")
    print(f"     {yaml_path}")


def validate_dataset(dataset_path: Path):
    """Validate dataset integrity."""
    print(f"\n{'='*60}")
    print(f"  Dataset Validation")
    print(f"{'='*60}")
    
    issues = []
    
    # Check data.yaml
    yaml_path = dataset_path / "data.yaml"
    if not yaml_path.exists():
        issues.append("data.yaml not found")
        print(f"[FAIL] data.yaml missing")
    else:
        print(f"[OK]   data.yaml exists")

    # Check splits
    for split in ["train", "valid", "test"]:
        img_dir = dataset_path / split / "images"
        lbl_dir = dataset_path / split / "labels"
        
        if img_dir.exists():
            imgs = list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png"))
            lbls = list(lbl_dir.glob("*.txt")) if lbl_dir.exists() else []
            
            missing = len(imgs) - len(lbls)
            status = "OK  " if missing == 0 else "WARN"
            print(f"[{status}] {split:5s}: {len(imgs):4d} images, {len(lbls):4d} labels"
                  + (f" ({missing} missing labels)" if missing > 0 else ""))
            
            if missing > 0:
                issues.append(f"{split}: {missing} images without labels")
        else:
            print(f"[FAIL] {split}: images directory not found")
            issues.append(f"{split} split missing")

    # Class distribution
    class_counts = {}
    lbl_dir = dataset_path / "train" / "labels"
    if lbl_dir.exists():
        for txt in lbl_dir.glob("*.txt"):
            for line in txt.read_text().strip().split("\n"):
                if line.strip():
                    cls_id = int(line.strip().split()[0])
                    class_counts[cls_id] = class_counts.get(cls_id, 0) + 1
    
    if class_counts:
        print(f"\n  Class distribution (train):")
        total = sum(class_counts.values())
        for cls_id in sorted(class_counts.keys()):
            name = EXPECTED_CLASSES[cls_id] if cls_id < len(EXPECTED_CLASSES) else f"class_{cls_id}"
            count = class_counts[cls_id]
            pct = count / total * 100
            print(f"    {cls_id}: {name:15s} = {count:5d} ({pct:.1f}%)")

    if issues:
        print(f"\n  Warnings: {len(issues)}")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print(f"\n  All checks passed!")
    
    print(f"{'='*60}")
    return len(issues) == 0


def main():
    parser = argparse.ArgumentParser(
        description="ZoneShield AI — Download conveyor belt dataset"
    )
    parser.add_argument("--api-key", type=str, default=None,
                        help="Roboflow API key")
    parser.add_argument("--local", type=str, default=None,
                        help="Path to local ZIP or directory")
    parser.add_argument("--skip-validate", action="store_true",
                        help="Skip dataset validation")
    args = parser.parse_args()

    print("=" * 60)
    print("  ZoneShield AI — Dataset Setup")
    print("=" * 60)

    if args.local:
        if args.local.endswith(".zip"):
            dataset_path = setup_from_local_zip(args.local)
        else:
            dataset_path = setup_from_local_dir(args.local)
    else:
        api_key = args.api_key
        if not api_key:
            api_key = os.environ.get("ROBOFLOW_API_KEY")
        if not api_key:
            print("\nNo API key provided. Get one from: https://roboflow.com/settings")
            api_key = input("Enter your Roboflow API key: ").strip()
            if not api_key:
                print("[!] No API key. Use --local to load from a ZIP or directory instead.")
                sys.exit(1)

        dataset_path = download_from_roboflow(api_key)

    # Fix data.yaml paths
    fix_data_yaml(dataset_path)

    # Validate
    if not args.skip_validate:
        validate_dataset(dataset_path)

    print(f"\n  Dataset ready at: {dataset_path.resolve()}")
    print(f"  Next step: Start training with:")
    print(f"    yolo train data={dataset_path.resolve()}/data.yaml model=yolov8n.pt epochs=50 imgsz=640")
    print()


if __name__ == "__main__":
    main()
