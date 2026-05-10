import logging
import random
import uuid
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_teacher
from app.db.database import get_db
from app.db.models import Attendance, AttendanceSession, Student, User
from app.core.config import settings
from app.services.emotion_service import analyze_image_emotion
from app.services.face_service import match_student
from app.services.liveness_service import liveness_engine

router = APIRouter()
logger = logging.getLogger(__name__)

# 内存缓存：{challenge_id: {"action_type": str, "expires_at": datetime, "used": bool}}
# 仅适用于 FastAPI 单进程开发服务器
_challenge_store = {}


class PublishAttendanceSessionRequest(BaseModel):
    title: str = "课堂签到"
    description: str | None = None


def _cleanup_expired_challenges():
    now = datetime.utcnow()
    expired = [k for k, v in _challenge_store.items() if now > v["expires_at"]]
    for k in expired:
        del _challenge_store[k]


def _validate_challenge(challenge_id: str | None, active_session_id: int | None = None) -> bool:
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
    if active_session_id is not None and challenge.get("session_id") != active_session_id:
        return False
    challenge["used"] = True
    return True


def success(data: dict | list, message: str = "success") -> dict:
    return {"code": 200, "message": message, "data": data}


def serialize_attendance_session(session: AttendanceSession | None, include_teacher_fields: bool = True) -> dict | None:
    if session is None:
        return None
    data = {
        "session_id": session.session_id,
        "is_active": session.is_active,
        "created_at": session.created_at,
    }
    if include_teacher_fields:
        data.update({
            "title": session.title,
            "description": session.description,
            "created_by": session.created_by,
            "closed_at": session.closed_at,
        })
    return data


def get_active_attendance_session(db: Session) -> AttendanceSession | None:
    return (
        db.query(AttendanceSession)
        .filter(AttendanceSession.is_active.is_(True))
        .order_by(AttendanceSession.session_id.desc())
        .first()
    )


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


ACTIONS = ["blink", "open_mouth"]


