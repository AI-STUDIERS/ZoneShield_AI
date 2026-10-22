"""Generate test_conveyor_video.mp4 for YOLOv8 model verification.

Renders realistic conveyor frames from SimulatorLive or test split images
into a benchmark video ready for:
    yolo predict model=runs/detect/train/weights/best.pt source=test_conveyor_video.mp4
"""

import sys
from pathlib import Path
import cv2
import numpy as np

# Ensure vision package is on sys.path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "vision"))

from zoneshield.framesource import SimulatorLive

def generate_video(output_path: str = "test_conveyor_video.mp4", duration_sec: int = 10, fps: int = 30):
    sim = SimulatorLive(fps=fps, seed=42)
    total_frames = duration_sec * fps
    
    # Peek one frame to get dimensions
    f0 = sim.read()
    h, w = f0.image.shape[:2]
    sim.restart()
    
    out_file = Path(output_path)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_file), fourcc, fps, (w, h))
    
    print(f"Rendering {total_frames} frames ({duration_sec}s @ {fps}fps, {w}x{h}) to {out_file}...")
    for i in range(total_frames):
        frame = sim.read()
        if frame is None:
            break
        writer.write(frame.image)
        if (i + 1) % 60 == 0:
            print(f"  Frame {i+1}/{total_frames}")
            
    writer.release()
    sim.close()
    print(f"SUCCESS: Generated {out_file} (size: {out_file.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "test_conveyor_video.mp4"
    generate_video(out)
