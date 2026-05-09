from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user, require_teacher
from app.db.database import get_db
from app.db.models import FaceFeature, Student, User
from app.schemas.student import StudentCreate, StudentUpdate
from app.services.face_service import (
    add_student_to_gallery,
    build_face_feature_from_path,
    parse_students_csv,
    remove_student_from_gallery,
    save_upload_file,
)

router = APIRouter()


def success(data: dict | list, message: str = "success") -> dict:
    return {"code": 200, "message": message, "data": data}


def serialize_student(item: Student) -> dict:
    return {
        "student_id": item.student_id,
        "student_no": item.student_no,
        "name": item.name,
        "class_name": item.class_name,
        "face_image_path": item.face_image_path,
        "created_at": item.created_at,
    }


@router.get("")
def list_students(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Student)
    if user.role != "teacher":
        if user.student_id is None:
            return success([])
        query = query.filter(Student.student_id == user.student_id)

    students = query.order_by(Student.student_id.desc()).all()
    return success([serialize_student(item) for item in students])


@router.post("")
def create_student(payload: StudentCreate, db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    exists = db.query(Student).filter(Student.student_no == payload.student_no).first()
    if exists:
        raise HTTPException(status_code=400, detail="学号已存在")

    student = Student(student_no=payload.student_no, name=payload.name, class_name=payload.class_name)
    db.add(student)
    db.commit()
    db.refresh(student)
    return success(serialize_student(student))


@router.put("/{student_id}")
def update_student(student_id: int, payload: StudentUpdate, db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    duplicated = db.query(Student).filter(Student.student_no == payload.student_no, Student.student_id != student_id).first()
    if duplicated:
        raise HTTPException(status_code=400, detail="学号已存在")

    student.student_no = payload.student_no
    student.name = payload.name
    student.class_name = payload.class_name
    db.commit()
    db.refresh(student)
    return success(serialize_student(student))


@router.delete("/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    db.query(FaceFeature).filter(FaceFeature.student_id == student_id).delete()
    db.delete(student)
    db.commit()
    remove_student_from_gallery(student_id)
    return success({"deleted": True, "student_id": student_id})


@router.post("/{student_id}/face")
async def upload_student_face(
    student_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    if user.role != "teacher" and user.student_id != student_id:
        raise HTTPException(status_code=403, detail="只能上传自己的学生人脸")

    suffix = Path(file.filename or "face.jpg").suffix or ".jpg"
    destination = settings.UPLOAD_DIR / "students" / f"student_{student_id}{suffix}"
    await save_upload_file(file, destination)

    student.face_image_path = str(destination).replace("\\", "/")
    db.query(FaceFeature).filter(FaceFeature.student_id == student_id).delete()
    feature_vector = build_face_feature_from_path(student.face_image_path)
    db.add(FaceFeature(student_id=student_id, feature_vector=feature_vector))
    db.commit()
    db.refresh(student)
    add_student_to_gallery(student_id, feature_vector)

    return success({
        "student_id": student.student_id,
        "face_image_path": student.face_image_path,
        "feature_generated": True,
    })


@router.post("/batch")
async def batch_import_students(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    temp_path = settings.UPLOAD_DIR / "imports" / (file.filename or "students.csv")
    await save_upload_file(file, temp_path)
    rows = parse_students_csv(temp_path)

    created = 0
    skipped = 0
    for row in rows:
        student_no = (row.get("student_no") or "").strip()
        name = (row.get("name") or "").strip()
        class_name = (row.get("class_name") or "").strip()
        if not student_no or not name or not class_name:
            skipped += 1
            continue
        exists = db.query(Student).filter(Student.student_no == student_no).first()
        if exists:
            skipped += 1
            continue
        db.add(Student(student_no=student_no, name=name, class_name=class_name))
        created += 1

    db.commit()
    return success({"created": created, "skipped": skipped})
