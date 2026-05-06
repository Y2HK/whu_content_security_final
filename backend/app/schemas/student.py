from datetime import datetime

from pydantic import BaseModel


class StudentCreate(BaseModel):
    student_no: str
    name: str
    class_name: str


class StudentUpdate(BaseModel):
    student_no: str
    name: str
    class_name: str


class StudentResponse(BaseModel):
    student_id: int
    student_no: str
    name: str
    class_name: str
    face_image_path: str | None
    created_at: datetime | None

    class Config:
        from_attributes = True
