"""
人脸识别可视化调试脚本

用途:
  - 默认打开本机摄像头做实时人脸检测和 1:N 比对
  - 从数据库加载已入库的人脸特征
  - 弹出本机窗口显示人脸框、关键点、学号和相似度
  - 按 Esc 退出窗口

示例:
  python script/run_face_detection.py
  python script/run_face_detection.py --camera 1
  python script/run_face_detection.py --probe data/face_data/2023302181032-雷雨桐-网安-女.jpg
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
LAUNCH_CWD = Path.cwd().resolve()

# 固定到 backend 工作目录，确保 .env、attendance.db、uploads、models 都与后端运行时一致。
os.chdir(BACKEND_ROOT)
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.init_db import init_database
from app.db.models import FaceFeature, Student
from app.services.face_pipeline import get_pipeline
from app.services.face_service import load_gallery_from_db


@dataclass(slots=True)
class RecognitionResult:
    face_index: int
    face: Any
    score: float
    matched_student_id: int | None
    matched_student_no: str | None


def _load_image(path: Path) -> np.ndarray:
    try:
        image_bytes = np.fromfile(str(path), dtype=np.uint8)
    except OSError as exc:
        raise ValueError(f"无法读取图片: {path}") from exc

    image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"无法读取图片: {path}")
    return image


def _resolve_input_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve()

    candidates = [
        (LAUNCH_CWD / path).resolve(),
        (PROJECT_ROOT / path).resolve(),
        (BACKEND_ROOT / path).resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def _get_student_map() -> tuple[dict[int, Student], int]:
    init_database()
    with SessionLocal() as db:
        gallery_size = load_gallery_from_db(db)
        students = (
            db.query(Student)
            .join(FaceFeature, FaceFeature.student_id == Student.student_id)
            .order_by(Student.student_id.asc())
            .all()
        )
    return {student.student_id: student for student in students}, gallery_size


def _normalize_points(raw_points: Any) -> list[tuple[int, int]]:
    if raw_points is None:
        return []

    array = np.asarray(raw_points)
    if array.ndim != 2 or array.shape[1] < 2:
        return []

    points: list[tuple[int, int]] = []
    for x, y in array[:, :2]:
        points.append((int(round(float(x))), int(round(float(y)))))
    return points


def _face_bbox(face: Any) -> tuple[int, int, int, int]:
    bbox = np.asarray(face.bbox).tolist()
    x1, y1, x2, y2 = [int(round(float(value))) for value in bbox[:4]]
    return x1, y1, x2, y2


def _recognize_faces(
    image: np.ndarray,
    student_map: dict[int, Student],
    threshold: float,
    verbose: bool = False,
) -> list[RecognitionResult]:
    pipeline = get_pipeline()
    faces = pipeline.detect_faces(image)
    if verbose:
        print(f"[INFO] 检测到 {len(faces)} 张人脸")

    results: list[RecognitionResult] = []
    for index, face in enumerate(faces, start=1):
        embedding = getattr(face, "normed_embedding", None)
        score = 0.0
        matched_student_id: int | None = None
        matched_student_no: str | None = None

        if embedding is not None and student_map:
            matched_student_id, score = pipeline.match_1_to_N(embedding, threshold=threshold)
            if matched_student_id is not None:
                matched_student = student_map.get(matched_student_id)
                matched_student_no = matched_student.student_no if matched_student else None

        bbox = _face_bbox(face)
        keypoints_5 = _normalize_points(getattr(face, "kps", None))
        keypoints_dense = _normalize_points(getattr(face, "landmark_2d_106", None))
        if not keypoints_dense:
            keypoints_dense = _normalize_points(getattr(face, "landmark_3d_68", None))

        if verbose:
            print(
                f"[INFO] face#{index}: bbox={bbox} "
                f"kps5={len(keypoints_5)} dense_kps={len(keypoints_dense)} "
                f"matched_student_no={matched_student_no or 'UNKNOWN'} score={score:.6f}"
            )

        results.append(
            RecognitionResult(
                face_index=index,
                face=face,
                score=score,
                matched_student_id=matched_student_id,
                matched_student_no=matched_student_no,
            )
        )

    return results


def _draw_label(image: np.ndarray, text: str, anchor: tuple[int, int], color: tuple[int, int, int]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.65
    thickness = 2
    (text_width, text_height), baseline = cv2.getTextSize(text, font, scale, thickness)

    x, y = anchor
    box_x1 = max(x, 0)
    box_y2 = max(y, text_height + baseline + 8)
    box_y1 = max(box_y2 - text_height - baseline - 8, 0)
    box_x2 = box_x1 + text_width + 10

    cv2.rectangle(image, (box_x1, box_y1), (box_x2, box_y2), color, thickness=-1)
    cv2.putText(
        image,
        text,
        (box_x1 + 5, box_y2 - baseline - 4),
        font,
        scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )


def _draw_status_panel(
    image: np.ndarray,
    lines: list[str],
    origin: tuple[int, int] = (12, 12),
    text_color: tuple[int, int, int] = (255, 255, 255),
    bg_color: tuple[int, int, int] = (32, 32, 32),
) -> None:
    if not lines:
        return

    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.55
    thickness = 1
    padding_x = 10
    padding_y = 8
    line_gap = 6

    sizes = [cv2.getTextSize(line, font, scale, thickness)[0] for line in lines]
    text_width = max(width for width, _ in sizes)
    text_height = sum(height for _, height in sizes) + line_gap * (len(lines) - 1)
    box_width = text_width + padding_x * 2
    box_height = text_height + padding_y * 2

    x, y = origin
    x1 = max(x, 0)
    y1 = max(y, 0)
    x2 = min(x1 + box_width, image.shape[1] - 1)
    y2 = min(y1 + box_height, image.shape[0] - 1)

    overlay = image.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), bg_color, thickness=-1)
    cv2.addWeighted(overlay, 0.72, image, 0.28, 0, image)

    current_y = y1 + padding_y
    for line, (_, height) in zip(lines, sizes):
        text_y = current_y + height
        cv2.putText(
            image,
            line,
            (x1 + padding_x, text_y),
            font,
            scale,
            text_color,
            thickness,
            cv2.LINE_AA,
        )
        current_y = text_y + line_gap


def _annotate_image(
    image: np.ndarray,
    results: list[RecognitionResult],
    threshold: float,
    overlay_lines: list[str] | None = None,
) -> np.ndarray:
    canvas = image.copy()

    for result in results:
        face = result.face
        x1, y1, x2, y2 = _face_bbox(face)
        matched = result.matched_student_no is not None and result.score >= threshold
        color = (60, 200, 60) if matched else (50, 80, 220)

        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness=2)

        dense_points = _normalize_points(getattr(face, "landmark_2d_106", None))
        if not dense_points:
            dense_points = _normalize_points(getattr(face, "landmark_3d_68", None))
        for point_x, point_y in dense_points:
            cv2.circle(canvas, (point_x, point_y), 1, (255, 180, 0), thickness=-1)

        for point_x, point_y in _normalize_points(getattr(face, "kps", None)):
            cv2.circle(canvas, (point_x, point_y), 3, (0, 255, 255), thickness=-1)

        label = f"NO:{result.matched_student_no} {result.score:.3f}" if matched else f"UNKNOWN {result.score:.3f}"
        _draw_label(canvas, label, (x1, max(y1 - 6, 0)), color)

    if not results:
        cv2.putText(
            canvas,
            "NO_FACE",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

    if overlay_lines:
        _draw_status_panel(canvas, overlay_lines)

    return canvas


def _show_window(image: np.ndarray, window_name: str) -> None:
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.imshow(window_name, image)

    while True:
        visible = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
        if visible < 1:
            break

        key = cv2.waitKey(50) & 0xFF
        if key == 27:
            break

    cv2.destroyWindow(window_name)


def _open_camera(camera_index: int, width: int, height: int) -> cv2.VideoCapture:
    capture: cv2.VideoCapture | None = None

    if sys.platform == "win32":
        capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            capture = None

    if capture is None:
        capture = cv2.VideoCapture(camera_index)

    if not capture.isOpened():
        raise RuntimeError(f"无法打开摄像头: index={camera_index}")

    if width > 0:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height > 0:
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    print(f"[INFO] 摄像头已打开: index={camera_index}")
    return capture


def _matched_count(results: list[RecognitionResult], threshold: float) -> int:
    return sum(1 for item in results if item.matched_student_no is not None and item.score >= threshold)


def _run_probe_mode(
    probe_path: Path,
    student_map: dict[int, Student],
    gallery_size: int,
    threshold: float,
    window_title: str,
    no_window: bool,
) -> None:
    print(f"[INFO] 待识别图片: {probe_path}")
    image = _load_image(probe_path)
    results = _recognize_faces(image, student_map, threshold, verbose=True)

    print("\n[SUMMARY]")
    print(f"faces_detected={len(results)}")
    print(f"gallery_size={gallery_size}")
    print(f"matched_faces={_matched_count(results, threshold)}")

    for item in results:
        print(
            f"face#{item.face_index}: "
            f"student_no={item.matched_student_no or 'UNKNOWN'} "
            f"score={item.score:.6f}"
        )

    if not no_window:
        overlay_lines = [
            f"gallery={gallery_size}",
            f"faces={len(results)}",
            f"matched={_matched_count(results, threshold)}",
            "ESC: quit",
        ]
        annotated = _annotate_image(image, results, threshold, overlay_lines=overlay_lines)
        _show_window(annotated, window_title)


def _run_camera_mode(
    camera_index: int,
    student_map: dict[int, Student],
    gallery_size: int,
    threshold: float,
    window_title: str,
    width: int,
    height: int,
    mirror: bool,
) -> None:
    capture = _open_camera(camera_index, width, height)
    cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)

    last_report_at = 0.0
    previous_signature: tuple[tuple[str, float], ...] = tuple()
    previous_face_count = -1

    try:
        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                print("[WARN] 摄像头读取失败，正在退出。")
                break

            if mirror:
                frame = cv2.flip(frame, 1)

            started = time.perf_counter()
            results = _recognize_faces(frame, student_map, threshold, verbose=False)
            elapsed_ms = (time.perf_counter() - started) * 1000.0

            faces_count = len(results)
            matched_count = _matched_count(results, threshold)
            signature = tuple(
                sorted(
                    (
                        (item.matched_student_no or "UNKNOWN", round(item.score, 3))
                        for item in results
                    ),
                    key=lambda pair: (pair[0], pair[1]),
                )
            )
            now = time.monotonic()
            if faces_count != previous_face_count or signature != previous_signature or now - last_report_at >= 2.0:
                print(
                    f"[INFO] faces={faces_count} matched={matched_count} "
                    f"results={[f'{name}:{score:.3f}' for name, score in signature]}"
                )
                previous_face_count = faces_count
                previous_signature = signature
                last_report_at = now

            overlay_lines = [
                f"camera={camera_index} gallery={gallery_size}",
                f"faces={faces_count} matched={matched_count}",
                f"infer={elapsed_ms:.1f}ms",
                "ESC: quit",
            ]
            if gallery_size == 0:
                overlay_lines.insert(2, "gallery empty")

            annotated = _annotate_image(frame, results, threshold, overlay_lines=overlay_lines)
            cv2.imshow(window_title, annotated)

            visible = cv2.getWindowProperty(window_title, cv2.WND_PROP_VISIBLE)
            if visible < 1:
                break

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break
    finally:
        capture.release()
        cv2.destroyWindow(window_title)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="人脸识别可视化调试脚本")
    parser.add_argument("--probe", help="待识别图片路径；不传时默认打开摄像头")
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="摄像头索引 (默认: 0)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="摄像头宽度请求值 (默认: 1280)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="摄像头高度请求值 (默认: 720)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=settings.FACE_SIMILARITY_THRESHOLD,
        help=f"匹配阈值 (默认: {settings.FACE_SIMILARITY_THRESHOLD})",
    )
    parser.add_argument(
        "--window-title",
        default="Face Recognition Debug",
        help="本机弹窗标题",
    )
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="仅在 --probe 模式下生效，只输出控制台结果，不弹窗",
    )
    parser.add_argument(
        "--mirror",
        action="store_true",
        help="摄像头画面左右镜像显示",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    student_map, gallery_size = _get_student_map()
    print(f"[INFO] 模型目录: {settings.MODEL_DIR}")
    print(f"[INFO] 人脸库特征数: {gallery_size}")
    print(f"[INFO] 人脸库学生数: {len(student_map)}")
    print(f"[INFO] 匹配阈值: {args.threshold}")

    if gallery_size == 0:
        print("[WARN] 当前数据库中没有已入库的人脸特征，只会显示检测框和关键点，不会识别出学号。")

    if args.probe:
        probe_path = _resolve_input_path(args.probe)
        if not probe_path.exists():
            raise SystemExit(f"待识别图片不存在: {probe_path}")
        _run_probe_mode(
            probe_path=probe_path,
            student_map=student_map,
            gallery_size=gallery_size,
            threshold=args.threshold,
            window_title=args.window_title,
            no_window=args.no_window,
        )
        return

    if args.no_window:
        raise SystemExit("--no-window 仅支持和 --probe 一起使用。")

    _run_camera_mode(
        camera_index=args.camera,
        student_map=student_map,
        gallery_size=gallery_size,
        threshold=args.threshold,
        window_title=args.window_title,
        width=args.width,
        height=args.height,
        mirror=args.mirror,
    )


if __name__ == "__main__":
    main()
