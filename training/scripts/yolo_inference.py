"""
ZoneShield AI — YOLOv8 ONNX Inference Engine for OpenCV DNN
=============================================================
Runs the trained YOLOv8 segmentation model through OpenCV DNN,
replacing/augmenting the classical contour-based detection pipeline.

This bridges the YOLOv8 training output into the existing ZoneShield
pipeline.PipelineContext flow.

Usage as standalone:
    python yolo_inference.py --model data/conveyor_yolov8_best.onnx --source test_image.jpg

Usage in pipeline:
    from training.scripts.yolo_inference import YOLOv8Detector
    detector = YOLOv8Detector("data/conveyor_yolov8_best.onnx")
    detections = detector.detect(frame)
"""

import argparse
import os
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


class YOLOv8Detector:
    """YOLOv8 ONNX detector using OpenCV DNN backend.
    
    Designed for the ZoneShield conveyor belt detection pipeline.
    Handles both detection (bbox) and segmentation (mask) outputs.
    """

    # Class mapping from training
    CLASS_NAMES = {0: "cardboard_box", 1: "conveyor", 2: "kartonbox"}
    
    # Map YOLOv8 classes to ZoneShield pipeline classes
    ZONESHIELD_CLASS_MAP = {
        "cardboard_box": "foreign",    # Foreign object on conveyor
        "conveyor": "legit",            # The conveyor belt itself (legitimate)
        "kartonbox": "foreign",         # Foreign carton box
    }

    def __init__(
        self,
        model_path: str,
        conf_threshold: float = 0.25,
        nms_threshold: float = 0.45,
        input_size: int = 640,
        backend: int = cv2.dnn.DNN_BACKEND_OPENCV,
        target: int = cv2.dnn.DNN_TARGET_CPU,
    ):
        """
        Args:
            model_path: Path to ONNX model file
            conf_threshold: Minimum confidence for detection
            nms_threshold: NMS IoU threshold
            input_size: Model input size (usually 640)
            backend: OpenCV DNN backend
            target: OpenCV DNN target device
        """
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")

        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        self.input_size = input_size
        self.model_path = model_path

        # Load ONNX model
        self.net = cv2.dnn.readNetFromONNX(model_path)
        self.net.setPreferableBackend(backend)
        self.net.setPreferableTarget(target)

        # Get output layer info
        self.output_names = self.net.getUnconnectedOutLayersNames()
        
        self._warm_up()

    def _warm_up(self):
        """Run one inference pass to initialize the network."""
        dummy = np.zeros((self.input_size, self.input_size, 3), dtype=np.uint8)
        try:
            self._raw_inference(dummy)
        except Exception:
            pass  # Warm-up failure is non-fatal

    def _preprocess(self, frame: np.ndarray) -> tuple[np.ndarray, float, float, int, int]:
        """Preprocess frame for YOLOv8 inference.
        
        Returns:
            blob: Preprocessed blob for DNN
            ratio: Scale ratio
            dw, dh: Padding offsets
        """
        h, w = frame.shape[:2]
        
        # Calculate scale ratio (letterbox)
        ratio = min(self.input_size / h, self.input_size / w)
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        
        # Resize
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Pad to square
        dw = (self.input_size - new_w) // 2
        dh = (self.input_size - new_h) // 2
        padded = cv2.copyMakeBorder(
            resized, dh, self.input_size - new_h - dh,
            dw, self.input_size - new_w - dw,
            cv2.BORDER_CONSTANT, value=(114, 114, 114),
        )
        
        # Create blob
        blob = cv2.dnn.blobFromImage(
            padded, scalefactor=1.0 / 255.0,
            size=(self.input_size, self.input_size),
            mean=(0, 0, 0), swapRB=True, crop=False,
        )
        
        return blob, ratio, dw, dh

    def _raw_inference(self, frame: np.ndarray) -> list[np.ndarray]:
        """Run raw inference, return network outputs."""
        blob, _, _, _ = self._preprocess(frame)
        self.net.setInput(blob)
        outputs = self.net.forward(self.output_names)
        return outputs

    def detect(self, frame: np.ndarray) -> list[dict]:
        """Run detection on a frame.
        
        Args:
            frame: BGR image (numpy array)
            
        Returns:
            List of detections, each containing:
                - bbox: [x, y, w, h] in original frame coordinates
                - centroid: [cx, cy] center point
                - area: bounding box area
                - class: YOLOv8 class name
                - class_id: YOLOv8 class index
                - confidence: detection confidence
                - zoneshield_class: mapped class for ZoneShield pipeline
                - class_probs: probability dict for pipeline compatibility
                - dnn_accelerated: True (always, since this uses DNN)
                - mask: segmentation mask (if available)
        """
        start_ms = time.perf_counter() * 1000

        h_orig, w_orig = frame.shape[:2]
        blob, ratio, dw, dh = self._preprocess(frame)

        # Inference
        self.net.setInput(blob)
        outputs = self.net.forward(self.output_names)

        inference_ms = time.perf_counter() * 1000 - start_ms

        # Parse YOLOv8 output format
        # YOLOv8 detection output shape: [1, 4+nc, num_predictions]
        # YOLOv8 segmentation output: [1, 4+nc+nm, num_predictions] + [1, nm, mask_h, mask_w]
        
        detections = self._parse_outputs(outputs, h_orig, w_orig, ratio, dw, dh, frame)

        # Add timing
        for det in detections:
            det["inference_ms"] = inference_ms

        return detections

    def _parse_outputs(
        self, outputs: list[np.ndarray],
        h_orig: int, w_orig: int,
        ratio: float, dw: int, dh: int,
        frame: np.ndarray,
    ) -> list[dict]:
        """Parse YOLOv8 network outputs into structured detections."""
        
        nc = len(self.CLASS_NAMES)
        detections = []

        # Handle different output formats
        if len(outputs) == 1:
            # Detection-only output: [1, 4+nc, N]
            output = outputs[0]
            if output.ndim == 3:
                output = output[0]  # Remove batch dim → [4+nc, N]
            
            if output.shape[0] == 4 + nc:
                # Already in [features, predictions] format
                pass
            elif output.shape[1] == 4 + nc:
                output = output.T  # Transpose to [features, predictions]
            else:
                # Unknown format, try transposing
                if output.shape[0] < output.shape[1]:
                    pass  # [features, predictions] — correct
                else:
                    output = output.T
            
            return self._parse_detection_output(output, nc, h_orig, w_orig, ratio, dw, dh)

        elif len(outputs) == 2:
            # Segmentation output: det_output + mask_protos
            det_output = outputs[0]
            mask_protos = outputs[1]  # [1, nm, mask_h, mask_w]
            
            if det_output.ndim == 3:
                det_output = det_output[0]
            if mask_protos.ndim == 4:
                mask_protos = mask_protos[0]
            
            if det_output.shape[0] < det_output.shape[1]:
                pass  # [features, predictions]
            else:
                det_output = det_output.T

            return self._parse_segmentation_output(
                det_output, mask_protos, nc, h_orig, w_orig, ratio, dw, dh, frame
            )

        return detections

    def _parse_detection_output(
        self, output: np.ndarray, nc: int,
        h_orig: int, w_orig: int,
        ratio: float, dw: int, dh: int,
    ) -> list[dict]:
        """Parse detection-only output."""
        # output shape: [4+nc, N]
        boxes_xywh = output[:4, :]  # [4, N] — cx, cy, w, h
        class_scores = output[4:4+nc, :]  # [nc, N]

        # Get max class score and class id per prediction
        class_ids = np.argmax(class_scores, axis=0)  # [N]
        max_scores = np.max(class_scores, axis=0)  # [N]

        # Filter by confidence
        mask = max_scores >= self.conf_threshold
        if not np.any(mask):
            return []

        boxes_xywh = boxes_xywh[:, mask].T  # [M, 4]
        class_ids = class_ids[mask]
        max_scores = max_scores[mask]
        class_scores_filtered = class_scores[:, mask].T  # [M, nc]

        # Convert xywh to xyxy for NMS
        boxes_xyxy = np.zeros_like(boxes_xywh)
        boxes_xyxy[:, 0] = boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2  # x1
        boxes_xyxy[:, 1] = boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2  # y1
        boxes_xyxy[:, 2] = boxes_xywh[:, 0] + boxes_xywh[:, 2] / 2  # x2
        boxes_xyxy[:, 3] = boxes_xywh[:, 1] + boxes_xywh[:, 3] / 2  # y2

        # NMS
        indices = cv2.dnn.NMSBoxes(
            boxes_xyxy.tolist(), max_scores.tolist(),
            self.conf_threshold, self.nms_threshold,
        )

        detections = []
        if len(indices) > 0:
            indices = indices.flatten()
            for i in indices:
                # Scale coordinates back to original image
                x1 = (boxes_xyxy[i, 0] - dw) / ratio
                y1 = (boxes_xyxy[i, 1] - dh) / ratio
                x2 = (boxes_xyxy[i, 2] - dw) / ratio
                y2 = (boxes_xyxy[i, 3] - dh) / ratio

                # Clip to image bounds
                x1 = max(0, min(x1, w_orig))
                y1 = max(0, min(y1, h_orig))
                x2 = max(0, min(x2, w_orig))
                y2 = max(0, min(y2, h_orig))

                w = x2 - x1
                h = y2 - y1
                cx = x1 + w / 2
                cy = y1 + h / 2

                cls_id = int(class_ids[i])
                cls_name = self.CLASS_NAMES.get(cls_id, f"class_{cls_id}")
                zs_class = self.ZONESHIELD_CLASS_MAP.get(cls_name, "ambiguous")

                # Build class probabilities for pipeline compatibility
                scores = class_scores_filtered[i]
                score_sum = scores.sum()
                class_probs = {}
                for j, name in self.CLASS_NAMES.items():
                    zs_name = self.ZONESHIELD_CLASS_MAP.get(name, "ambiguous")
                    class_probs[zs_name] = class_probs.get(zs_name, 0) + float(scores[j] / score_sum if score_sum > 0 else 1/len(self.CLASS_NAMES))

                detections.append({
                    "bbox": [float(x1), float(y1), float(w), float(h)],
                    "centroid": [float(cx), float(cy)],
                    "area": float(w * h),
                    "class": zs_class,
                    "class_id": cls_id,
                    "class_name": cls_name,
                    "confidence": float(max_scores[i]),
                    "class_probs": class_probs,
                    "dnn_accelerated": True,
                    "detector": "yolov8-onnx",
                })

        return detections

    def _parse_segmentation_output(
        self, det_output: np.ndarray, mask_protos: np.ndarray,
        nc: int, h_orig: int, w_orig: int,
        ratio: float, dw: int, dh: int,
        frame: np.ndarray,
    ) -> list[dict]:
        """Parse segmentation output with masks."""
        # det_output: [4+nc+nm, N]
        nm = mask_protos.shape[0]  # Number of mask coefficients
        
        boxes_xywh = det_output[:4, :]
        class_scores = det_output[4:4+nc, :]
        mask_coeffs = det_output[4+nc:4+nc+nm, :]  # [nm, N]

        class_ids = np.argmax(class_scores, axis=0)
        max_scores = np.max(class_scores, axis=0)

        mask = max_scores >= self.conf_threshold
        if not np.any(mask):
            return []

        boxes_xywh = boxes_xywh[:, mask].T
        class_ids = class_ids[mask]
        max_scores = max_scores[mask]
        class_scores_filtered = class_scores[:, mask].T
        mask_coeffs = mask_coeffs[:, mask].T  # [M, nm]

        # Convert xywh → xyxy
        boxes_xyxy = np.zeros_like(boxes_xywh)
        boxes_xyxy[:, 0] = boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2
        boxes_xyxy[:, 1] = boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2
        boxes_xyxy[:, 2] = boxes_xywh[:, 0] + boxes_xywh[:, 2] / 2
        boxes_xyxy[:, 3] = boxes_xywh[:, 1] + boxes_xywh[:, 3] / 2

        indices = cv2.dnn.NMSBoxes(
            boxes_xyxy.tolist(), max_scores.tolist(),
            self.conf_threshold, self.nms_threshold,
        )

        detections = []
        if len(indices) > 0:
            indices = indices.flatten()

            # Generate masks: mask_coeffs @ mask_protos → [M, mask_h, mask_w]
            mask_h, mask_w = mask_protos.shape[1], mask_protos.shape[2]
            protos_flat = mask_protos.reshape(nm, -1)  # [nm, mask_h*mask_w]

            for i in indices:
                # Compute mask for this detection
                mask_pred = (mask_coeffs[i] @ protos_flat).reshape(mask_h, mask_w)
                mask_pred = 1.0 / (1.0 + np.exp(-mask_pred))  # Sigmoid

                # Scale coordinates back to original image
                x1 = (boxes_xyxy[i, 0] - dw) / ratio
                y1 = (boxes_xyxy[i, 1] - dh) / ratio
                x2 = (boxes_xyxy[i, 2] - dw) / ratio
                y2 = (boxes_xyxy[i, 3] - dh) / ratio

                x1 = max(0, min(x1, w_orig))
                y1 = max(0, min(y1, h_orig))
                x2 = max(0, min(x2, w_orig))
                y2 = max(0, min(y2, h_orig))

                w = x2 - x1
                h = y2 - y1
                cx = x1 + w / 2
                cy = y1 + h / 2

                # Resize mask to original image size
                mask_resized = cv2.resize(mask_pred, (self.input_size, self.input_size))
                # Remove padding
                mask_cropped = mask_resized[dh:dh + int(h_orig * ratio), dw:dw + int(w_orig * ratio)]
                if mask_cropped.size > 0:
                    mask_final = cv2.resize(mask_cropped, (w_orig, h_orig))
                    mask_binary = (mask_final > 0.5).astype(np.uint8)
                else:
                    mask_binary = np.zeros((h_orig, w_orig), dtype=np.uint8)

                cls_id = int(class_ids[i])
                cls_name = self.CLASS_NAMES.get(cls_id, f"class_{cls_id}")
                zs_class = self.ZONESHIELD_CLASS_MAP.get(cls_name, "ambiguous")

                scores = class_scores_filtered[i]
                score_sum = scores.sum()
                class_probs = {}
                for j, name in self.CLASS_NAMES.items():
                    zs_name = self.ZONESHIELD_CLASS_MAP.get(name, "ambiguous")
                    class_probs[zs_name] = class_probs.get(zs_name, 0) + float(scores[j] / score_sum if score_sum > 0 else 1/len(self.CLASS_NAMES))

                detections.append({
                    "bbox": [float(x1), float(y1), float(w), float(h)],
                    "centroid": [float(cx), float(cy)],
                    "area": float(w * h),
                    "class": zs_class,
                    "class_id": cls_id,
                    "class_name": cls_name,
                    "confidence": float(max_scores[i]),
                    "class_probs": class_probs,
                    "dnn_accelerated": True,
                    "detector": "yolov8-onnx-seg",
                    "mask": mask_binary,
                })

        return detections

    def draw_detections(self, frame: np.ndarray, detections: list[dict], 
                        show_masks: bool = True) -> np.ndarray:
        """Draw detections on frame for visualization."""
        vis = frame.copy()

        colors = {
            "foreign": (0, 0, 255),     # Red
            "legit": (0, 255, 0),       # Green
            "ambiguous": (0, 165, 255), # Orange
        }

        for det in detections:
            x, y, w, h = [int(v) for v in det["bbox"]]
            cls = det["class"]
            conf = det["confidence"]
            color = colors.get(cls, (128, 128, 128))

            # Draw mask if available
            if show_masks and "mask" in det and det["mask"] is not None:
                mask = det["mask"]
                overlay = vis.copy()
                overlay[mask > 0] = color
                vis = cv2.addWeighted(vis, 0.7, overlay, 0.3, 0)

            # Draw bbox
            cv2.rectangle(vis, (x, y), (x + w, y + h), color, 2)

            # Label
            label = f"{det.get('class_name', cls)} {conf:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(vis, (x, y - th - 8), (x + tw + 4, y), color, -1)
            cv2.putText(vis, label, (x + 2, y - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return vis


def main():
    parser = argparse.ArgumentParser(description="ZoneShield YOLOv8 ONNX Inference")
    parser.add_argument("--model", required=True, help="Path to ONNX model")
    parser.add_argument("--source", required=True, help="Image or video path")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--nms", type=float, default=0.45, help="NMS threshold")
    parser.add_argument("--output", default="output", help="Output directory")
    args = parser.parse_args()

    detector = YOLOv8Detector(
        args.model,
        conf_threshold=args.conf,
        nms_threshold=args.nms,
    )

    os.makedirs(args.output, exist_ok=True)

    source = args.source
    if source.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
        # Single image
        frame = cv2.imread(source)
        if frame is None:
            print(f"Failed to read: {source}")
            return

        start = time.perf_counter()
        detections = detector.detect(frame)
        elapsed = (time.perf_counter() - start) * 1000

        print(f"\nDetections: {len(detections)} | Inference: {elapsed:.1f}ms")
        for det in detections:
            print(f"  {det['class_name']:15s} conf={det['confidence']:.3f} "
                  f"bbox=[{det['bbox'][0]:.0f},{det['bbox'][1]:.0f},"
                  f"{det['bbox'][2]:.0f},{det['bbox'][3]:.0f}] "
                  f"→ {det['class']}")

        vis = detector.draw_detections(frame, detections)
        out_path = os.path.join(args.output, f"det_{Path(source).stem}.jpg")
        cv2.imwrite(out_path, vis)
        print(f"Saved: {out_path}")

    else:
        # Video
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            print(f"Failed to open: {source}")
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        out_path = os.path.join(args.output, f"det_{Path(source).stem}.mp4")
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))

        frame_count = 0
        total_ms = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            detections = detector.detect(frame)
            total_ms += detections[0]["inference_ms"] if detections else 0
            frame_count += 1

            vis = detector.draw_detections(frame, detections)
            writer.write(vis)

            if frame_count % 30 == 0:
                avg_ms = total_ms / frame_count if frame_count > 0 else 0
                print(f"  Frame {frame_count}/{total} | Avg inference: {avg_ms:.1f}ms | "
                      f"Detections: {len(detections)}")

        cap.release()
        writer.release()
        print(f"\nProcessed {frame_count} frames → {out_path}")


if __name__ == "__main__":
    main()
