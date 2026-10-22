# 🛡️ ZoneShield AI — AWS Graviton + COOL Deployment & Model Training Guide
**OpenCV AI Competition 2026 | Powered by AWS**

This guide documents the exact end-to-end execution flow for training and verifying the YOLOv8 conveyor model on an **AWS Graviton (m8g / m9g / c7g)** instance pre-loaded with the **Cloud Optimized OpenCV Library (COOL)**.

---

## Step 1: Launch Graviton Instance from AWS Marketplace

1. Navigate to **AWS Marketplace** in the AWS Console.
2. Search for: **`Cloud Optimized OpenCV Library (COOL)`**.
3. Select the official AMI built for **AWS Graviton4 / Graviton3**:
   - **OS:** Ubuntu 24.04 LTS (arm64)
   - **Pre-installed:** OpenCV 5.1.0 + Python 3.12 (with Arm KleidiCV & NEON vector acceleration)
4. Launch EC2 instance:
   - **Instance Family:** `m8g.xlarge` (Graviton4) or `m9g` / `c7g.xlarge` (Graviton3)
   - **Storage:** 40 GB gp3 root volume
   - **Security Group:** SSH (port 22) + Web Dashboard (port 8000)

---

## Step 2: Set Up Repository on Graviton

SSH into your Graviton instance:
```bash
ssh -i your-key.pem ubuntu@<your-ec2-ip>
```

Clone the repository and set up environment:
```bash
# 1. Clone repository
git clone https://github.com/YOUR_ORG/ZoneShield_AI.git
cd ZoneShield_AI

# 2. Install Python dependencies
pip install -r requirements.txt ultralytics onnx

# 3. Pull conveyor dataset into workspace
python download_data.py
# (Or enter your Roboflow API key when prompted, or pass --local if copied)
```

The dataset will be validated and staged at `./dataset/` with an updated `./dataset/data.yaml`.

---

## Step 3: Train and Export the Model

Initiate YOLOv8n training (50 epochs, 640x640):
```bash
yolo train data=./dataset/data.yaml model=yolov8n.pt epochs=50 imgsz=640 batch=16
```

Once training completes, export weights to ONNX for OpenCV 5 DNN ingestion:
```bash
yolo export model=runs/detect/train/weights/best.pt format=onnx imgsz=640 opset=12
```

Copy best model to the ZoneShield data directory:
```bash
cp runs/detect/train/weights/best.onnx data/conveyor_yolov8_best.onnx
```

---

## Step 4: Verify Compliance & Verification Checklist

### A. Verify Architecture & COOL Acceleration (Constraints C2 & C3)
Run this command to prove OpenCV 5 and Arm KleidiCV acceleration are active:
```bash
python3 -c "import cv2; print(cv2.getBuildInformation())" | grep -E 'Baseline|Custom HAL'
```
**Expected Terminal Output:**
```
Custom HAL:                      YES (KleidiCV)
CPU/HW features:
  Baseline:                      NEON FP16
```
Run the automated self-check proof generator:
```bash
python -m zoneshield.selfcheck
# Emits PASS and records proof to data/cool_proof.json
```

### B. Verify Model Learning
During training, monitor the progress table:
- Watch the **`mAP50(B)`** and **`mAP50-95(B)`** columns.
- As epochs progress, `mAP50` will climb steadily toward **0.80 – 0.95**, proving the model distinguishes cardboard boxes and conveyor boundaries from anomalies.

### C. Verify Vision Pipeline on Video
Run inference on the simulated test conveyor video:
```bash
# If test_conveyor_video.mp4 is not already present, generate it with:
python scripts/generate_test_conveyor_video.py test_conveyor_video.mp4

# Run YOLO prediction
yolo predict model=runs/detect/train/weights/best.pt source=test_conveyor_video.mp4 conf=0.25 save=True
```
Review the annotated output video in `runs/detect/predict/test_conveyor_video.avi` to confirm detection accuracy, stable bounding boxes, and zero false-triggering on background texture.

---

## Step 5: Run Full Test Suite & Benchmark

Verify the entire ZoneShield AI system:
```bash
# Run all 81 unit tests (100% green)
pytest vision/tests -v

# Run 3-way benchmark comparison on Graviton
python -m benchmarks.run --suite default --reps 10 --out results/
```
