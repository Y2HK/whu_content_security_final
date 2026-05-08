import base64
import csv
import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import UploadFile

from app.core.config import settings
from app.services.face_pipeline import get_pipeline

logger = logging.getLogger(__name__)


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


async def save_upload_file(upload_file: UploadFile, destination: Path) -> Path:
    ensure_directory(destination.parent)
    contents = await upload_file.read()
    destination.write_bytes(contents)
    return destination


def _embedding_to_base64(emb: np.ndarray) -> str:
    return base64.b64encode(emb.astype(np.float32).tobytes()).decode("utf-8")


def _base64_to_embedding(s: str) -> np.ndarray | None:
    try:
        arr = np.frombuffer(base64.b64decode(s), dtype=np.float32)
        if arr.shape[0] != 512:
            return None
        return arr
    except Exception:
        return None


def build_face_feature_from_path(image_path: str) -> str:
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"无法读取图片: {image_path}")

    pipeline = get_pipeline()
    embedding = pipeline.extract_embedding(img)
    if embedding is None:
        raise ValueError("图片中未检测到人脸")

    return _embedding_to_base64(embedding)


def match_student(students: list[Any], image_bytes: bytes) -> tuple[Any | None, float]:
    if not students:
        return None, 0.0

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return None, 0.0

    pipeline = get_pipeline()
    embedding = pipeline.extract_embedding(img)
    if embedding is None:
        return None, 0.0

    best_id, confidence = pipeline.match_1_to_N(embedding)
    if best_id is None:
        return None, confidence
    matched = next((s for s in students if s.student_id == best_id), None)
    return matched, confidence


def recognize_group(students: list[Any], image_path: str) -> list[tuple[Any, float]]:
    if not students:
        return []

    img = cv2.imread(image_path)
    if img is None:
        return []

    pipeline = get_pipeline()
    embeddings = pipeline.extract_all_embeddings(img)
    if not embeddings:
        return []

    student_map = {s.student_id: s for s in students}
    results: list[tuple[Any, float]] = []
    seen: set[int] = set()

    for emb in embeddings:
        best_id, confidence = pipeline.match_1_to_N(emb, threshold=settings.GROUP_FACE_SIMILARITY_THRESHOLD)
        if best_id and best_id in student_map and best_id not in seen:
            results.append((student_map[best_id], confidence))
            seen.add(best_id)

    return results


def load_gallery_from_db(db) -> int:
    from app.db.models import FaceFeature

    pipeline = get_pipeline()
    features = db.query(FaceFeature).all()
    gallery: dict[int, np.ndarray] = {}
    for ff in features:
        emb = _base64_to_embedding(ff.feature_vector)
        if emb is not None:
            gallery[ff.student_id] = emb

    pipeline.load_gallery(gallery)
    logger.info("内存人脸库加载完成，共 %d 条特征", len(gallery))
    return len(gallery)


def add_student_to_gallery(student_id: int, feature_base64: str) -> None:
    emb = _base64_to_embedding(feature_base64)
    if emb is not None:
        get_pipeline().add_to_gallery(student_id, emb)


def remove_student_from_gallery(student_id: int) -> None:
    get_pipeline().remove_from_gallery(student_id)


def parse_students_csv(file_path: Path) -> list[dict[str, str]]:
    with file_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [row for row in reader]
