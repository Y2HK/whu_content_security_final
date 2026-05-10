import base64
import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import UploadFile

from app.core.config import settings
from app.services.face_pipeline import get_pipeline

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecognizedFace:
    student: Any
    confidence: float
    bbox: tuple[int, int, int, int]
    face_crop: np.ndarray


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


async def save_upload_file(upload_file: UploadFile, destination: Path) -> Path:
    ensure_directory(destination.parent)
    contents = await upload_file.read()
    destination.write_bytes(contents)
    return destination


def _embedding_to_base64(embedding: np.ndarray) -> str:
    return base64.b64encode(embedding.astype(np.float32).tobytes()).decode("utf-8")


def _base64_to_embedding(feature_vector: str) -> np.ndarray | None:
    try:
        embedding = np.frombuffer(base64.b64decode(feature_vector), dtype=np.float32)
    except Exception:
        return None
    if embedding.shape[0] != 512:
        return None
    return embedding


def _read_image(image_path: str) -> np.ndarray | None:
    try:
        image_bytes = np.fromfile(image_path, dtype=np.uint8)
    except OSError:
        return None
    return cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)


def build_face_feature_from_path(image_path: str) -> str:
    image = _read_image(image_path)
    if image is None:
        raise ValueError(f"Unable to read image: {image_path}")

    embedding = get_pipeline().extract_embedding(image)
    if embedding is None:
        raise ValueError("No face detected in image")

    return _embedding_to_base64(embedding)


def match_student(students: list[Any], image_bytes: bytes) -> tuple[Any | None, float]:
    if not students:
        return None, 0.0

    image_array = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        return None, 0.0

    embedding = get_pipeline().extract_embedding(image)
    if embedding is None:
        return None, 0.0

    best_id, confidence = get_pipeline().match_1_to_N(
        embedding,
        threshold=settings.FACE_SIMILARITY_THRESHOLD,
    )
    if best_id is None:
        return None, confidence

    matched = next((student for student in students if student.student_id == best_id), None)
    return matched, confidence


def recognize_group(students: list[Any], image_path: str) -> list[tuple[Any, float]]:
    return [(item.student, item.confidence) for item in recognize_group_detailed(students, image_path)]


def _crop_bbox(image: np.ndarray, bbox: tuple[int, int, int, int], margin: float = 0.0) -> np.ndarray:
    x, y, width, height = bbox
    img_h, img_w = image.shape[:2]
    pad_x = int(width * margin)
    pad_y = int(height * margin)
    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(img_w, x + width + pad_x)
    y2 = min(img_h, y + height + pad_y)
    return image[y1:y2, x1:x2]


def recognize_group_detailed(students: list[Any], image_path: str) -> list[RecognizedFace]:
    if not students:
        return []

    image = _read_image(image_path)
    if image is None:
        return []

    detected_faces = get_pipeline().extract_all_detected_faces(image)
    if not detected_faces:
        return []

    student_map = {student.student_id: student for student in students}
    results: list[RecognizedFace] = []
    seen: set[int] = set()

    for detected_face in detected_faces:
        best_id, confidence = get_pipeline().match_1_to_N(
            detected_face.embedding,
            threshold=settings.GROUP_FACE_SIMILARITY_THRESHOLD,
        )
        if best_id is not None and best_id in student_map and best_id not in seen:
            results.append(
                RecognizedFace(
                    student=student_map[best_id],
                    confidence=confidence,
                    bbox=detected_face.bbox,
                    face_crop=_crop_bbox(image, detected_face.bbox),
                )
            )
            seen.add(best_id)

    return results


def load_gallery_from_db(db: Any) -> int:
    from app.db.models import FaceFeature

    gallery: dict[int, np.ndarray] = {}
    for face_feature in db.query(FaceFeature).all():
        embedding = _base64_to_embedding(face_feature.feature_vector)
        if embedding is not None:
            gallery[face_feature.student_id] = embedding

    get_pipeline().load_gallery(gallery)
    logger.info("Loaded %d face features into memory gallery.", len(gallery))
    return len(gallery)


def add_student_to_gallery(student_id: int, feature_vector: str) -> None:
    embedding = _base64_to_embedding(feature_vector)
    if embedding is not None:
        get_pipeline().add_to_gallery(student_id, embedding)


def remove_student_from_gallery(student_id: int) -> None:
    get_pipeline().remove_from_gallery(student_id)


def parse_students_csv(file_path: Path) -> list[dict[str, str]]:
    with file_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [row for row in reader]
