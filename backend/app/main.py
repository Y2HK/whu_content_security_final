from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import SessionLocal
from app.db.init_db import init_database
from app.routers import attendance, auth, emotion, group, students
from app.services.face_service import load_gallery_from_db
from app.services.face_data_importer import import_face_data_on_startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    db = SessionLocal()
    try:
        import_face_data_on_startup(db)
        load_gallery_from_db(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Class Attendance System MVP",
    version="0.1.0",
    description="课程设计基础版最小可用后端系统",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"code": 200, "message": "success", "data": {"service": "class-attendance-system-mvp"}}


@app.get("/health")
def health():
    return {"code": 200, "message": "success", "data": {"status": "ok"}}


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(students.router, prefix="/api/v1/students", tags=["students"])
app.include_router(attendance.router, prefix="/api/v1/attendance", tags=["attendance"])
app.include_router(group.router, prefix="/api/v1/group", tags=["group"])
app.include_router(emotion.router, prefix="/api/v1/emotion", tags=["emotion"])
