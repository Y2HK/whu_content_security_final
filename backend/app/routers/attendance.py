import logging
import random
import uuid
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import Attendance, Student, User
from app.services.emotion_service import analyze_image_emotion
from app.services.face_service import match_student
from app.services.liveness_service import liveness_engine

router = APIRouter()
logger = logging.getLogger(__name__)

# 内存缓存：{challenge_id: {"action_type": str, "expires_at": datetime, "used": bool}}
# 仅适用于 FastAPI 单进程开发服务器
_challenge_store = {}


def _cleanup_expired_challenges():
    now = datetime.utcnow()
    expired = [k for k, v in _challenge_store.items() if now > v["expires_at"]]
    for k in expired:
        del _challenge_store[k]


def _validate_challenge(challenge_id: str | None) -> bool:
    if not challenge_id:
        return False
    _cleanup_expired_challenges()
    challenge = _challenge_store.get(challenge_id)
    if not challenge:
        return False
    if challenge["used"]:
        return False
    if datetime.utcnow() > challenge["expires_at"]:
        return False
    challenge["used"] = True
    return True


def success(data: dict | list, message: str = "success") -> dict:
    return {"code": 200, "message": message, "data": data}


def accessible_students_query(db: Session, user: User):
    query = db.query(Student)
    if user.role != "teacher":
        if user.student_id is None:
            raise HTTPException(status_code=403, detail="学生账号未绑定学生信息")
        query = query.filter(Student.student_id == user.student_id)
    return query


def apply_attendance_filters(
    query,
    user: User,
    student_no: str | None = None,
    name: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    if user.role != "teacher":
        if user.student_id is None:
            return None
        query = query.filter(Attendance.student_id == user.student_id)
    if student_no:
        query = query.filter(Student.student_no.contains(student_no))
    if name:
        query = query.filter(Student.name.contains(name))
    if date_from:
        query = query.filter(Attendance.check_time >= datetime.combine(date_from, time.min))
    if date_to:
        query = query.filter(Attendance.check_time <= datetime.combine(date_to, time.max))
    return query


@router.get("/action-challenge")
def action_challenge(user: User = Depends(get_current_user)):
    _cleanup_expired_challenges()
    challenge_id = str(uuid.uuid4())
    action_type = random.choice(["blink", "open_mouth"])
    _challenge_store[challenge_id] = {
        "action_type": action_type,
        "expires_at": datetime.utcnow() + timedelta(seconds=60),
        "used": False,
    }
    return success({
        "challenge_id": challenge_id,
        "action_type": action_type,
        "description": "请眨眼" if action_type == "blink" else "请张嘴",
        "timeout_seconds": 10,
    })


@router.post("/check")
def attendance_check(
    file: UploadFile = File(...),
    challenge_id: str | None = Form(None),
    action_verified: bool = Form(False),
    action_meta: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    students = accessible_students_query(db, user).all()
    if not students:
        raise HTTPException(status_code=400, detail="当前没有学生数据，无法完成考勤")

    # 如果提供了 challenge_id，校验其有效性
    if challenge_id is not None and not _validate_challenge(challenge_id):
        raise HTTPException(status_code=400, detail="动作验证凭证无效或已过期")

    # 记录前端动作校验日志（仅日志，不存储到数据库）
    if action_verified or action_meta:
        logger.info(
            "attendance_check action info: action_verified=%s action_meta=%s user=%s",
            action_verified,
            action_meta,
            user.username,
        )

    image_bytes = file.file.read()
    matched_student, confidence = match_student(students, image_bytes)
    emotion_prediction = analyze_image_emotion(
        image_bytes,
        fallback_seed=(file.filename or "attendance") + str(matched_student.student_id if matched_student else 0),
    )
    emotion = emotion_prediction.emotion
    check_time = datetime.now(timezone.utc)

    # 纹理活体检测（直接对整图分析）
    live_result = liveness_engine.predict(image_bytes)

    # 活体检测策略：模型加载成功且判定为假 → 拒绝
    if live_result["model_loaded"] and not live_result["is_live"]:
        raise HTTPException(status_code=400, detail="活体检测未通过，请使用真实人脸")

    if not matched_student:
        raise HTTPException(status_code=404, detail="未识别到匹配学生")

    record = Attendance(
        student_id=matched_student.student_id,
        check_time=check_time,
        status="success",
        is_live=live_result["is_live"],
        live_method=live_result["method"],
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
        "emotion_confidence": emotion_prediction.confidence,
        "emotion_source": emotion_prediction.source,
        "confidence": confidence,
        "live_result": {
            "is_live": live_result["is_live"],
            "confidence": live_result["confidence"],
            "method": live_result["method"],
            "model_loaded": live_result["model_loaded"],
        },
    })


@router.get("/records")
def attendance_records(
    student_no: str | None = Query(default=None),
    name: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Attendance, Student).join(Student, Attendance.student_id == Student.student_id)
    query = apply_attendance_filters(query, user, student_no, name, date_from, date_to)
    if query is None:
        return success([])

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
def export_attendance(
    student_no: str | None = Query(default=None),
    name: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Attendance, Student).join(Student, Attendance.student_id == Student.student_id)
    query = apply_attendance_filters(query, user, student_no, name, date_from, date_to)
    rows = [] if query is None else query.order_by(Attendance.record_id.asc()).all()

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
