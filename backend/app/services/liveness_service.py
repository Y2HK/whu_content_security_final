import logging
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class LivenessEngine:
    def __init__(self) -> None:
        self.model_type: str = "none"
        self.model_loaded: bool = False
        self._model: Any = None
        self._torch: Any = None
        self._transforms: Any = None
        self._onnx_session: Any = None

        if not settings.ENABLE_LIVENESS:
            logger.info("Liveness detection is disabled via ENABLE_LIVENESS=False.")
            return

        # Try loading models in order: custom -> minifasnet (onnx) -> cdcn -> silent_face
        self._try_load_custom()
        if not self.model_loaded:
            self._try_load_minifasnet()
        if not self.model_loaded:
            self._try_load_cdcn()
        if not self.model_loaded:
            self._try_load_silent_face()

        if self.model_loaded:
            logger.info("Liveness model loaded: type=%s", self.model_type)
        else:
            logger.warning(
                "No liveness model available. Predictions will default to is_live=False."
            )

    def _import_torch(self) -> bool:
        if self._torch is not None:
            return True
        try:
            import torch

            self._torch = torch
            return True
        except ImportError as exc:
            logger.warning("torch is not installed, cannot load PyTorch models: %s", exc)
            return False

    def _try_load_custom(self) -> None:
        if not self._import_torch():
            return
        path = settings.CUSTOM_MODEL_PATH
        if not path.exists():
            logger.debug("Custom model not found at %s", path)
            return
        try:
            model = self._torch.load(path, map_location="cpu", weights_only=False)
            if hasattr(model, "eval"):
                model.eval()
            self._model = model
            self.model_type = "custom"
            self.model_loaded = True
            logger.info("Custom liveness model loaded from %s", path)
        except Exception as exc:
            logger.warning("Failed to load custom model from %s: %s", path, exc)

    def _try_load_minifasnet(self) -> None:
        """Load MiniFASNet-V2 ONNX model for face anti-spoofing.

        Input: 128x128 RGB, pixel / 255 -> [0, 1], NCHW (1, 3, 128, 128) float32
        Output: 2-class logits [live, spoof]
        """
        path = settings.MINIFASNET_MODEL_PATH
        if not path.exists():
            logger.debug("MiniFASNet ONNX model not found at %s", path)
            return
        try:
            import onnxruntime as ort

            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            sess = ort.InferenceSession(str(path), providers=providers)
            self._onnx_session = sess
            self.model_type = "minifasnet"
            self.model_loaded = True
            logger.info("MiniFASNet ONNX liveness model loaded from %s", path)
        except ImportError as exc:
            logger.warning("onnxruntime is not installed, cannot load ONNX models: %s", exc)
        except Exception as exc:
            logger.warning("Failed to load MiniFASNet ONNX model from %s: %s", path, exc)

    def _try_load_cdcn(self) -> None:
        if not self._import_torch():
            return
        path = settings.CDCN_MODEL_PATH
        if not path.exists():
            logger.debug("CDCN model not found at %s", path)
            return
        try:
            model = self._torch.load(path, map_location="cpu", weights_only=False)
            if hasattr(model, "eval"):
                model.eval()
            self._model = model
            self.model_type = "cdcn"
            self.model_loaded = True
            logger.info("CDCN liveness model loaded from %s", path)
        except Exception as exc:
            logger.warning("Failed to load CDCN model from %s: %s", path, exc)

    def _try_load_silent_face(self) -> None:
        path = settings.SILENT_FACE_MODEL_PATH
        if not path.exists():
            logger.debug("Silent-Face model directory not found at %s", path)
            return
        try:
            from silent_face_anti_spoofing import AntiSpoofPredict

            model = AntiSpoofPredict(device_id=0)
            model._load_model(str(path))
            self._model = model
            self.model_type = "silent_face"
            self.model_loaded = True
            logger.info("Silent-Face liveness model loaded from %s", path)
        except ImportError as exc:
            logger.warning(
                "silent_face_anti_spoofing is not installed, cannot load Silent-Face model: %s",
                exc,
            )
        except Exception as exc:
            logger.warning("Failed to load Silent-Face model from %s: %s", path, exc)

    def _decode_image(self, image_input: bytes | np.ndarray) -> np.ndarray:
        if isinstance(image_input, np.ndarray):
            return image_input
        import cv2

        image_array = np.frombuffer(image_input, dtype=np.uint8)
        decoded = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if decoded is None:
            raise ValueError("无法解析输入图片")
        return decoded

    def _preprocess_custom_or_cdcn(self, image: np.ndarray) -> Any:
        import cv2

        if self._torch is None:
            raise RuntimeError("torch is not available")
        resized = cv2.resize(image, (256, 256))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        # normalize to [-1, 1]
        normalized = (rgb.astype(np.float32) / 255.0 - 0.5) / 0.5
        tensor = self._torch.from_numpy(normalized).permute(2, 0, 1).unsqueeze(0)
        return tensor

    def _preprocess_minifasnet(self, image: np.ndarray) -> np.ndarray:
        """Preprocess for MiniFASNet ONNX: 128x128 RGB, [0, 1], NCHW.

        Includes adaptive gamma correction for low-light images.
        """
        import cv2

        # Adaptive gamma correction for low-light images
        mean_val = float(image.mean())
        if mean_val < 80:  # Dark image
            gamma = max(0.3, min(1.0, mean_val / 127.0))
            lookup = np.array([((i / 255.0) ** gamma) * 255 for i in range(256)], dtype=np.uint8)
            image = cv2.LUT(image, lookup)
            logger.info("[LIVENESS PREP] Applied gamma correction: gamma=%.2f, mean_before=%.1f, mean_after=%.1f", gamma, mean_val, float(image.mean()))

        resized = cv2.resize(image, (128, 128))
        # Convert BGR -> RGB (model was trained on RGB)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        normalized = rgb.astype(np.float32) / 255.0
        # HWC -> NCHW
        nchw = np.transpose(normalized, (2, 0, 1))[np.newaxis, ...]
        return nchw

    def _infer_minifasnet(self, nchw: np.ndarray) -> float:
        """Run ONNX inference and return live probability.

        Output is 2-class logits: [live, spoof].
        Live probability = softmax(index=0).
        """
        if self._onnx_session is None:
            raise RuntimeError("ONNX session not available")
        input_name = self._onnx_session.get_inputs()[0].name
        output = self._onnx_session.run(None, {input_name: nchw})[0]
        logits = output[0]
        # Softmax
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        live_prob = float(probs[0])
        return live_prob

    def _preprocess_silent_face(self, image: np.ndarray) -> Any:
        import cv2

        # Silent-Face typically expects 80x80 or 128x128; try 80x80 first
        resized = cv2.resize(image, (80, 80))
        # The library usually handles color space internally; pass RGB tensor
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        normalized = rgb.astype(np.float32) / 255.0
        if self._torch is not None:
            tensor = self._torch.from_numpy(normalized).permute(2, 0, 1).unsqueeze(0)
        else:
            tensor = normalized[np.newaxis, ...]
        return tensor

    def _infer_custom_or_cdcn(self, tensor: Any) -> float:
        if self._torch is None or self._model is None:
            raise RuntimeError("Model or torch not available")
        with self._torch.no_grad():
            output = self._model(tensor)
            if isinstance(output, tuple):
                output = output[0]
            prob = float(self._torch.sigmoid(output).item())
        return prob

    def _infer_silent_face(self, image: np.ndarray) -> float:
        if self._model is None:
            raise RuntimeError("Model not available")
        # AntiSpoofPredict.get_bbox_landmks_img usually expects a numpy BGR image
        result = self._model.get_bbox_landmks_img(image)
        # result format varies; assume it returns a dict with "score" or we call predict
        # Fallback: if the library exposes predict, use it
        if hasattr(self._model, "predict"):
            pred = self._model.predict(image)
            if isinstance(pred, dict):
                live_prob = float(pred.get("live_prob", pred.get("score", 0.5)))
            elif isinstance(pred, (list, tuple)) and len(pred) >= 2:
                live_prob = float(pred[1])
            else:
                live_prob = float(pred)
            return live_prob
        # Heuristic fallback
        return 0.5

    def predict(self, image_input: bytes | np.ndarray) -> dict[str, Any]:
        if not settings.ENABLE_LIVENESS or self.model_type == "none":
            return {
                "is_live": False,
                "confidence": 0.0,
                "method": self.model_type,
                "model_loaded": self.model_loaded,
            }

        try:
            image = self._decode_image(image_input)
            logger.warning(
                "[LIVENESS INPUT DEBUG] shape=%s, dtype=%s, min=%.2f, max=%.2f, mean=%.2f",
                image.shape, image.dtype, float(image.min()), float(image.max()), float(image.mean()),
            )
        except Exception as exc:
            logger.warning("Failed to decode image for liveness detection: %s", exc)
            return {
                "is_live": False,
                "confidence": 0.0,
                "method": self.model_type,
                "model_loaded": self.model_loaded,
            }

        try:
            if self.model_type in ("custom", "cdcn"):
                tensor = self._preprocess_custom_or_cdcn(image)
                confidence = self._infer_custom_or_cdcn(tensor)
            elif self.model_type == "minifasnet":
                nchw = self._preprocess_minifasnet(image)
                confidence = self._infer_minifasnet(nchw)
            elif self.model_type == "silent_face":
                confidence = self._infer_silent_face(image)
            else:
                confidence = 1.0
        except Exception as exc:
            logger.warning("Liveness inference failed (%s): %s", self.model_type, exc)
            return {
                "is_live": False,
                "confidence": 0.0,
                "method": self.model_type,
                "model_loaded": self.model_loaded,
            }

        is_live = confidence > settings.LIVENESS_THRESHOLD
        return {
            "is_live": bool(is_live),
            "confidence": float(confidence),
            "method": self.model_type,
            "model_loaded": self.model_loaded,
        }


liveness_engine = LivenessEngine()
