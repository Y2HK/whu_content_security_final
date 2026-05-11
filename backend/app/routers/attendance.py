import logging
import random
import uuid
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import Attendance, Student, User
from app.core.config import settings
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


ACTIONS = ["blink", "open_mouth"]


@router.get("/action-challenge")
def action_challenge(user: User = Depends(get_current_user)):
    _cleanup_expired_challenges()
    challenge_id = str(uuid.uuid4())
    actions = random.sample(ACTIONS, k=len(ACTIONS))
    descriptions = ["请眨眼" if a == "blink" else "请张嘴" for a in actions]
    _challenge_store[challenge_id] = {
        "actions": actions,
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


def _decode_upload(file: UploadFile) -> np.ndarray:
    """Decode uploaded image file to BGR numpy array."""
    import cv2
    import numpy as np

    image_bytes = file.file.read()
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="无法解析上传图片")
    return img, image_bytes


def _detect_and_crop_face(img: np.ndarray, pipeline) -> tuple[np.ndarray, list]:
    """Detect face and return face crop + faces list."""
    faces = pipeline.detect_faces(img)
    if not faces:
        return None, faces

    bbox = faces[0].bbox.astype(int)
    h, w = img.shape[:2]
    fx1, fy1, fx2, fy2 = bbox[0], bbox[1], bbox[2], bbox[3]
    cx, cy = (fx1 + fx2) / 2, (fy1 + fy2) / 2
    fw, fh = fx2 - fx1, fy2 - fy1
    scale = 2.7
    nx1 = int(max(0, cx - fw * scale / 2))
    ny1 = int(max(0, cy - fh * scale / 2))
    nx2 = int(min(w, cx + fw * scale / 2))
    ny2 = int(min(h, cy + fh * scale / 2))
    face_crop = img[ny1:ny2, nx1:nx2]
    return face_crop, faces


def _run_liveness_single(face_crop: np.ndarray) -> dict[str, Any]:
    """Run texture liveness detection on a single face crop."""
    live_result = liveness_engine.predict(face_crop)
    logger.warning(
        "[LIVENESS DEBUG] method=%s, model_loaded=%s, is_live=%s, confidence=%.4f, threshold=%.2f",
        live_result["method"],
        live_result["model_loaded"],
        live_result["is_live"],
        live_result["confidence"],
        settings.LIVENESS_THRESHOLD,
    )
    return live_result


def _run_liveness_multi(face_crops: list[np.ndarray]) -> dict[str, Any]:
    """Run texture liveness detection on multiple face crops and vote.

    Temporal consistency enhancement: requires majority of frames to pass.
    """
    if len(face_crops) == 1:
        return _run_liveness_single(face_crops[0])

    results = [_run_liveness_single(crop) for crop in face_crops]
    live_votes = sum(1 for r in results if r["is_live"])
    total = len(results)
    is_live = live_votes > total / 2  # strict majority
    avg_confidence = sum(r["confidence"] for r in results) / total

    # Use the most confident frame's method info
    method = results[0]["method"] + f"_multi({live_votes}/{total})"
    model_loaded = results[0]["model_loaded"]

    logger.warning(
        "[LIVENESS MULTI] frames=%d, live_votes=%d, is_live=%s, avg_confidence=%.4f",
        total, live_votes, is_live, avg_confidence,
    )

    return {
        "is_live": is_live,
        "confidence": avg_confidence,
        "method": method,
        "model_loaded": model_loaded,
    }


@router.post("/check")
def attendance_check(
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] = File(default=[]),
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

    # 兼容旧前端单文件上传（file）和新前端多帧上传（files）
    if files:
        upload_files = files
    elif file is not None:
        upload_files = [file]
    else:
        raise HTTPException(status_code=400, detail="请上传至少一张图片")

    # 解码所有帧
    decoded_frames = []
    first_bytes = None
    for i, f in enumerate(upload_files):
        img, img_bytes = _decode_upload(f)
        decoded_frames.append(img)
        if i == 0:
            first_bytes = img_bytes
        logger.info(
            "[FACE DEBUG] Frame %d shape=%s, dtype=%s, mean=%.1f",
            i, img.shape, img.dtype, float(img.mean()),
        )

    # 人脸检测和裁剪（对每帧）
    from app.services.face_pipeline import get_pipeline
    pipeline = get_pipeline()

    face_crops = []
    first_faces = None
    for i, img in enumerate(decoded_frames):
        face_crop, faces = _detect_and_crop_face(img, pipeline)
        logger.info("[FACE DEBUG] Frame %d detect_faces returned %d faces", i, len(faces))
        if not faces:
            raise HTTPException(
                status_code=400,
                detail=f"第{i+1}帧未检测到人脸。图片尺寸={img.shape[1]}x{img.shape[0]}，请确保人脸清晰可见、正对摄像头。"
            )
        face_crops.append(face_crop)
        if first_faces is None:
            first_faces = faces

    # 纹理活体检测（多帧投票）
    live_result = _run_liveness_multi(face_crops)

    # 人脸识别和情绪分析只用第一帧
    first_img = decoded_frames[0]
    embedding = first_faces[0].normed_embedding
    best_id, confidence = pipeline.match_1_to_N(
        embedding, threshold=settings.FACE_SIMILARITY_THRESHOLD
    )
    matched_student = next(
        (student for student in students if student.student_id == best_id), None
    )
    logger.info(
        "[FACE DEBUG] faces_detected=%d, matched=%s, best_id=%s, confidence=%.4f",
        len(first_faces),
        matched_student.name if matched_student else "None",
        best_id,
        confidence,
    )

    emotion_prediction = analyze_image_emotion(
        first_bytes,
        fallback_seed=(upload_files[0].filename or "attendance") + str(matched_student.student_id if matched_student else 0),
    )
    emotion = emotion_prediction.emotion
    check_time = datetime.now(timezone.utc)

    # 活体检测策略：模型加载成功且判定为假 → 拒绝
    if live_result["model_loaded"] and not live_result["is_live"]:
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
