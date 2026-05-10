from types import SimpleNamespace

import cv2
import numpy as np

from app.services import face_service
from app.services.face_pipeline import DetectedFace


class FakePipeline:
    def extract_all_detected_faces(self, image):
        return [
            DetectedFace(embedding=np.array([1.0, 0.0], dtype=np.float32), bbox=(10, 10, 30, 30)),
            DetectedFace(embedding=np.array([0.0, 1.0], dtype=np.float32), bbox=(35, 35, 55, 55)),
        ]

    def match_1_to_N(self, embedding, threshold):
        if float(embedding[0]) == 1.0:
            return 101, 0.91
        return 202, 0.88


def test_recognize_group_detailed_returns_face_crops(monkeypatch, tmp_path):
    monkeypatch.setattr(face_service, "get_pipeline", lambda: FakePipeline())
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    image_path = tmp_path / "group.jpg"
    assert cv2.imwrite(str(image_path), image)

    students = [
        SimpleNamespace(student_id=101, name="a"),
        SimpleNamespace(student_id=202, name="b"),
    ]

    results = face_service.recognize_group_detailed(students, str(image_path))
    legacy_results = face_service.recognize_group(students, str(image_path))

    assert [item.student.student_id for item in results] == [101, 202]
    assert [round(item.confidence, 2) for item in results] == [0.91, 0.88]
    assert results[0].bbox == (10, 10, 30, 30)
    assert results[0].face_crop.shape[:2] == (30, 30)
    assert [(student.student_id, round(confidence, 2)) for student, confidence in legacy_results] == [
        (101, 0.91),
        (202, 0.88),
    ]
