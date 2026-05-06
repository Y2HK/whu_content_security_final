from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import create_access_token, verify_password
from app.db.database import get_db
from app.db.models import User
from app.schemas.auth import CurrentUserResponse, LoginRequest

router = APIRouter()


def success(data: dict, message: str = "success") -> dict:
    return {"code": 200, "message": message, "data": data}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    token = create_access_token({"sub": user.username, "role": user.role, "student_id": user.student_id})
    return success({"access_token": token, "token_type": "bearer"})


@router.get("/me", response_model=None)
def me(user: User = Depends(get_current_user)):
    data = CurrentUserResponse(username=user.username, role=user.role, student_id=user.student_id)
    return success(data.model_dump())


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    return success({"message": f"{user.username} 已退出登录"})
