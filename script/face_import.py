from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
GENDERS = {"男", "女"}

# 固定到 backend 工作目录，确保 .env、SQLite、uploads、models 都与后端运行时一致。
os.chdir(BACKEND_ROOT)
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.init_db import init_database
from app.db.models import FaceFeature, Student
from app.services.face_service import add_student_to_gallery, build_face_feature_from_path


@dataclass(slots=True)
class FaceRecord:
    source_path: Path
    student_no: str
    name: str
    class_name: str
    gender: str


@dataclass(slots=True)
class ImportResult:
    student_id: int
    created: bool
    destination: str


def backend_abs_path(path: str | Path) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value.resolve()
    return (BACKEND_ROOT / value).resolve()


def list_image_files(data_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in data_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def parse_split_stem(stem: str) -> tuple[str, str, str, str] | None:
    parts = [part.strip() for part in stem.split("-") if part.strip()]
    if len(parts) < 3:
        return None

    student_no = parts[0]
    if not student_no.isdigit():
        return None

    gender = ""
    tail = len(parts)
    if parts[-1] in GENDERS:
        gender = parts[-1]
        tail -= 1

    if tail < 3:
        return None

    name = parts[1].strip()
    class_name = "-".join(parts[2:tail]).strip()
    if not name or not class_name:
        return None

    return student_no, name, class_name, gender


def build_class_candidates(image_files: list[Path]) -> list[str]:
    class_names: set[str] = set()
    for image_path in image_files:
        parsed = parse_split_stem(image_path.stem)
        if parsed is not None:
            class_names.add(parsed[2])
    return sorted(class_names, key=lambda value: (-len(value), value))


def parse_compact_stem(stem: str, class_candidates: list[str]) -> tuple[str, str, str, str] | None:
    index = 0
    while index < len(stem) and stem[index].isdigit():
        index += 1

    student_no = stem[:index]
    remainder = stem[index:].strip()
    if not student_no or not student_no.isdigit() or not remainder:
        return None

    gender = ""
    if remainder[-1:] in GENDERS:
        gender = remainder[-1]
        remainder = remainder[:-1].strip()

    if not remainder:
        return None

    for class_name in class_candidates:
        if remainder.endswith(class_name):
            name = remainder[: -len(class_name)].strip()
            if name:
                return student_no, name, class_name, gender

    return None


def parse_face_record(image_path: Path, class_candidates: list[str]) -> FaceRecord | None:
    parsed = parse_split_stem(image_path.stem)
    if parsed is None:
        parsed = parse_compact_stem(image_path.stem.replace("-", ""), class_candidates)
    if parsed is None:
        return None

    student_no, name, class_name, gender = parsed
    return FaceRecord(
        source_path=image_path,
        student_no=student_no,
        name=name,
        class_name=class_name,
        gender=gender,
    )


def cleanup_old_face_image(old_path: str | None, new_path: Path) -> None:
    if not old_path:
        return

    old_abs = backend_abs_path(old_path)
    new_abs = new_path.resolve()
    if old_abs == new_abs or not old_abs.exists():
        return

    upload_root = backend_abs_path(settings.UPLOAD_DIR)
    try:
        old_abs.relative_to(upload_root)
    except ValueError:
        return

    old_abs.unlink(missing_ok=True)


def stage_image_for_feature_extraction(record: FaceRecord) -> Path:
    temp_dir = backend_abs_path(settings.UPLOAD_DIR / "_import_tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    staged_path = temp_dir / f"import_{record.student_no}{record.source_path.suffix.lower() or '.jpg'}"
    shutil.copy2(record.source_path, staged_path)
    return staged_path


def import_face_record(record: FaceRecord, dry_run: bool) -> ImportResult:
    staged_path = stage_image_for_feature_extraction(record)
    try:
        feature_vec = build_face_feature_from_path(str(staged_path))

        with SessionLocal() as db:
            student = db.query(Student).filter(Student.student_no == record.student_no).first()
            created = student is None

            if student is None:
                student = Student(
                    student_no=record.student_no,
                    name=record.name,
                    class_name=record.class_name,
                )
                db.add(student)
                db.flush()
            else:
                student.name = record.name
                student.class_name = record.class_name
                db.flush()

            suffix = record.source_path.suffix.lower() or ".jpg"
            destination_rel = settings.UPLOAD_DIR / "students" / f"student_{student.student_id}{suffix}"
            destination_abs = backend_abs_path(destination_rel)
            old_face_path = student.face_image_path

            if not dry_run:
                destination_abs.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staged_path, destination_abs)

            student.face_image_path = destination_rel.as_posix()
            db.query(FaceFeature).filter(FaceFeature.student_id == student.student_id).delete()
            db.add(FaceFeature(student_id=student.student_id, feature_vector=feature_vec))

            if dry_run:
                db.flush()
                student_id = student.student_id
                preview_rel = destination_rel
                if created:
                    preview_rel = settings.UPLOAD_DIR / "students" / f"student_<new>{suffix}"
                db.rollback()
                return ImportResult(
                    student_id=student_id,
                    created=created,
                    destination=preview_rel.as_posix(),
                )

            db.commit()
            add_student_to_gallery(student.student_id, feature_vec)
            cleanup_old_face_image(old_face_path, destination_abs)
            return ImportResult(
                student_id=student.student_id,
                created=created,
                destination=destination_rel.as_posix(),
            )
    finally:
        staged_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量导入 data 目录下的人脸图片到学生库")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"人脸数据目录，默认: {DEFAULT_DATA_DIR}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只做解析和特征提取校验，不写数据库、不复制图片",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    if not data_dir.exists():
        raise SystemExit(f"数据目录不存在: {data_dir}")

    init_database()
    image_files = list_image_files(data_dir)
    if not image_files:
        raise SystemExit(f"未在目录中找到图片: {data_dir}")

    class_candidates = build_class_candidates(image_files)
    print(f"[INFO] 数据目录: {data_dir}")
    print(f"[INFO] 图片数量: {len(image_files)}")
    print(f"[INFO] 识别出的班级标签: {len(class_candidates)}")
    if args.dry_run:
        print("[INFO] 当前为 dry-run，不会修改数据库和上传目录。")

    created = 0
    updated = 0
    skipped = 0
    failed = 0
    issues: list[str] = []

    for image_path in image_files:
        record = parse_face_record(image_path, class_candidates)
        if record is None:
            skipped += 1
            message = f"[SKIP] 文件名无法解析: {image_path.name}"
            issues.append(message)
            print(message)
            continue

        try:
            result = import_face_record(record, dry_run=args.dry_run)
        except Exception as exc:
            failed += 1
            message = f"[FAIL] {image_path.name}: {exc}"
            issues.append(message)
            print(message)
            continue

        if result.created:
            created += 1
            action = "CREATE"
        else:
            updated += 1
            action = "UPDATE"

        prefix = "[DRY-RUN]" if args.dry_run else "[OK]"
        print(
            f"{prefix} {action} {record.student_no} {record.name} "
            f"-> {result.destination}"
        )

    print()
    print("[DONE] 批量导入完成")
    print(f"  创建学生: {created}")
    print(f"  更新学生: {updated}")
    print(f"  跳过文件: {skipped}")
    print(f"  失败文件: {failed}")

    if issues:
        print()
        print("[DETAIL] 异常明细")
        for item in issues:
            print(f"  {item}")


if __name__ == "__main__":
    main()
