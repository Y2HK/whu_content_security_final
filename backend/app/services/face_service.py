import csv
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


async def save_upload_file(upload_file: UploadFile, destination: Path) -> Path:
    ensure_directory(destination.parent)
    contents = await upload_file.read()
    destination.write_bytes(contents)
    return destination


def build_face_feature_from_path(image_path: str) -> str:
    payload = f"{image_path}|{datetime.utcnow().isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def match_student(students: list[Any], image_identifier: str) -> tuple[Any | None, float]:
    if not students:
        return None, 0.0

    index = int(hashlib.md5(image_identifier.encode("utf-8")).hexdigest(), 16) % len(students)
    confidence = 0.72 + (index % 20) * 0.01
    return students[index], min(confidence, 0.95)


def simulate_group_matches(students: list[Any], activity_name: str) -> list[tuple[Any, float]]:
    if not students:
        return []

    count = min(max(1, len(students) // 2), len(students))
    base = int(hashlib.sha1(activity_name.encode("utf-8")).hexdigest(), 16)
    selected = []
    for offset in range(count):
        student = students[(base + offset) % len(students)]
        confidence = 0.7 + ((base + offset) % 20) * 0.01
        selected.append((student, min(confidence, 0.94)))
    return selected


def parse_students_csv(file_path: Path) -> list[dict[str, str]]:
    with file_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [row for row in reader]
