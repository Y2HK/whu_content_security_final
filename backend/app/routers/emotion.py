from collections import Counter

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import ActivityParticipant, Attendance, Student, User
from app.services.emotion_service import EMOTIONS, emotion_model_status

router = APIRouter()


def success(data: dict | list, message: str = "success") -> dict:
    return {"code": 200, "message": message, "data": data}


@router.get("/statistics")
def emotion_statistics(
    student_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attendance_query = db.query(Attendance.emotion).filter(Attendance.emotion.is_not(None))
    group_query = db.query(ActivityParticipant.emotion).filter(ActivityParticipant.emotion.is_not(None))

    if user.role != "teacher":
        if user.student_id is None:
            return success([])
        attendance_query = attendance_query.filter(Attendance.student_id == user.student_id)
        group_query = group_query.filter(ActivityParticipant.student_id == user.student_id)
    elif student_id is not None:
        attendance_query = attendance_query.filter(Attendance.student_id == student_id)
        group_query = group_query.filter(ActivityParticipant.student_id == student_id)

    attendance_emotions = [item[0] for item in attendance_query.all()]
    group_emotions = [item[0] for item in group_query.all()]
    counter = Counter(attendance_emotions + group_emotions)
    ordered_emotions = EMOTIONS + sorted(set(counter) - set(EMOTIONS))
    return success([
        {"emotion": emotion, "count": counter.get(emotion, 0)}
        for emotion in ordered_emotions
    ])


@router.get("/model-status")
def model_status(user: User = Depends(get_current_user)):
    return success(emotion_model_status())


@router.get("/timeline")
def emotion_timeline(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = (
        db.query(Attendance, Student)
        .join(Student, Attendance.student_id == Student.student_id)
    )
    if user.role != "teacher":
        if user.student_id is None:
            return success([])
        query = query.filter(Attendance.student_id == user.student_id)

    rows = query.order_by(Attendance.record_id.desc()).limit(50).all()
    data = [
        {
            "scene": "attendance",
            "emotion": record.emotion,
            "is_live": record.is_live,
            "timestamp": str(record.check_time),
            "student_no": student.student_no,
            "student_name": student.name,
        }
        for record, student in rows
    ]
    return success(data)
