from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    username: str
    role: str
    student_id: int | None = None


class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: dict
    timestamp: datetime = datetime.utcnow()
