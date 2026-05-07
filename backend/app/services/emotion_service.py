import hashlib
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

EMOTIONS = [
    "happy",
    "neutral",
    "surprise",
    "sad",
    "angry",
    "fear",
    "disgust",
]

DEEPFACE_EMOTION_MAP = {
    "angry": "angry",
    "disgust": "disgust",
    "fear": "fear",
    "happy": "happy",
    "sad": "sad",
    "surprise": "surprise",
    "neutral": "neutral",
}


@dataclass(frozen=True)
class EmotionPrediction:
    emotion: str
    confidence: float
    source: str


@lru_cache(maxsize=1)
def _load_deepface() -> Any | None:
    if not settings.ENABLE_EMOTION_MODEL:
        return None

    try:
        deepface_home = settings.MODEL_DIR / "deepface"
        deepface_home.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("DEEPFACE_HOME", str(deepface_home))

        from deepface import DeepFace
    except Exception as exc:
        logger.warning("DeepFace emotion model is unavailable: %s", exc)
        return None

    return DeepFace


def _fallback_prediction(seed_text: str) -> EmotionPrediction:
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(EMOTIONS)
    confidence = 0.55 + (int(digest[:4], 16) % 35) / 100
    return EmotionPrediction(emotion=EMOTIONS[index], confidence=round(min(confidence, 0.89), 4), source="fallback")


def _normalize_emotion(raw_emotion: str | None) -> str:
    if not raw_emotion:
        return "neutral"
    return DEEPFACE_EMOTION_MAP.get(raw_emotion.lower(), "neutral")


def _confidence_from_scores(result: dict[str, Any], emotion: str) -> float:
    scores = result.get("emotion") or {}
    score = scores.get(emotion, scores.get(emotion.lower(), 0.0))
    try:
        confidence = float(score)
    except (TypeError, ValueError):
        return 0.0

    if confidence > 1:
        confidence = confidence / 100
    return round(max(0.0, min(confidence, 1.0)), 4)


def _image_payload(image: bytes | str | Path) -> Any:
    if isinstance(image, (str, Path)):
        return str(image)

    import cv2
    import numpy as np

    image_array = np.frombuffer(image, dtype=np.uint8)
    decoded = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if decoded is None:
        raise ValueError("无法解析上传图片")
    return decoded


def _deepface_predictions(image: bytes | str | Path) -> list[EmotionPrediction]:
    DeepFace = _load_deepface()
    if DeepFace is None:
        return []

    result = DeepFace.analyze(
        img_path=_image_payload(image),
        actions=["emotion"],
        enforce_detection=False,
        detector_backend=settings.EMOTION_DETECTOR_BACKEND,
        silent=True,
    )
    rows = result if isinstance(result, list) else [result]
    predictions = []
    for row in rows:
        raw_emotion = row.get("dominant_emotion") if isinstance(row, dict) else None
        emotion = _normalize_emotion(raw_emotion)
        predictions.append(
            EmotionPrediction(
                emotion=emotion,
                confidence=_confidence_from_scores(row, raw_emotion or emotion) if isinstance(row, dict) else 0.0,
                source="deepface",
            )
        )
    return predictions


def analyze_image_emotion(image: bytes | str | Path, fallback_seed: str = "emotion") -> EmotionPrediction:
    try:
        predictions = _deepface_predictions(image)
    except Exception as exc:
        logger.warning("DeepFace emotion analysis failed, fallback will be used: %s", exc)
        predictions = []

    if predictions:
        return predictions[0]
    return _fallback_prediction(fallback_seed)


def analyze_image_emotions(image: bytes | str | Path, count: int, fallback_seed: str = "emotion") -> list[EmotionPrediction]:
    try:
        predictions = _deepface_predictions(image)
    except Exception as exc:
        logger.warning("DeepFace batch emotion analysis failed, fallback will be used: %s", exc)
        predictions = []

    if predictions:
        return [predictions[index % len(predictions)] for index in range(count)]

    return [_fallback_prediction(f"{fallback_seed}-{index}") for index in range(count)]


def analyze_emotion(seed_text: str) -> str:
    return _fallback_prediction(seed_text).emotion


def emotion_model_status() -> dict[str, Any]:
    model = _load_deepface()
    return {
        "enabled": settings.ENABLE_EMOTION_MODEL,
        "provider": "deepface",
        "available": model is not None,
        "detector_backend": settings.EMOTION_DETECTOR_BACKEND,
        "fallback": "deterministic-demo",
        "emotions": EMOTIONS,
    }
