from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import ActivityParticipant, Attendance, Student, User

router = APIRouter()


def success(data: dict | list, message: str = "success") -> dict:
    return {"code": 200, "message": message, "data": data}


@router.get("/statistics")
def emotion_statistics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attendance_emotions = [item[0] for item in db.query(Attendance.emotion).filter(Attendance.emotion.is_not(None)).all()]
    group_emotions = [item[0] for item in db.query(ActivityParticipant.emotion).filter(ActivityParticipant.emotion.is_not(None)).all()]
    counter = Counter(attendance_emotions + group_emotions)
    return success([
        {"emotion": emotion, "count": count}
        for emotion, count in sorted(counter.items(), key=lambda item: item[0])
    ])


@router.get("/timeline")
def emotion_timeline(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(Attendance, Student)
        .join(Student, Attendance.student_id == Student.student_id)
        .order_by(Attendance.record_id.desc())
        .limit(50)
        .all()
    )
    data = [
        {
            "scene": "attendance",
            "emotion": record.emotion,
            "timestamp": str(record.check_time),
            "student_name": student.name,
        }
        for record, student in rows
    ]
    return success(data)
