"""
ZoneShield AI — Dataset Health Analyzer
========================================
Analyzes the conveyor belt dataset before training to identify:
- Class imbalance severity
- Label quality issues
- Image quality problems
- Annotation consistency
- Train/val/test distribution

Usage:
    python analyze_dataset.py
"""

import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

DATASET_DIR = Path(r"C:\Users\Alence\Downloads\conveyor.v3i.yolov8")
CLASS_NAMES = {0: "cardboard_box", 1: "conveyor", 2: "kartonbox"}


def analyze():
    print("=" * 70)
    print("  ZoneShield AI — Dataset Health Analysis")
    print("=" * 70)

    results = {
        "splits": {},
        "class_distribution": {},
        "warnings": [],
        "recommendations": [],
    }

    for split in ["train", "valid", "test"]:
        img_dir = DATASET_DIR / split / "images"
        lbl_dir = DATASET_DIR / split / "labels"

        if not img_dir.exists():
            print(f"\n[!] {split} split not found")
            continue

        images = sorted(list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png")))
        labels = sorted(list(lbl_dir.glob("*.txt"))) if lbl_dir.exists() else []

        # Image names without extension
        img_stems = {p.stem for p in images}
        lbl_stems = {p.stem for p in labels}

        orphan_imgs = img_stems - lbl_stems
        orphan_lbls = lbl_stems - img_stems

        print(f"\n--- {split.upper()} Split ---")
        print(f"  Images: {len(images)} | Labels: {len(labels)}")

        if orphan_imgs:
            print(f"  [!] {len(orphan_imgs)} images without labels")
            results["warnings"].append(f"{split}: {len(orphan_imgs)} unlabeled images")
        if orphan_lbls:
            print(f"  [!] {len(orphan_lbls)} labels without images")
            results["warnings"].append(f"{split}: {len(orphan_lbls)} orphan labels")

        # Class distribution
        class_counts = Counter()
        bbox_sizes = defaultdict(list)
        annotations_per_image = []
        empty_labels = 0
        poly_format = False

        for lbl_path in labels:
            content = lbl_path.read_text().strip()
            if not content:
                empty_labels += 1
                annotations_per_image.append(0)
                continue

            lines = content.split("\n")
            annotations_per_image.append(len(lines))

            for line in lines:
                parts = line.strip().split()
                if not parts:
                    continue
                cls_id = int(parts[0])
                class_counts[cls_id] += 1

                if len(parts) > 5:
                    poly_format = True
                elif len(parts) == 5:
                    _, cx, cy, w, h = map(float, parts)
                    bbox_sizes[cls_id].append((w, h))

        total_anns = sum(class_counts.values())
        print(f"  Total annotations: {total_anns}")
        print(f"  Empty labels: {empty_labels}")
        print(f"  Label format: {'Segmentation (polygon)' if poly_format else 'Detection (bbox)'}")
        print(f"  Annotations/image: min={min(annotations_per_image) if annotations_per_image else 0}, "
              f"max={max(annotations_per_image) if annotations_per_image else 0}, "
              f"avg={np.mean(annotations_per_image) if annotations_per_image else 0:.1f}")

        print(f"\n  Class Distribution:")
        for cls_id in sorted(class_counts.keys()):
            name = CLASS_NAMES.get(cls_id, f"unknown_{cls_id}")
            count = class_counts[cls_id]
            pct = count / total_anns * 100 if total_anns > 0 else 0
            bar = "#" * max(1, int(pct / 2))
            flag = ""
            if count < 10:
                flag = " ** CRITICAL (< 10 samples)"
            elif count < 50:
                flag = " ** LOW"
            print(f"    {cls_id}: {name:15s} = {count:5d} ({pct:5.1f}%) {bar}{flag}")

        results["splits"][split] = {
            "images": len(images),
            "labels": len(labels),
            "annotations": total_anns,
            "class_counts": dict(class_counts),
        }
        results["class_distribution"][split] = dict(class_counts)

    # Check a sample of images for quality
    print(f"\n--- Image Quality Check (sample) ---")
    sample_dir = DATASET_DIR / "train" / "images"
    if sample_dir.exists():
        sample_imgs = list(sample_dir.glob("*.jpg"))[:20]
        widths, heights, channels = [], [], []
        corrupt = 0
        for img_path in sample_imgs:
            img = cv2.imread(str(img_path))
            if img is None:
                corrupt += 1
                continue
            h, w = img.shape[:2]
            c = img.shape[2] if img.ndim == 3 else 1
            widths.append(w)
            heights.append(h)
            channels.append(c)

        if widths:
            print(f"  Resolution: {min(widths)}x{min(heights)} to {max(widths)}x{max(heights)}")
            print(f"  Channels: {set(channels)}")
            print(f"  Corrupt images: {corrupt}/{len(sample_imgs)}")
            if len(set(zip(widths, heights))) > 1:
                print(f"  [!] Mixed resolutions detected")
        else:
            print(f"  [!] Could not read any sample images")

    # Recommendations
    print(f"\n{'='*70}")
    print(f"  TRAINING RECOMMENDATIONS")
    print(f"{'='*70}")

    train_dist = results["class_distribution"].get("train", {})
    if train_dist:
        min_class = min(train_dist.values())
        max_class = max(train_dist.values())
        ratio = max_class / min_class if min_class > 0 else float('inf')

        if ratio > 10:
            print(f"\n  ⚠️  SEVERE CLASS IMBALANCE (ratio {ratio:.0f}:1)")
            print(f"     Minority class has only {min_class} samples.")
            print(f"     Recommended mitigations:")
            print(f"     1. Heavy augmentation (mosaic=1.0, copy_paste=0.3, mixup=0.2)")
            print(f"     2. Oversample minority class (collect more data if possible)")
            print(f"     3. Use class weights in loss function")
            print(f"     4. Lower confidence threshold for minority class in inference")
            print(f"     5. Use focal loss (built into YOLOv8)")
            results["recommendations"].append("Severe class imbalance — use heavy augmentation")

        total_train = sum(train_dist.values())
        if total_train < 500:
            print(f"\n  ⚠️  SMALL DATASET ({total_train} annotations)")
            print(f"     Recommended:")
            print(f"     1. Use a pre-trained model (transfer learning)")
            print(f"     2. Start with YOLOv8n or YOLOv8s (avoid overfitting)")
            print(f"     3. Use maximum augmentation")
            print(f"     4. Increase patience for early stopping")
            results["recommendations"].append("Small dataset — use strong transfer learning")

    print(f"\n  ✅ RECOMMENDED TRAINING COMMAND:")
    print(f"     cd \"{DATASET_DIR.parent / 'BUILDWITHGEMINI' / 'OpenCV PRoject' / 'zoneshield-ai' / 'training' / 'scripts'}\"")
    print(f"     python train_yolov8.py --mode standard")
    print(f"\n  For competition submission:")
    print(f"     python train_yolov8.py --mode competition")
    print(f"{'='*70}")

    return results


if __name__ == "__main__":
    analyze()
