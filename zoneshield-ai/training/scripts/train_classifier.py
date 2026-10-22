"""
ZoneShield AI — Lightweight 3-Class Crop Classifier Training
==============================================================
Trains a small CNN classifier (foreign / legit / ambiguous) from the
YOLOv8 segmentation dataset crops. This model is loaded by the existing
pipeline's Classify stage via cv2.dnn.readNetFromONNX.

The model takes 32x32 BGR crops and outputs [foreign, legit, ambiguous] probs.

This is SEPARATE from the full YOLOv8 segmentation model — it's the
lightweight fallback classifier for object crops already detected by
the contour-based pipeline.

Usage:
    python train_classifier.py           # Train and export ONNX
    python train_classifier.py --epochs 50 --lr 0.001
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np

DATASET_DIR = Path(r"C:\Users\Alence\Downloads\conveyor.v3i.yolov8")
PROJECT_DIR = Path(r"C:\Users\Alence\Downloads\BUILDWITHGEMINI\OpenCV PRoject\zoneshield-ai")
OUTPUT_DIR = PROJECT_DIR / "data"

# Map Roboflow classes → ZoneShield pipeline classes
# 0: cardboard_box → foreign (foreign object on conveyor)
# 1: conveyor → legit (the conveyor belt itself)
# 2: kartonbox → foreign (another foreign object type)
ROBOFLOW_TO_ZONESHIELD = {
    0: 0,  # cardboard_box → foreign
    1: 1,  # conveyor → legit
    2: 0,  # kartonbox → foreign (merged with cardboard_box)
}
# Output classes: [foreign=0, legit=1, ambiguous=2]
CLASSIFIER_CLASSES = ["foreign", "legit", "ambiguous"]


def extract_crops(split: str = "train", crop_size: int = 32) -> tuple[list, list]:
    """Extract object crops from images using polygon/bbox annotations."""
    img_dir = DATASET_DIR / split / "images"
    lbl_dir = DATASET_DIR / split / "labels"

    crops = []
    labels = []

    for lbl_path in sorted(lbl_dir.glob("*.txt")):
        img_name = lbl_path.stem + ".jpg"
        img_path = img_dir / img_name
        if not img_path.exists():
            img_name = lbl_path.stem + ".png"
            img_path = img_dir / img_name
        if not img_path.exists():
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            continue

        h, w = img.shape[:2]
        content = lbl_path.read_text().strip()
        if not content:
            continue

        for line in content.split("\n"):
            parts = line.strip().split()
            if len(parts) < 3:
                continue

            cls_id = int(parts[0])
            coords = [float(x) for x in parts[1:]]

            if len(coords) > 4:
                # Segmentation polygon — compute bounding box from polygon points
                xs = [coords[i] * w for i in range(0, len(coords), 2)]
                ys = [coords[i] * h for i in range(1, len(coords), 2)]
                x1 = max(0, int(min(xs)))
                y1 = max(0, int(min(ys)))
                x2 = min(w, int(max(xs)))
                y2 = min(h, int(max(ys)))
            elif len(coords) == 4:
                # Standard bbox: cx, cy, bw, bh (normalized)
                cx, cy, bw, bh = coords
                x1 = max(0, int((cx - bw / 2) * w))
                y1 = max(0, int((cy - bh / 2) * h))
                x2 = min(w, int((cx + bw / 2) * w))
                y2 = min(h, int((cy + bh / 2) * h))
            else:
                continue

            crop_w = x2 - x1
            crop_h = y2 - y1
            if crop_w < 8 or crop_h < 8:
                continue

            crop = img[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            crop_resized = cv2.resize(crop, (crop_size, crop_size), interpolation=cv2.INTER_AREA)
            zs_label = ROBOFLOW_TO_ZONESHIELD.get(cls_id, 0)

            crops.append(crop_resized)
            labels.append(zs_label)

    return crops, labels


def augment_crop(crop: np.ndarray) -> np.ndarray:
    """Apply random augmentation to a crop."""
    h, w = crop.shape[:2]
    aug = crop.copy()

    # Random horizontal flip
    if random.random() > 0.5:
        aug = cv2.flip(aug, 1)

    # Random vertical flip
    if random.random() > 0.5:
        aug = cv2.flip(aug, 0)

    # Random rotation (90° increments)
    k = random.randint(0, 3)
    if k > 0:
        aug = np.rot90(aug, k)

    # Random brightness
    if random.random() > 0.3:
        delta = random.randint(-40, 40)
        aug = np.clip(aug.astype(np.int16) + delta, 0, 255).astype(np.uint8)

    # Random contrast
    if random.random() > 0.3:
        alpha = random.uniform(0.7, 1.3)
        aug = np.clip(aug.astype(np.float32) * alpha, 0, 255).astype(np.uint8)

    # Random Gaussian noise
    if random.random() > 0.5:
        noise = np.random.normal(0, 10, aug.shape).astype(np.int16)
        aug = np.clip(aug.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Random blur
    if random.random() > 0.7:
        ksize = random.choice([3, 5])
        aug = cv2.GaussianBlur(aug, (ksize, ksize), 0)

    return aug


def balance_classes(crops: list, labels: list, target_per_class: int = None) -> tuple[list, list]:
    """Oversample minority classes with augmentation."""
    from collections import Counter
    dist = Counter(labels)
    print(f"  Original distribution: {dict(dist)}")

    if target_per_class is None:
        target_per_class = max(dist.values())

    balanced_crops = []
    balanced_labels = []

    for cls_id in sorted(dist.keys()):
        cls_indices = [i for i, l in enumerate(labels) if l == cls_id]
        cls_crops = [crops[i] for i in cls_indices]

        # Keep all originals
        balanced_crops.extend(cls_crops)
        balanced_labels.extend([cls_id] * len(cls_crops))

        # Augment to reach target
        needed = target_per_class - len(cls_crops)
        for _ in range(needed):
            src = random.choice(cls_crops)
            aug = augment_crop(src)
            balanced_crops.append(aug)
            balanced_labels.append(cls_id)

    new_dist = Counter(balanced_labels)
    print(f"  Balanced distribution: {dict(new_dist)}")
    return balanced_crops, balanced_labels


def build_model_pytorch(num_classes: int = 3):
    """Build a simple CNN classifier using PyTorch."""
    import torch
    import torch.nn as nn

    class ConveyorClassifier(nn.Module):
        """Compact CNN for 32x32 crop classification.
        
        Architecture designed to be small enough for real-time inference
        via OpenCV DNN on CPU/ARM (Graviton).
        """
        def __init__(self, num_classes=3):
            super().__init__()
            self.features = nn.Sequential(
                # Block 1: 32x32x3 → 16x16x32
                nn.Conv2d(3, 32, 3, padding=1),
                nn.BatchNorm2d(32),
                nn.ReLU(inplace=True),
                nn.Conv2d(32, 32, 3, padding=1),
                nn.BatchNorm2d(32),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2),

                # Block 2: 16x16x32 → 8x8x64
                nn.Conv2d(32, 64, 3, padding=1),
                nn.BatchNorm2d(64),
                nn.ReLU(inplace=True),
                nn.Conv2d(64, 64, 3, padding=1),
                nn.BatchNorm2d(64),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2),

                # Block 3: 8x8x64 → 4x4x128
                nn.Conv2d(64, 128, 3, padding=1),
                nn.BatchNorm2d(128),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2),
            )
            self.classifier = nn.Sequential(
                nn.AdaptiveAvgPool2d(1),
                nn.Flatten(),
                nn.Dropout(0.3),
                nn.Linear(128, 64),
                nn.ReLU(inplace=True),
                nn.Dropout(0.2),
                nn.Linear(64, num_classes),
            )

        def forward(self, x):
            x = self.features(x)
            x = self.classifier(x)
            return x

    return ConveyorClassifier(num_classes)


def train_classifier(epochs: int = 30, lr: float = 0.001, batch_size: int = 32):
    """Train the lightweight crop classifier."""
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset

    print("\n" + "=" * 70)
    print("  ZoneShield AI — Crop Classifier Training")
    print("=" * 70)

    # Extract crops
    print("\n[1/6] Extracting crops from training set...")
    train_crops, train_labels = extract_crops("train")
    print(f"  Extracted {len(train_crops)} crops")

    print("\n[2/6] Extracting crops from validation set...")
    val_crops, val_labels = extract_crops("valid")
    print(f"  Extracted {len(val_crops)} crops")

    # Add synthetic "ambiguous" class from borderline crops
    print("\n[3/6] Generating ambiguous class samples...")
    n_ambiguous_train = max(50, len(train_crops) // 10)
    for _ in range(n_ambiguous_train):
        if len(train_crops) > 1:
            idx1, idx2 = random.sample(range(len(train_crops)), 2)
            # Create ambiguous sample by blending two different-class crops
            alpha = random.uniform(0.3, 0.7)
            blended = cv2.addWeighted(train_crops[idx1], alpha, train_crops[idx2], 1 - alpha, 0)
            # Add noise
            noise = np.random.normal(0, 15, blended.shape).astype(np.int16)
            blended = np.clip(blended.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            train_crops.append(blended)
            train_labels.append(2)  # ambiguous

    n_ambiguous_val = max(10, len(val_crops) // 10)
    for _ in range(n_ambiguous_val):
        if len(val_crops) > 1:
            idx1, idx2 = random.sample(range(len(val_crops)), 2)
            alpha = random.uniform(0.3, 0.7)
            blended = cv2.addWeighted(val_crops[idx1], alpha, val_crops[idx2], 1 - alpha, 0)
            val_crops.append(blended)
            val_labels.append(2)

    # Balance classes
    print("\n[4/6] Balancing classes...")
    train_crops, train_labels = balance_classes(train_crops, train_labels)

    # Convert to tensors
    def to_tensor(crops, labels):
        X = np.stack(crops).astype(np.float32) / 255.0  # [N, 32, 32, 3]
        X = X.transpose(0, 3, 1, 2)  # [N, 3, 32, 32] — NCHW
        y = np.array(labels, dtype=np.int64)
        return torch.from_numpy(X), torch.from_numpy(y)

    X_train, y_train = to_tensor(train_crops, train_labels)
    X_val, y_val = to_tensor(val_crops, val_labels)

    print(f"\n  Train: {X_train.shape[0]} samples | Val: {X_val.shape[0]} samples")

    train_ds = TensorDataset(X_train, y_train)
    val_ds = TensorDataset(X_val, y_val)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    # Build model
    print("\n[5/6] Training classifier...")
    model = build_model_pytorch(num_classes=3)
    device = torch.device("cpu")  # CPU training for this lightweight model
    model.to(device)

    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    print(f"  Model parameters: {total_params:,} ({total_params * 4 / 1024:.1f} KB FP32)")

    # Class-weighted loss to handle imbalance
    from collections import Counter
    dist = Counter(train_labels)
    total = sum(dist.values())
    weights = torch.tensor([total / (3 * dist.get(i, 1)) for i in range(3)], dtype=torch.float32)
    weights = weights / weights.sum() * 3  # Normalize
    print(f"  Class weights: {weights.tolist()}")

    criterion = nn.CrossEntropyLoss(weight=weights.to(device))
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=lr / 100)

    best_val_acc = 0.0
    best_epoch = 0
    patience = 10
    patience_counter = 0

    start_time = time.time()

    for epoch in range(1, epochs + 1):
        # Train
        model.train()
        train_loss = 0
        train_correct = 0
        train_total = 0

        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            optimizer.zero_grad()
            outputs = model(X_batch)
            loss = criterion(outputs, y_batch)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * X_batch.size(0)
            _, predicted = outputs.max(1)
            train_correct += predicted.eq(y_batch).sum().item()
            train_total += X_batch.size(0)

        scheduler.step()

        # Validate
        model.eval()
        val_loss = 0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch, y_batch = X_batch.to(device), y_batch.to(device)
                outputs = model(X_batch)
                loss = criterion(outputs, y_batch)
                val_loss += loss.item() * X_batch.size(0)
                _, predicted = outputs.max(1)
                val_correct += predicted.eq(y_batch).sum().item()
                val_total += X_batch.size(0)

        train_acc = train_correct / train_total * 100
        val_acc = val_correct / val_total * 100
        avg_train_loss = train_loss / train_total
        avg_val_loss = val_loss / val_total

        if epoch % 5 == 0 or epoch == 1 or val_acc > best_val_acc:
            lr_current = scheduler.get_last_lr()[0]
            print(f"  Epoch {epoch:3d}/{epochs} | "
                  f"Train Loss: {avg_train_loss:.4f} Acc: {train_acc:.1f}% | "
                  f"Val Loss: {avg_val_loss:.4f} Acc: {val_acc:.1f}% | "
                  f"LR: {lr_current:.6f}"
                  + (" *BEST*" if val_acc > best_val_acc else ""))

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch = epoch
            patience_counter = 0
            # Save best model
            torch.save(model.state_dict(), str(OUTPUT_DIR / "classifier_best.pth"))
        else:
            patience_counter += 1
            if patience_counter >= patience and epoch > 15:
                print(f"\n  Early stopping at epoch {epoch} (no improvement for {patience} epochs)")
                break

    elapsed = time.time() - start_time
    print(f"\n  Training complete in {elapsed:.1f}s")
    print(f"  Best validation accuracy: {best_val_acc:.1f}% at epoch {best_epoch}")

    # Load best model and export to ONNX
    print("\n[6/6] Exporting to ONNX...")
    model.load_state_dict(torch.load(str(OUTPUT_DIR / "classifier_best.pth"), weights_only=True))
    model.eval()

    export_to_onnx(model)

    return best_val_acc


def export_to_onnx(model):
    """Export PyTorch model to ONNX compatible with OpenCV DNN."""
    import torch

    model.eval()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Dummy input: [1, 3, 32, 32]
    dummy_input = torch.randn(1, 3, 32, 32)

    onnx_path = OUTPUT_DIR / "classifier.onnx"

    torch.onnx.export(
        model,
        dummy_input,
        str(onnx_path),
        export_params=True,
        opset_version=12,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes=None,  # Static shape for OpenCV DNN
    )

    # Verify file size
    size_kb = onnx_path.stat().st_size / 1024
    print(f"\n  ONNX exported: {onnx_path}")
    print(f"  Model size: {size_kb:.1f} KB")

    # Validate with OpenCV DNN
    try:
        net = cv2.dnn.readNetFromONNX(str(onnx_path))

        # Test inference
        test_crop = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
        blob = cv2.dnn.blobFromImage(
            test_crop, scalefactor=1.0 / 255.0,
            size=(32, 32), mean=(0, 0, 0),
            swapRB=False, crop=False,
        )
        net.setInput(blob)
        output = net.forward()
        probs = output[0]

        # Apply softmax
        exp_probs = np.exp(probs - np.max(probs))
        softmax_probs = exp_probs / exp_probs.sum()

        print(f"\n  OpenCV DNN validation: SUCCESS")
        print(f"  Test output (raw):    {probs}")
        print(f"  Test output (softmax): foreign={softmax_probs[0]:.3f}, "
              f"legit={softmax_probs[1]:.3f}, ambiguous={softmax_probs[2]:.3f}")
        print(f"\n  [OK] classifier.onnx is ready for the ZoneShield pipeline!")
        print(f"       Loaded by: vision/zoneshield/pipeline.py → Classify stage")
    except Exception as e:
        print(f"\n  [!] OpenCV DNN validation failed: {e}")
        print(f"      The ONNX was exported but may need a compatible OpenCV version.")

    return onnx_path


def main():
    parser = argparse.ArgumentParser(description="ZoneShield Crop Classifier Training")
    parser.add_argument("--epochs", type=int, default=40, help="Training epochs")
    parser.add_argument("--lr", type=float, default=0.001, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    import torch
    torch.manual_seed(args.seed)

    train_classifier(epochs=args.epochs, lr=args.lr, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
