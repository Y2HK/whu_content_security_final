from datetime import datetime

from pydantic import BaseModel


class AttendanceCheckResponse(BaseModel):
    student_id: int | None
    student_no: str | None
    name: str | None
    check_time: datetime
    status: str
    emotion: str | None
    emotion_confidence: float | None = None
    emotion_source: str | None = None
    confidence: float
    live_result: dict


class AttendanceRecordResponse(BaseModel):
    record_id: int
    student_id: int
    student_no: str
    name: str
    class_name: str
    check_time: datetime
    status: str
    is_live: bool
    live_method: str | None
    emotion: str | None
    confidence: float | None
