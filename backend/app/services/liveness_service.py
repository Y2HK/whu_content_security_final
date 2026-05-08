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

        if not settings.ENABLE_LIVENESS:
            logger.info("Liveness detection is disabled via ENABLE_LIVENESS=False.")
            return

        # Try loading models in order: custom -> cdcn -> silent_face
        self._try_load_custom()
        if not self.model_loaded:
            self._try_load_cdcn()
        if not self.model_loaded:
            self._try_load_silent_face()

        if self.model_loaded:
            logger.info("Liveness model loaded: type=%s", self.model_type)
        else:
            logger.warning(
                "No liveness model available. All predictions will fallback to is_live=True."
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
                "is_live": True,
                "confidence": 1.0,
                "method": self.model_type,
                "model_loaded": self.model_loaded,
            }

        try:
            image = self._decode_image(image_input)
        except Exception as exc:
            logger.warning("Failed to decode image for liveness detection: %s", exc)
            return {
                "is_live": True,
                "confidence": 1.0,
                "method": self.model_type,
                "model_loaded": self.model_loaded,
            }

        try:
            if self.model_type in ("custom", "cdcn"):
                tensor = self._preprocess_custom_or_cdcn(image)
                confidence = self._infer_custom_or_cdcn(tensor)
            elif self.model_type == "silent_face":
                confidence = self._infer_silent_face(image)
            else:
                confidence = 1.0
        except Exception as exc:
            logger.warning("Liveness inference failed (%s): %s", self.model_type, exc)
            return {
                "is_live": True,
                "confidence": 1.0,
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
