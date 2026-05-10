from __future__ import annotations

import argparse
import os
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

# Keep the script aligned with the backend's relative sqlite path and .env file.
os.chdir(BACKEND_ROOT)
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.database import SessionLocal  # noqa: E402
from app.db.init_db import init_database  # noqa: E402
from app.db.models import Attendance, Student  # noqa: E402


DEFAULT_EMOTIONS = ("happy", "neutral", "surprise", "sad", "angry", "fear", "disgust")
DEFAULT_STATUS_WEIGHTS = "success=0.86,late=0.10,failed=0.04"
DEFAULT_METHOD = "random_seed_script"


@dataclass(frozen=True)
class StatusChoice:
    status: str
    weight: float


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date: {value}. Use YYYY-MM-DD.") from exc


def parse_clock(value: str) -> time:
    try:
        hour, minute = value.split(":", 1)
        return time(hour=int(hour), minute=int(minute))
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError(f"Invalid time: {value}. Use HH:MM.") from exc


def parse_time_window(value: str) -> tuple[time, time]:
    try:
        start_raw, end_raw = value.split("-", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Time window must look like 08:00-18:30.") from exc

    start_time = parse_clock(start_raw.strip())
    end_time = parse_clock(end_raw.strip())
    if datetime.combine(date.today(), start_time) > datetime.combine(date.today(), end_time):
        raise argparse.ArgumentTypeError("Time window start must be earlier than the end.")
    return start_time, end_time


def parse_status_weights(value: str) -> list[StatusChoice]:
    choices: list[StatusChoice] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            status, weight_raw = item.split("=", 1)
            weight = float(weight_raw)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                "Status weights must look like success=0.8,late=0.2."
            ) from exc

        status = status.strip()
        if not status:
            raise argparse.ArgumentTypeError("Status name cannot be empty.")
        if weight < 0:
            raise argparse.ArgumentTypeError("Status weight cannot be negative.")
        choices.append(StatusChoice(status=status, weight=weight))

    if not choices or sum(choice.weight for choice in choices) <= 0:
        raise argparse.ArgumentTypeError("At least one positive status weight is required.")
    return choices


def random_datetime(
    rng: random.Random,
    start_date: date,
    end_date: date,
    start_time: time,
    end_time: time,
) -> datetime:
    day_span = (end_date - start_date).days
    selected_date = start_date + timedelta(days=rng.randint(0, day_span))
    start_dt = datetime.combine(selected_date, start_time, tzinfo=timezone.utc)
    end_dt = datetime.combine(selected_date, end_time, tzinfo=timezone.utc)
    seconds = int((end_dt - start_dt).total_seconds())
    return start_dt + timedelta(seconds=rng.randint(0, seconds))


def choose_status(rng: random.Random, choices: list[StatusChoice]) -> str:
    statuses = [choice.status for choice in choices]
    weights = [choice.weight for choice in choices]
    return rng.choices(statuses, weights=weights, k=1)[0]


def build_record(
    rng: random.Random,
    student: Student,
    args: argparse.Namespace,
    status_choices: list[StatusChoice],
) -> Attendance:
    check_time = random_datetime(
        rng,
        args.start_date,
        args.end_date,
        args.start_time,
        args.end_time,
    )
    status = choose_status(rng, status_choices)
    is_live = status == "success" and rng.random() < args.live_rate
    emotion = rng.choice(args.emotions)
    confidence = round(rng.uniform(args.min_confidence, args.max_confidence), 4)

    return Attendance(
        student_id=student.student_id,
        check_time=check_time,
        status=status,
        is_live=is_live,
        live_method=DEFAULT_METHOD,
        emotion=emotion,
        confidence=confidence,
    )


def fetch_students(args: argparse.Namespace) -> list[Student]:
    with SessionLocal() as db:
        query = db.query(Student)
        if args.class_name:
            query = query.filter(Student.class_name == args.class_name)
        if args.student_no:
            query = query.filter(Student.student_no.in_(args.student_no))
        return query.order_by(Student.student_id.asc()).all()


def generate_records(
    students: list[Student],
    args: argparse.Namespace,
    status_choices: list[StatusChoice],
) -> list[Attendance]:
    rng = random.Random(args.seed)
    records: list[Attendance] = []
    for student in students:
        record_count = rng.randint(args.min_records, args.max_records)
        for _ in range(record_count):
            records.append(build_record(rng, student, args, status_choices))
    rng.shuffle(records)
    return records


