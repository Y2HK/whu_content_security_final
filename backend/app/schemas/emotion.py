from pydantic import BaseModel


class EmotionStatisticItem(BaseModel):
    emotion: str
    count: int


class EmotionTimelineItem(BaseModel):
    scene: str
    emotion: str
    timestamp: str
    student_name: str
