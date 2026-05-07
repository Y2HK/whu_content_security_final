from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user, require_teacher
from app.db.database import get_db
from app.db.models import Activity, ActivityParticipant, Student, User
from app.services.emotion_service import analyze_image_emotions
from app.services.face_service import save_upload_file, simulate_group_matches

router = APIRouter()


def success(data: dict | list, message: str = "success") -> dict:
    return {"code": 200, "message": message, "data": data}


@router.post("/upload")
async def upload_group_photo(
    activity_name: str = Form(...),
    event_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    students = db.query(Student).order_by(Student.student_id.asc()).all()
    if not students:
        raise HTTPException(status_code=400, detail="当前没有学生数据，无法完成合照识别")

    suffix = Path(file.filename or "group.jpg").suffix or ".jpg"
    destination = settings.UPLOAD_DIR / "activities" / f"{activity_name}_{event_date}{suffix}"
    await save_upload_file(file, destination)

    activity = Activity(activity_name=activity_name, image_path=str(destination).replace("\\", "/"), event_date=event_date, participant_count=0)
    db.add(activity)
    db.commit()
    db.refresh(activity)

    matches = simulate_group_matches(students, activity_name)
    emotion_predictions = analyze_image_emotions(destination, count=len(matches), fallback_seed=activity_name)
    participants = []
    for index, (student, confidence) in enumerate(matches):
        emotion_prediction = emotion_predictions[index]
        emotion = emotion_prediction.emotion
        db.add(ActivityParticipant(activity_id=activity.activity_id, student_id=student.student_id, confidence=confidence, emotion=emotion))
        participants.append({
            "student_id": student.student_id,
            "student_no": student.student_no,
            "name": student.name,
            "confidence": confidence,
            "emotion": emotion,
            "emotion_confidence": emotion_prediction.confidence,
            "emotion_source": emotion_prediction.source,
        })

    activity.participant_count = len(participants)
    db.commit()
    db.refresh(activity)

    return success({
        "activity_id": activity.activity_id,
        "activity_name": activity.activity_name,
        "event_date": activity.event_date,
        "participant_count": activity.participant_count,
        "participants": participants,
    })


@router.get("/activities")
def list_activities(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Activity)
    if user.role != "teacher":
        if user.student_id is None:
            return success([])
        query = query.join(ActivityParticipant, Activity.activity_id == ActivityParticipant.activity_id).filter(
            ActivityParticipant.student_id == user.student_id
        )

    activities = query.order_by(Activity.activity_id.desc()).all()
    return success([
        {
            "activity_id": item.activity_id,
            "activity_name": item.activity_name,
            "event_date": item.event_date,
            "participant_count": item.participant_count,
            "created_at": item.created_at,
        }
        for item in activities
    ])


@router.get("/activities/{activity_id}")
def activity_detail(activity_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    activity = db.query(Activity).filter(Activity.activity_id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在")

    participant_query = (
        db.query(ActivityParticipant, Student)
        .join(Student, ActivityParticipant.student_id == Student.student_id)
        .filter(ActivityParticipant.activity_id == activity_id)
    )
    if user.role != "teacher":
        if user.student_id is None:
            raise HTTPException(status_code=403, detail="学生账号未绑定学生信息")
        participant_query = participant_query.filter(ActivityParticipant.student_id == user.student_id)

    rows = participant_query.all()
    if user.role != "teacher" and not rows:
        raise HTTPException(status_code=403, detail="只能查看自己参与的活动")

    participants = [
        {
            "student_id": student.student_id,
            "student_no": student.student_no,
            "name": student.name,
            "confidence": participant.confidence,
            "emotion": participant.emotion,
        }
        for participant, student in rows
    ]
    return success({
        "activity_id": activity.activity_id,
        "activity_name": activity.activity_name,
        "event_date": activity.event_date,
        "participant_count": activity.participant_count,
        "participants": participants,
    })


@router.get("/statistics")
def activity_statistics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Student)
    if user.role != "teacher":
        if user.student_id is None:
            return success([])
        query = query.filter(Student.student_id == user.student_id)

    students = query.order_by(Student.student_id.asc()).all()
    data = []
    for student in students:
        count = db.query(ActivityParticipant).filter(ActivityParticipant.student_id == student.student_id).count()
        data.append({
            "student_id": student.student_id,
            "student_no": student.student_no,
            "name": student.name,
            "activity_count": count,
        })
    return success(data)
