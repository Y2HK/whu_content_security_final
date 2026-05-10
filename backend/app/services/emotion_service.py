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

FERPLUS_LABELS = [
    "neutral",
    "happy",
    "surprise",
    "sad",
    "angry",
    "disgust",
    "fear",
    "neutral",  # contempt is folded into neutral for this app's 7-class UI.
]

HSEMOTION_LABELS = [
    "angry",
    "neutral",  # contempt is folded into neutral for this app's 7-class UI.
    "disgust",
    "fear",
    "happy",
    "neutral",
    "sad",
    "surprise",
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
    raw_emotion: str | None = None
    scores: dict[str, float] | None = None


def _fallback_prediction(seed_text: str) -> EmotionPrediction:
    return EmotionPrediction(emotion="neutral", confidence=0.0, source="fallback", scores={"neutral": 0.0})


def _normalize_emotion(raw_emotion: str | None) -> str:
    if not raw_emotion:
        return "neutral"
    return DEEPFACE_EMOTION_MAP.get(raw_emotion.lower(), "neutral")


def _softmax(scores: Any) -> Any:
    import numpy as np

    values = np.asarray(scores, dtype=np.float32)
    values = values - np.max(values)
    exp_values = np.exp(values)
    return exp_values / np.sum(exp_values)


def _image_payload(image: bytes | str | Path | Any) -> Any:
    if isinstance(image, (str, Path)):
        return str(image)
    if hasattr(image, "shape"):
        return image

    import cv2
    import numpy as np

    image_array = np.frombuffer(image, dtype=np.uint8)
    decoded = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if decoded is None:
        raise ValueError("无法解析上传图片")
    return decoded


def _image_array(image: bytes | str | Path | Any) -> Any:
    import cv2
    import numpy as np

    payload = _image_payload(image)
    if isinstance(payload, str):
        image_bytes = np.fromfile(payload, dtype=np.uint8)
        decoded = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
        if decoded is None:
            raise ValueError(f"无法解析图片: {payload}")
        return decoded
    return payload


def _ferplus_input(image: bytes | str | Path | Any) -> Any:
    import cv2
    import numpy as np

    img = _image_array(image)
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    gray = cv2.equalizeHist(gray)
    resized = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
    return resized.astype(np.float32).reshape(1, 1, 64, 64)


@lru_cache(maxsize=1)
def _load_ferplus_session() -> Any | None:
    if not settings.ENABLE_EMOTION_MODEL:
        return None

    model_path = settings.FERPLUS_MODEL_PATH
    if not model_path.exists():
        logger.warning("FER+ emotion model is missing: %s", model_path)
        return None

    try:
        import onnxruntime as ort
    except Exception as exc:
        logger.warning("onnxruntime is unavailable for FER+ emotion model: %s", exc)
        return None

    try:
        return ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    except Exception as exc:
        logger.warning("Failed to load FER+ emotion model: %s", exc)
        return None


@lru_cache(maxsize=1)
def _load_hsemotion_session() -> Any | None:
    if not settings.ENABLE_EMOTION_MODEL:
        return None

    model_path = settings.HSEMOTION_MODEL_PATH
    if not model_path.exists():
        logger.warning("HSEmotion model is missing: %s", model_path)
        return None

    try:
        import onnxruntime as ort
    except Exception as exc:
        logger.warning("onnxruntime is unavailable for HSEmotion model: %s", exc)
        return None

    try:
        return ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    except Exception as exc:
        logger.warning("Failed to load HSEmotion model: %s", exc)
        return None


def _hsemotion_input(image: bytes | str | Path | Any) -> Any:
    import cv2
    import numpy as np

    img = _image_array(image)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    resized = cv2.resize(img, (224, 224), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    resized[..., 0] = (resized[..., 0] - 0.485) / 0.229
    resized[..., 1] = (resized[..., 1] - 0.456) / 0.224
    resized[..., 2] = (resized[..., 2] - 0.406) / 0.225
    return resized.transpose(2, 0, 1).astype(np.float32)[None, ...]


def _hsemotion_prediction(image: bytes | str | Path | Any) -> EmotionPrediction | None:
    session = _load_hsemotion_session()
    if session is None:
        return None

    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: _hsemotion_input(image)})
    probs = _softmax(outputs[0][0])
    best_index = int(probs.argmax())
    raw_emotion = HSEMOTION_LABELS[best_index]
    confidence = round(float(probs[best_index]), 4)
    emotion = raw_emotion
    score_map: dict[str, float] = {}
    for index, label in enumerate(HSEMOTION_LABELS):
        score_map[label] = max(score_map.get(label, 0.0), round(float(probs[index]), 4))

    if confidence < settings.EMOTION_MIN_CONFIDENCE:
        emotion = "neutral"

    return EmotionPrediction(
        emotion=emotion,
        confidence=confidence,
        source="hsemotion_onnx",
        raw_emotion=raw_emotion,
        scores=score_map,
    )


