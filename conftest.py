"""Pytest configuration for ZoneShield AI."""
import sys
from pathlib import Path

# Ensure vision package is importable
vision_path = str(Path(__file__).resolve().parent / "vision")
if vision_path not in sys.path:
    sys.path.insert(0, vision_path)