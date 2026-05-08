from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import Attendance, Student, User
from app.services.emotion_service import analyze_emotion
from app.services.face_service import match_student
from app.services.liveness_service import get_liveness_placeholder

router = APIRouter()


def success(data: dict | list, message: str = "success") -> dict:
    return {"code": 200, "message": message, "data": data}


@router.get("/action-challenge")
def action_challenge(user: User = Depends(get_current_user)):
    return success(get_liveness_placeholder(), message="placeholder")


@router.post("/check")
async def attendance_check(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    students = db.query(Student).all()
    if not students:
        raise HTTPException(status_code=400, detail="当前没有学生数据，无法完成考勤")

    image_bytes = await file.read()
    matched_student, confidence = match_student(students, image_bytes)
    emotion = analyze_emotion(str(matched_student.student_id if matched_student else 0))
    check_time = datetime.now(timezone.utc)
    live_result = get_liveness_placeholder()

    if not matched_student:
        raise HTTPException(status_code=404, detail="未识别到匹配学生")

    record = Attendance(
        student_id=matched_student.student_id,
        check_time=check_time,
        status="success",
        is_live=False,
        live_method="reserved",
        emotion=emotion,
        confidence=confidence,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return success({
        "record_id": record.record_id,
        "student_id": matched_student.student_id,
        "student_no": matched_student.student_no,
        "name": matched_student.name,
        "check_time": check_time,
        "status": "success",
        "emotion": emotion,
        "confidence": confidence,
        "live_result": live_result,
    })


@router.get("/records")
def attendance_records(
    student_no: str | None = Query(default=None),
    name: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Attendance, Student).join(Student, Attendance.student_id == Student.student_id)
    if student_no:
        query = query.filter(Student.student_no.contains(student_no))
    if name:
        query = query.filter(Student.name.contains(name))

    rows = query.order_by(Attendance.record_id.desc()).all()
    data = []
    for record, student in rows:
        data.append({
            "record_id": record.record_id,
            "student_id": student.student_id,
            "student_no": student.student_no,
            "name": student.name,
            "class_name": student.class_name,
            "check_time": record.check_time,
            "status": record.status,
            "is_live": record.is_live,
            "live_method": record.live_method,
            "emotion": record.emotion,
            "confidence": record.confidence,
        })
    return success(data)


@router.get("/export")
def export_attendance(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(Attendance, Student)
        .join(Student, Attendance.student_id == Student.student_id)
        .order_by(Attendance.record_id.asc())
        .all()
    )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "attendance"
    sheet.append(["记录ID", "学号", "姓名", "班级", "考勤时间", "状态", "活体结果", "情绪", "置信度"])

    for record, student in rows:
        sheet.append([
            record.record_id,
            student.student_no,
            student.name,
            student.class_name,
            str(record.check_time),
            record.status,
            "是" if record.is_live else "否",
            record.emotion,
            record.confidence,
        ])

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="attendance.xlsx"'},
    )
