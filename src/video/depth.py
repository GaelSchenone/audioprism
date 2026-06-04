"""Live monocular depth estimation (ONNX, CPU) on a worker thread.

Two interchangeable backends:
  - 'midas'          MiDaS v2.1 small, 256x256   (~8 fps on a Ryzen 5 3500C)
  - 'depth_anything' Depth Anything V2 small, 518 (~0.4 fps on CPU — needs a GPU)

The worker consumes the latest webcam frame and publishes a normalized depth map
(0 = far, 1 = near). Models download on demand to a gitignored models/ dir.
"""

from __future__ import annotations

import threading
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

_MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)

MODELS: dict[str, dict] = {
    "midas": {
        "file": "midas_small.onnx",
        "url": "https://github.com/isl-org/MiDaS/releases/download/v2_1/model-small.onnx",
        "size": 256,
    },
    "depth_anything": {
        "file": "depth_anything_v2_small.onnx",
        "url": "https://github.com/fabio-sim/Depth-Anything-ONNX/releases/download/v2.0.0/depth_anything_v2_vits.onnx",
        "size": 518,
    },
}

DEFAULT_MODEL = "midas"


def _ensure_model(cfg: dict) -> str:
    _MODELS_DIR.mkdir(exist_ok=True)
    path = _MODELS_DIR / cfg["file"]
    if not path.exists():
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(cfg["url"], tmp)
        tmp.rename(path)
    return str(path)


class DepthEstimator:
    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        if model not in MODELS:
            model = DEFAULT_MODEL
        self.model = model
        cfg = MODELS[model]
        self.size = cfg["size"]

        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        so.intra_op_num_threads = 4              # physical cores — best on this CPU
        self.sess = ort.InferenceSession(
            _ensure_model(cfg), sess_options=so, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.sess.get_inputs()[0].name

    def infer(self, rgb: np.ndarray) -> np.ndarray:
        """RGB frame (HxWx3 uint8) → normalized depth (size x size float, 1=near)."""
        img = cv2.resize(rgb, (self.size, self.size)).astype(np.float32) / 255.0
        img = (img - _IMAGENET_MEAN) / _IMAGENET_STD
        x = np.ascontiguousarray(img.transpose(2, 0, 1)[None])      # 1,3,H,W
        out = self.sess.run(None, {self.input_name: x})[0][0]       # HxW inverse depth
        lo, hi = float(out.min()), float(out.max())
        return ((out - lo) / (hi - lo + 1e-6)).astype(np.float32)


class DepthWorker:
    """Runs depth inference on the latest frame in a background thread."""

    def __init__(self, frame_getter, model: str = DEFAULT_MODEL) -> None:
        self.frame_getter = frame_getter
        self.estimator = DepthEstimator(model)
        self.latest_depth: np.ndarray | None = None
        self.fps = 0.0
        self.error: str | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    @property
    def model(self) -> str:
        return self.estimator.model

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while self._running:
            frame = self.frame_getter()
            if frame is None:
                time.sleep(0.03)
                continue
            try:
                t = time.time()
                depth = self.estimator.infer(frame)
                dt = time.time() - t
            except Exception as e:  # noqa: BLE001
                self.error = str(e)
                time.sleep(0.1)
                continue
            with self._lock:
                self.latest_depth = depth
                self.fps = 1.0 / dt if dt > 0 else 0.0

    def read(self) -> tuple[np.ndarray | None, float]:
        with self._lock:
            return self.latest_depth, self.fps

    def set_model(self, model: str) -> None:
        if model == self.estimator.model:
            return
        self.stop()
        self.estimator = DepthEstimator(model)
        with self._lock:
            self.latest_depth = None
        self.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
