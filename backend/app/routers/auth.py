from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.database import get_db
from app.db.models import Student, User
from app.schemas.auth import CurrentUserResponse, LoginRequest, RegisterRequest

router = APIRouter()


def success(data: dict, message: str = "success") -> dict:
    return {"code": 200, "message": message, "data": data}


def build_user_payload(user: User, db: Session) -> dict:
    student = None
    if user.student_id is not None:
        student = db.query(Student).filter(Student.student_id == user.student_id).first()

    data = CurrentUserResponse(
        username=user.username,
        role=user.role,
        student_id=user.student_id,
        student_no=student.student_no if student else None,
        name=student.name if student else None,
    )
    return data.model_dump()


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="密码长度至少 6 位")

    exists = db.query(User).filter(User.username == username).first()
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在")

    student_id = None
    if payload.role == "student":
        student_no = (payload.student_no or "").strip()
        if not student_no:
            raise HTTPException(status_code=400, detail="学生注册必须填写学号")

        student = db.query(Student).filter(Student.student_no == student_no).first()
        if not student:
            raise HTTPException(status_code=404, detail="未找到该学号，请先由教师导入学生信息")

        bound_user = db.query(User).filter(User.student_id == student.student_id).first()
        if bound_user:
            raise HTTPException(status_code=400, detail="该学生已绑定账号")
        student_id = student.student_id
    else:
        teacher_no = (payload.teacher_no or "").strip()
        if not teacher_no:
            raise HTTPException(status_code=400, detail="教师注册必须填写工号")

    user = User(
        username=username,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        student_id=student_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.username, "role": user.role, "student_id": user.student_id})
    return success({"access_token": token, "token_type": "bearer", "user": build_user_payload(user, db)}, message="注册成功")


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    token = create_access_token({"sub": user.username, "role": user.role, "student_id": user.student_id})
    return success({"access_token": token, "token_type": "bearer"})


@router.get("/me", response_model=None)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success(build_user_payload(user, db))


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    return success({"message": f"{user.username} 已退出登录"})