def print_preview(records: list[Attendance], students_by_id: dict[int, Student], limit: int) -> None:
    for record in records[:limit]:
        student = students_by_id[record.student_id]
        print(
            f"  {student.student_no} {student.name} "
            f"{record.check_time.isoformat()} "
            f"status={record.status} live={record.is_live} "
            f"emotion={record.emotion} confidence={record.confidence}"
        )
    if len(records) > limit:
        print(f"  ... {len(records) - limit} more")


def parse_args() -> argparse.Namespace:
    today = date.today()
    parser = argparse.ArgumentParser(
        description="Generate random attendance records for existing students."
    )
    parser.add_argument(
        "--start-date",
        type=parse_iso_date,
        default=today - timedelta(days=30),
        help="First possible check-in date, default: 30 days ago.",
    )
    parser.add_argument(
        "--end-date",
        type=parse_iso_date,
        default=today,
        help="Last possible check-in date, default: today.",
    )
    parser.add_argument(
        "--time-window",
        type=parse_time_window,
        default=parse_time_window("08:00-18:30"),
        help="Daily check-in time range, for example 08:00-18:30.",
    )
    parser.add_argument(
        "--min-records",
        type=int,
        default=1,
        help="Minimum records to create per selected student.",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=3,
        help="Maximum records to create per selected student.",
    )
    parser.add_argument(
        "--student-no",
        action="append",
        help="Limit to one student number. Can be passed multiple times.",
    )
    parser.add_argument(
        "--class-name",
        help="Limit to one class name.",
    )
    parser.add_argument(
        "--status-weights",
        type=parse_status_weights,
        default=parse_status_weights(DEFAULT_STATUS_WEIGHTS),
        help=f"Weighted statuses, default: {DEFAULT_STATUS_WEIGHTS}.",
    )
    parser.add_argument(
        "--emotions",
        default=",".join(DEFAULT_EMOTIONS),
        help="Comma-separated emotion values.",
    )
    parser.add_argument(
        "--live-rate",
        type=float,
        default=0.92,
        help="Probability that a success record is marked live.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.72,
        help="Minimum random face confidence.",
    )
    parser.add_argument(
        "--max-confidence",
        type=float,
        default=0.99,
        help="Maximum random face confidence.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Set a seed to reproduce the same random records.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated records without writing them.",
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=20,
        help="How many generated rows to print.",
    )
    args = parser.parse_args()

    args.start_time, args.end_time = args.time_window
    args.emotions = [item.strip() for item in args.emotions.split(",") if item.strip()]
    if not args.emotions:
        parser.error("--emotions must contain at least one value.")
    if args.end_date < args.start_date:
        parser.error("--end-date must not be earlier than --start-date.")
    if args.min_records < 0 or args.max_records < 0:
        parser.error("--min-records and --max-records cannot be negative.")
    if args.max_records < args.min_records:
        parser.error("--max-records must be greater than or equal to --min-records.")
    if not 0 <= args.live_rate <= 1:
        parser.error("--live-rate must be between 0 and 1.")
    if not 0 <= args.min_confidence <= args.max_confidence <= 1:
        parser.error("Confidence range must satisfy 0 <= min <= max <= 1.")

    return args


def main() -> None:
    args = parse_args()
    init_database()

    students = fetch_students(args)
    if not students:
        raise SystemExit("No students matched. Import students before generating attendance records.")

    records = generate_records(students, args, args.status_weights)
    students_by_id = {student.student_id: student for student in students}

    print(f"[INFO] selected students: {len(students)}")
    print(f"[INFO] generated records: {len(records)}")
    print(
        f"[INFO] date range: {args.start_date.isoformat()} to {args.end_date.isoformat()}, "
        f"time window: {args.start_time.strftime('%H:%M')}-{args.end_time.strftime('%H:%M')}"
    )
    if args.seed is not None:
        print(f"[INFO] seed: {args.seed}")
    if args.dry_run:
        print("[INFO] dry-run enabled; database will not be changed.")

    print("[PREVIEW]")
    print_preview(records, students_by_id, args.preview_limit)

    if args.dry_run:
        return

    with SessionLocal() as db:
        db.add_all(records)
        db.commit()

    print(f"[DONE] inserted {len(records)} attendance records.")


if __name__ == "__main__":
    main()
