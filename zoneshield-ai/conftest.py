"""Pytest configuration for ZoneShield AI."""
import sys
from pathlib import Path

# Ensure vision and root packages are importable
root_path = str(Path(__file__).resolve().parent)
vision_path = str(Path(__file__).resolve().parent / "vision")

for p in (root_path, vision_path):
    if p not in sys.path:
        sys.path.insert(0, p)