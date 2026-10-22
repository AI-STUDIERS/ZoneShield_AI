#!/usr/bin/env bash
set -e

echo "============================================================"
echo "  ZoneShield AI — AWS Graviton4 + COOL Setup & Validation"
echo "============================================================"

# 1. Architecture Check (KleidiCV & OpenCV 5)
echo "[1/5] Verifying OpenCV 5 and Arm KleidiCV acceleration..."
python3 -c "import cv2; print('OpenCV Version:', cv2.__version__)"
BUILD_CHECK=$(python3 -c "import cv2; print(cv2.getBuildInformation())" | grep -E 'Baseline|Custom HAL')
echo "$BUILD_CHECK"

if echo "$BUILD_CHECK" | grep -q "KleidiCV"; then
    echo ">>> KleidiCV Custom HAL: ACTIVE (COOL optimization verified)"
else
    echo ">>> WARNING: KleidiCV not detected in Custom HAL. Ensure you are running on the COOL AMI."
fi

# 2. Dependency Check & Installation
echo ""
echo "[2/5] Checking Python packages..."
pip install -r requirements.txt ultralytics onnx --quiet

# 3. Dataset Download
echo ""
echo "[3/5] Setting up conveyor dataset..."
if [ ! -d "./dataset/train" ]; then
    python3 download_data.py
else
    echo "Dataset already present in ./dataset/"
fi

# 4. Generate Test Conveyor Video
echo ""
echo "[4/5] Preparing test conveyor video..."
if [ ! -f "test_conveyor_video.mp4" ]; then
    python3 scripts/generate_test_conveyor_video.py test_conveyor_video.mp4
else
    echo "test_conveyor_video.mp4 already present."
fi

# 5. Run Selfcheck & Unit Tests
echo ""
echo "[5/5] Executing selfcheck and test suite..."
python3 -m vision.zoneshield.selfcheck
pytest vision/tests -q

echo ""
echo "============================================================"
echo "  System Ready for YOLOv8 Training!"
echo "  Run: yolo train data=./dataset/data.yaml model=yolov8n.pt epochs=50 imgsz=640"
echo "============================================================"
