from datetime import date, datetime

from pydantic import BaseModel


class GroupParticipantResponse(BaseModel):
    student_id: int
    student_no: str
    name: str
    confidence: float
    emotion: str | None
    emotion_confidence: float | None = None
    emotion_source: str | None = None


class GroupUploadResponse(BaseModel):
    activity_id: int
    activity_name: str
    event_date: date
    participant_count: int
    participants: list[GroupParticipantResponse]


class ActivitySummaryResponse(BaseModel):
    activity_id: int
    activity_name: str
    event_date: date
    participant_count: int
    created_at: datetime | None