def _ferplus_prediction(image: bytes | str | Path | Any) -> EmotionPrediction | None:
    session = _load_ferplus_session()
    if session is None:
        return None

    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: _ferplus_input(image)})
    probs = _softmax(outputs[0][0])
    best_index = int(probs.argmax())
    raw_emotion = FERPLUS_LABELS[best_index]
    confidence = round(float(probs[best_index]), 4)
    emotion = raw_emotion
    score_map: dict[str, float] = {}
    for index, label in enumerate(FERPLUS_LABELS):
        score_map[label] = max(score_map.get(label, 0.0), round(float(probs[index]), 4))

    if confidence < settings.EMOTION_MIN_CONFIDENCE:
        emotion = "neutral"

    return EmotionPrediction(
        emotion=emotion,
        confidence=confidence,
        source="ferplus_onnx",
        raw_emotion=raw_emotion,
        scores=score_map,
    )


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


def _deepface_prediction(image: bytes | str | Path | Any) -> EmotionPrediction | None:
    DeepFace = _load_deepface()
    if DeepFace is None:
        return None

    payload = _image_payload(image)
    detector_backend = "skip" if hasattr(payload, "shape") else settings.EMOTION_DETECTOR_BACKEND
    result = DeepFace.analyze(
        img_path=payload,
        actions=["emotion"],
        enforce_detection=False,
        detector_backend=detector_backend,
        silent=True,
    )
    row = result[0] if isinstance(result, list) else result
    if not isinstance(row, dict):
        return None

    raw_emotion = row.get("dominant_emotion")
    emotion = _normalize_emotion(raw_emotion)
    confidence = _confidence_from_scores(row, raw_emotion or emotion)
    if confidence < settings.EMOTION_MIN_CONFIDENCE:
        emotion = "neutral"

    return EmotionPrediction(
        emotion=emotion,
        confidence=confidence,
        source="deepface",
        raw_emotion=_normalize_emotion(raw_emotion),
        scores={emotion: confidence},
    )


def _camera_calibrate_prediction(prediction: EmotionPrediction) -> EmotionPrediction:
    if prediction.confidence < settings.CAMERA_EMOTION_MIN_CONFIDENCE:
        return EmotionPrediction(
            emotion="neutral",
            confidence=prediction.confidence,
            source=f"{prediction.source}-camera-low-confidence",
            raw_emotion=prediction.raw_emotion or prediction.emotion,
            scores=prediction.scores,
        )
    return prediction


def _predict_once(image: bytes | str | Path | Any) -> EmotionPrediction | None:
    provider = settings.EMOTION_PROVIDER.lower()
    if provider == "hsemotion_onnx":
        return _hsemotion_prediction(image) or _ferplus_prediction(image) or _deepface_prediction(image)
    if provider == "ferplus_onnx":
        return _ferplus_prediction(image) or _deepface_prediction(image)
    if provider == "deepface":
        return _deepface_prediction(image)
    logger.warning("Unknown EMOTION_PROVIDER=%s, falling back to HSEmotion.", settings.EMOTION_PROVIDER)
    return _hsemotion_prediction(image) or _ferplus_prediction(image) or _deepface_prediction(image)


def analyze_image_emotion(
    image: bytes | str | Path | Any,
    fallback_seed: str = "emotion",
    camera_mode: bool = False,
) -> EmotionPrediction:
    try:
        prediction = _predict_once(image)
    except Exception as exc:
        logger.warning("Emotion analysis failed, fallback will be used: %s", exc)
        prediction = None

    if prediction is None:
        return _fallback_prediction(fallback_seed)
    return _camera_calibrate_prediction(prediction) if camera_mode else prediction


def analyze_image_emotions(
    image: bytes | str | Path | Any,
    count: int,
    fallback_seed: str = "emotion",
) -> list[EmotionPrediction]:
    prediction = analyze_image_emotion(image, fallback_seed=fallback_seed)
    return [prediction for _ in range(count)]


def analyze_emotion(seed_text: str) -> str:
    return _fallback_prediction(seed_text).emotion


def emotion_model_status() -> dict[str, Any]:
    hsemotion = _load_hsemotion_session()
    ferplus = _load_ferplus_session()
    return {
        "enabled": settings.ENABLE_EMOTION_MODEL,
        "provider": settings.EMOTION_PROVIDER,
        "available": hsemotion is not None or ferplus is not None,
        "hsemotion_available": hsemotion is not None,
        "hsemotion_model_path": str(settings.HSEMOTION_MODEL_PATH),
        "ferplus_available": ferplus is not None,
        "ferplus_model_path": str(settings.FERPLUS_MODEL_PATH),
        "fallback": "neutral",
        "emotions": EMOTIONS,
    }