@router.get("/session/active")
def active_attendance_session(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(
        serialize_attendance_session(
            get_active_attendance_session(db),
            include_teacher_fields=user.role == "teacher",
        )
    )


@router.post("/session/publish")
def publish_attendance_session(
    payload: PublishAttendanceSessionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    now = datetime.now(timezone.utc)
    active_sessions = db.query(AttendanceSession).filter(AttendanceSession.is_active.is_(True)).all()
    for session in active_sessions:
        session.is_active = False
        session.closed_at = now

    title = payload.title.strip() or "课堂签到"
    session = AttendanceSession(
        title=title,
        description=(payload.description or "").strip() or None,
        is_active=True,
        created_by=user.user_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return success(serialize_attendance_session(session), "published")


@router.post("/session/close")
def close_attendance_session(db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    session = get_active_attendance_session(db)
    if session is None:
        return success({"closed": False})

    session.is_active = False
    session.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return success({"closed": True, "session": serialize_attendance_session(session)})


@router.get("/action-challenge")
def action_challenge(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    active_session = get_active_attendance_session(db)
    if active_session is None:
        raise HTTPException(status_code=400, detail="当前没有教师发布的签到")

    _cleanup_expired_challenges()
    challenge_id = str(uuid.uuid4())
    actions = random.sample(ACTIONS, k=len(ACTIONS))
    descriptions = ["请眨眼" if a == "blink" else "请张嘴" for a in actions]
    _challenge_store[challenge_id] = {
        "actions": actions,
        "session_id": active_session.session_id,
        "expires_at": datetime.utcnow() + timedelta(seconds=60),
        "used": False,
    }
    return success({
        "challenge_id": challenge_id,
        # 兼容旧前端
        "action_type": actions[0],
        "description": descriptions[0],
        # 新前端（动作序列）
        "actions": actions,
        "descriptions": descriptions,
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
    challenge_passed = False
    if challenge_id is not None:
        active_session = get_active_attendance_session(db)
        if active_session is None:
            raise HTTPException(status_code=400, detail="当前签到已结束或尚未发布")
        if not _validate_challenge(challenge_id, active_session.session_id):
            raise HTTPException(status_code=400, detail="动作验证凭证无效或已过期")
        challenge_passed = bool(action_verified)

    # 记录前端动作校验日志（仅日志，不存储到数据库）
    if action_verified or action_meta:
        logger.info(
            "attendance_check action info: action_verified=%s action_meta=%s user=%s",
            action_verified,
            action_meta,
            user.username,
        )

    image_bytes = file.file.read()

    # 解码图像用于人脸检测和活体检测
    import cv2
    import numpy as np

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="无法解析上传图片")

    # 检测人脸（一次检测，同时用于活体检测和人脸识别）
    from app.services.face_pipeline import get_pipeline

    logger.info(
        "[FACE DEBUG] Image shape=%s, dtype=%s, mean=%.1f",
        img.shape, img.dtype, float(img.mean()),
    )
    pipeline = get_pipeline()
    faces = pipeline.detect_faces(img)
    logger.info("[FACE DEBUG] detect_faces returned %d faces", len(faces))
    if not faces:
        raise HTTPException(
            status_code=400,
            detail=f"未检测到人脸。图片尺寸={img.shape[1]}x{img.shape[0]}，请确保人脸清晰可见、正对摄像头。"
        )

    # 裁剪人脸区域用于活体检测（MiniFASNet 需要 2.7x 扩展的 80x80 人脸区域）
    bbox = faces[0].bbox.astype(int)
    h, w = img.shape[:2]
    fx1, fy1, fx2, fy2 = bbox[0], bbox[1], bbox[2], bbox[3]
    cx, cy = (fx1 + fx2) / 2, (fy1 + fy2) / 2
    fw, fh = fx2 - fx1, fy2 - fy1
    # 2.7x 扩展（与模型训练时一致）
    scale = 2.7
    nx1 = int(max(0, cx - fw * scale / 2))
    ny1 = int(max(0, cy - fh * scale / 2))
    nx2 = int(min(w, cx + fw * scale / 2))
    ny2 = int(min(h, cy + fh * scale / 2))
    face_crop = img[ny1:ny2, nx1:nx2]
    logger.warning(
        "[CROP DEBUG] bbox=(%d,%d,%d,%d), crop=(%d,%d,%d,%d), size=%dx%d, "
        "face_crop_min=%.1f, max=%.1f, mean=%.1f",
        fx1, fy1, fx2, fy2, nx1, ny1, nx2, ny2,
        face_crop.shape[1], face_crop.shape[0],
        float(face_crop.min()), float(face_crop.max()), float(face_crop.mean()),
    )

    # 纹理活体检测（传入人脸区域）
    live_result = liveness_engine.predict(face_crop)
    logger.warning(
        "[LIVENESS DEBUG] method=%s, model_loaded=%s, is_live=%s, confidence=%.4f, threshold=%.2f",
        live_result["method"],
        live_result["model_loaded"],
        live_result["is_live"],
        live_result["confidence"],
        settings.LIVENESS_THRESHOLD,
    )

    # 人脸识别（复用已检测到的人脸特征）
    embedding = faces[0].normed_embedding
    best_id, confidence = pipeline.match_1_to_N(
        embedding, threshold=settings.FACE_SIMILARITY_THRESHOLD
    )
    matched_student = next(
        (student for student in students if student.student_id == best_id), None
    )
    logger.info(
        "[FACE DEBUG] faces_detected=%d, matched=%s, best_id=%s, confidence=%.4f",
        len(faces),
        matched_student.name if matched_student else "None",
        best_id,
        confidence,
    )

    # 情绪识别使用较紧的人脸裁剪，避免背景和身体动作影响表情分类。
    emotion_scale = 1.35
    ex1 = int(max(0, cx - fw * emotion_scale / 2))
    ey1 = int(max(0, cy - fh * emotion_scale / 2))
    ex2 = int(min(w, cx + fw * emotion_scale / 2))
    ey2 = int(min(h, cy + fh * emotion_scale / 2))
    emotion_crop = img[ey1:ey2, ex1:ex2]
    is_camera_capture = (
        action_verified
        or (file.filename or "").startswith(("camera_capture_", "facemesh_capture_"))
    )
    emotion_prediction = analyze_image_emotion(
        emotion_crop if emotion_crop.size else image_bytes,
        fallback_seed=(file.filename or "attendance") + str(matched_student.student_id if matched_student else 0),
        camera_mode=is_camera_capture,
    )
    emotion = emotion_prediction.emotion
    check_time = datetime.now(timezone.utc)

    backend_liveness_available = live_result["model_loaded"]
    final_is_live = bool(
        challenge_passed
        and (live_result["is_live"] if backend_liveness_available else True)
    )
    live_method = (
        live_result["method"]
        if backend_liveness_available
        else ("action_challenge" if challenge_passed else live_result["method"])
    )

    # 活体检测策略：动作验证通过后，如果后端模型可用且判定为假 → 拒绝
    if challenge_passed and backend_liveness_available and not live_result["is_live"]:
        logger.warning(
            "[LIVENESS REJECTED] confidence=%.4f < threshold=%.2f",
            live_result["confidence"],
            settings.LIVENESS_THRESHOLD,
        )
        raise HTTPException(status_code=400, detail="活体检测未通过，请使用真实人脸")

    if not matched_student:
        raise HTTPException(status_code=404, detail="未识别到匹配学生")

    record = Attendance(
        student_id=matched_student.student_id,
        check_time=check_time,
        status="success",
        is_live=final_is_live,
        live_method=live_method,
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
        "raw_emotion": emotion_prediction.raw_emotion,
        "emotion_scores": emotion_prediction.scores,
        "confidence": confidence,
        "live_result": {
            "is_live": final_is_live,
            "confidence": live_result["confidence"],
            "method": live_method,
            "model_loaded": live_result["model_loaded"],
            "challenge_passed": challenge_passed,
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
