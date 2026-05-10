import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import ActivityParticipant, Attendance, FaceFeature, Student, User
from app.services.face_service import build_face_feature_from_path

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
GENDERS = {"男", "女"}
DEMO_STUDENT_NOS = {"2023001", "2023002", "2023003", "2023004", "2023005"}
DEMO_STUDENT_NAMES = {"张三", "李四", "王五", "赵六", "孙七"}


@dataclass(frozen=True)
class FaceDataRecord:
    source_path: Path
    student_no: str
    name: str
    class_name: str


def _backend_abs_path(path: str | Path) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value.resolve()
    return (settings.UPLOAD_DIR.parent / value).resolve()


def _list_image_files(face_data_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in face_data_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def _parse_split_stem(stem: str) -> tuple[str, str, str] | None:
    parts = [part.strip() for part in stem.split("-") if part.strip()]
    if len(parts) < 3 or not parts[0].isdigit():
        return None

    tail = len(parts)
    if parts[-1] in GENDERS:
        tail -= 1
    if tail < 3:
        return None

    student_no = parts[0]
    name = parts[1]
    class_name = "-".join(parts[2:tail]).strip()
    if not name or not class_name:
        return None
    return student_no, name, class_name


def _build_class_candidates(image_files: list[Path]) -> list[str]:
    class_names: set[str] = set()
    for image_path in image_files:
        parsed = _parse_split_stem(image_path.stem)
        if parsed is not None:
            class_names.add(parsed[2])
    return sorted(class_names, key=lambda value: (-len(value), value))


def _parse_compact_stem(stem: str, class_candidates: list[str]) -> tuple[str, str, str] | None:
    index = 0
    while index < len(stem) and stem[index].isdigit():
        index += 1

    student_no = stem[:index]
    remainder = stem[index:].strip()
    if not student_no or not remainder:
        return None

    if remainder[-1:] in GENDERS:
        remainder = remainder[:-1].strip()

    for class_name in class_candidates:
        if remainder.endswith(class_name):
            name = remainder[: -len(class_name)].strip()
            if name:
                return student_no, name, class_name
    return None


def _parse_face_data_record(image_path: Path, class_candidates: list[str]) -> FaceDataRecord | None:
    parsed = _parse_split_stem(image_path.stem)
    if parsed is None:
        parsed = _parse_compact_stem(image_path.stem.replace("-", ""), class_candidates)
    if parsed is None:
        return None

    student_no, name, class_name = parsed
    return FaceDataRecord(
        source_path=image_path,
        student_no=student_no,
        name=name,
        class_name=class_name,
    )


def _cleanup_old_face_image(old_path: str | None, new_path: Path) -> None:
    if not old_path:
        return

    old_abs = _backend_abs_path(old_path)
    if old_abs == new_path.resolve() or not old_abs.exists():
        return

    upload_root = settings.UPLOAD_DIR.resolve()
    try:
        old_abs.relative_to(upload_root)
    except ValueError:
        return
    old_abs.unlink(missing_ok=True)


def remove_demo_students(db: Session) -> int:
    demo_students = (
        db.query(Student)
        .filter((Student.student_no.in_(DEMO_STUDENT_NOS)) | (Student.name.in_(DEMO_STUDENT_NAMES)))
        .all()
    )
    if not demo_students:
        return 0

    demo_student_ids = [student.student_id for student in demo_students]
    db.query(ActivityParticipant).filter(ActivityParticipant.student_id.in_(demo_student_ids)).delete(
        synchronize_session=False
    )
    db.query(Attendance).filter(Attendance.student_id.in_(demo_student_ids)).delete(synchronize_session=False)
    db.query(FaceFeature).filter(FaceFeature.student_id.in_(demo_student_ids)).delete(synchronize_session=False)
    db.query(User).filter(User.student_id.in_(demo_student_ids)).delete(synchronize_session=False)
    for student in demo_students:
        _cleanup_old_face_image(student.face_image_path, Path(""))
        db.delete(student)
    db.commit()
    logger.info("Removed %d demo students from database.", len(demo_students))
    return len(demo_students)


def _import_face_record(db: Session, record: FaceDataRecord) -> tuple[bool, bool]:
    student = db.query(Student).filter(Student.student_no == record.student_no).first()
    created = student is None

    if student is not None:
        has_feature = db.query(FaceFeature).filter(FaceFeature.student_id == student.student_id).first() is not None
        face_image_exists = bool(student.face_image_path and _backend_abs_path(student.face_image_path).exists())
        info_matches = student.name == record.name and student.class_name == record.class_name
        if has_feature and face_image_exists and info_matches:
            return False, False

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
    destination = settings.UPLOAD_DIR / "students" / f"student_{student.student_id}{suffix}"
    old_face_path = student.face_image_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(record.source_path, destination)

    feature_vector = build_face_feature_from_path(str(destination))
    student.face_image_path = destination.as_posix()
    db.query(FaceFeature).filter(FaceFeature.student_id == student.student_id).delete()
    db.add(FaceFeature(student_id=student.student_id, feature_vector=feature_vector))
    _cleanup_old_face_image(old_face_path, destination)
    return created, True


def import_face_data_on_startup(db: Session) -> dict[str, int]:
    result = {
        "removed_demo": 0,
        "scanned": 0,
        "created": 0,
        "updated": 0,
        "skipped_existing": 0,
        "skipped_unparsed": 0,
        "failed": 0,
    }
    result["removed_demo"] = remove_demo_students(db)

    if not settings.AUTO_IMPORT_FACE_DATA:
        logger.info("Face data auto import is disabled.")
        return result

    face_data_dir = settings.FACE_DATA_DIR
    if not face_data_dir.exists():
        logger.warning("Face data directory does not exist, skipped: %s", face_data_dir)
        return result

    image_files = _list_image_files(face_data_dir)
    result["scanned"] = len(image_files)
    if not image_files:
        logger.warning("No face images found in %s", face_data_dir)
        return result

    class_candidates = _build_class_candidates(image_files)
    for image_path in image_files:
        record = _parse_face_data_record(image_path, class_candidates)
        if record is None:
            result["skipped_unparsed"] += 1
            logger.warning("Skipped unparseable face data filename: %s", image_path.name)
            continue

        try:
            created, imported = _import_face_record(db, record)
            db.commit()
        except Exception as exc:
            db.rollback()
            result["failed"] += 1
            logger.warning("Failed to import face data image %s: %s", image_path.name, exc)
            continue

        if not imported:
            result["skipped_existing"] += 1
        elif created:
            result["created"] += 1
        else:
            result["updated"] += 1

    logger.info(
        "Face data auto import finished: removed_demo=%d scanned=%d created=%d updated=%d skipped_existing=%d skipped_unparsed=%d failed=%d",
        result["removed_demo"],
        result["scanned"],
        result["created"],
        result["updated"],
        result["skipped_existing"],
        result["skipped_unparsed"],
        result["failed"],
    )
    return result
