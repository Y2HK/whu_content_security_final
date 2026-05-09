import logging
import threading

import numpy as np

from app.core.config import settings
from app.core.insightface_compat import (
    has_onnx_files,
    migrate_legacy_pack_dir,
    patch_face_analysis_model_root,
    preload_onnxruntime_dlls,
)

logger = logging.getLogger(__name__)


class FacePipeline:
    """InsightFace 单例引擎：检测 + 特征提取 + 内存人脸库"""

    _instance: "FacePipeline | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "FacePipeline":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    obj = super().__new__(cls)
                    obj._app = None
                    obj._gallery: dict[int, np.ndarray] = {}
                    obj._gallery_lock = threading.Lock()
                    obj._inference_lock = threading.Lock()
                    cls._instance = obj
        return cls._instance

    def _ensure_model(self) -> None:
        if self._app is not None:
            return

        from insightface.app import FaceAnalysis
        import onnxruntime as ort

        patch_face_analysis_model_root()
        preload_onnxruntime_dlls()
        model_dir = str(settings.MODEL_DIR)
        pack_dir = migrate_legacy_pack_dir(model_dir, "buffalo_l")
        if not has_onnx_files(pack_dir):
            logger.warning("模型未下载，首次加载将自动下载 buffalo_l 到 %s", model_dir)

        available = ort.get_available_providers()
        if "CUDAExecutionProvider" in available:
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            ctx_id = 0
            logger.info("人脸引擎使用 CUDA GPU 推理")
        elif "DmlExecutionProvider" in available:
            providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
            ctx_id = 0
            logger.info("人脸引擎使用 DirectML GPU 推理")
        else:
            providers = ["CPUExecutionProvider"]
            ctx_id = -1
            logger.info("人脸引擎使用 CPU 推理")

        self._app = FaceAnalysis(name="buffalo_l", root=model_dir, providers=providers)
        self._app.prepare(ctx_id=ctx_id, det_thresh=0.5, det_size=(640, 640))
        logger.info("人脸引擎初始化完成")

    # ---- 检测 / 特征提取 ----

    def detect_faces(self, img: np.ndarray) -> list:
        self._ensure_model()
        with self._inference_lock:
            return self._app.get(img)

    def extract_embedding(self, img: np.ndarray) -> np.ndarray | None:
        """从图像提取 ArcFace 512 维归一化特征向量；未检测到人脸返回 None"""
        self._ensure_model()
        with self._inference_lock:
            faces = self._app.get(img)
        if not faces:
            return None
        return faces[0].normed_embedding

    def extract_all_embeddings(self, img: np.ndarray) -> list[np.ndarray]:
        """从图像提取所有人脸的归一化特征向量"""
        self._ensure_model()
        with self._inference_lock:
            faces = self._app.get(img)
        return [f.normed_embedding for f in faces if f.normed_embedding is not None]

    # ---- 相似度 ----

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b))

    # ---- 内存人脸库 ----

    def load_gallery(self, features: dict[int, np.ndarray]) -> None:
        with self._gallery_lock:
            self._gallery = dict(features)

    def add_to_gallery(self, student_id: int, embedding: np.ndarray) -> None:
        with self._gallery_lock:
            self._gallery[student_id] = embedding

    def remove_from_gallery(self, student_id: int) -> None:
        with self._gallery_lock:
            self._gallery.pop(student_id, None)

    def match_1_to_N(self, embedding: np.ndarray, threshold: float = 0.6) -> tuple[int | None, float]:
        """1:N 余弦比对，返回 (student_id, confidence)"""
        with self._gallery_lock:
            if not self._gallery:
                return None, 0.0
            gallery_ids = list(self._gallery.keys())
            gallery_matrix = np.stack([self._gallery[sid] for sid in gallery_ids])
        scores = np.dot(gallery_matrix, embedding)
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])
        if best_score < threshold:
            return None, best_score
        return gallery_ids[best_idx], best_score

    @property
    def gallery_size(self) -> int:
        with self._gallery_lock:
            return len(self._gallery)


def get_pipeline() -> FacePipeline:
    return FacePipeline()
