"""Train and export lightweight ONNX classifier for ZoneShield AI.

Generates a compact CNN model optimized for OpenCV 5 DNN engine inference
on foreign contaminant vs legitimate item crops.
Classes:
  0: foreign (contaminants, metal shavings, irregular objects)
  1: legit (standard packaged items, uniform color)
  2: ambiguous (shadowed, partial occlusion, borderline contrast)
"""

from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class ZoneShieldClassifierNet(nn.Module):
    """Compact 3-class CNN for conveyor object classification in OpenCV 5 DNN."""

    def __init__(self) -> None:
        super().__init__()
        # Input shape: [batch, 3, 32, 32]
        self.conv1 = nn.Conv2d(3, 16, kernel_size=3, padding=1)
        self.pool1 = nn.MaxPool2d(2, 2)  # -> [16, 16, 16]
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.pool2 = nn.AdaptiveAvgPool2d((4, 4))  # -> [32, 4, 4]
        self.fc1 = nn.Linear(32 * 4 * 4, 32)
        self.fc2 = nn.Linear(32, 3)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.conv1(x))
        x = self.pool1(x)
        x = F.relu(self.conv2(x))
        x = self.pool2(x)
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        x = F.softmax(x, dim=1)
        return x


def generate_synthetic_crops(n_samples: int = 600) -> tuple[torch.Tensor, torch.Tensor]:
    """Generate domain-randomized synthetic samples matching conveyor digital twin."""
    rng = np.random.default_rng(42)
    crops = []
    labels = []

    for _ in range(n_samples):
        cls_idx = rng.integers(0, 3)
        crop = np.zeros((3, 32, 32), dtype=np.float32)

        if cls_idx == 0:
            # Foreign: Green / high-variance contaminant or irregular dark shape
            crop[1, :, :] = rng.uniform(0.6, 1.0, (32, 32))  # G high
            crop[0, :, :] = rng.uniform(0.0, 0.3, (32, 32))  # B low
            crop[2, :, :] = rng.uniform(0.0, 0.3, (32, 32))  # R low
        elif cls_idx == 1:
            # Legit: Blue / cyan / uniform item
            crop[0, :, :] = rng.uniform(0.6, 1.0, (32, 32))  # B high
            crop[1, :, :] = rng.uniform(0.3, 0.6, (32, 32))  # G moderate
            crop[2, :, :] = rng.uniform(0.1, 0.4, (32, 32))  # R low
        else:
            # Ambiguous: Low contrast gray / near neutral or noise
            base = rng.uniform(0.3, 0.5)
            noise = rng.normal(0, 0.05, (3, 32, 32))
            crop = np.clip(base + noise, 0.0, 1.0)

        # Add random noise and illumination jitter
        jitter = rng.normal(0, 0.02, (3, 32, 32))
        crop = np.clip(crop + jitter, 0.0, 1.0).astype(np.float32)

        crops.append(crop)
        labels.append(cls_idx)

    return torch.tensor(np.array(crops)), torch.tensor(labels, dtype=torch.long)


def train_and_export(output_path: str = "data/classifier.onnx") -> str:
    """Train lightweight classifier and export to ONNX for OpenCV 5 DNN."""
    print("Generating training dataset with digital twin domain randomization...")
    x_train, y_train = generate_synthetic_crops(900)

    model = ZoneShieldClassifierNet()
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005)
    criterion = nn.CrossEntropyLoss()

    print("Training compact CNN classifier...")
    for epoch in range(12):
        optimizer.zero_grad()
        preds = model(x_train)
        loss = criterion(preds, y_train)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 4 == 0:
            acc = (preds.argmax(dim=1) == y_train).float().mean()
            print(f"  Epoch {epoch+1:02d} | Loss: {loss.item():.4f} | Accuracy: {acc * 100:.1f}%")

    model.eval()
    dummy_input = torch.randn(1, 3, 32, 32, dtype=torch.float32)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"Exporting ONNX model to {output_path}...")
    torch.onnx.export(
        model,
        dummy_input,
        str(out_file),
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["probabilities"],
        dynamic_axes={"input": {0: "batch_size"}, "probabilities": {0: "batch_size"}},
    )
    print(f"Successfully generated {output_path} (size: {out_file.stat().st_size} bytes)")
    return str(out_file)


if __name__ == "__main__":
    train_and_export()
