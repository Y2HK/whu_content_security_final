from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: Literal["teacher", "student"]
    student_no: str | None = None
    teacher_no: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    username: str
    role: str
    student_id: int | None = None
    student_no: str | None = None
    name: str | None = None


class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: dict
    timestamp: datetime = datetime.utcnow()
