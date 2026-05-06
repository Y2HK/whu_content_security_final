from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base


class User(Base):
    __tablename__ = "user"

    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="teacher")
    student_id = Column(Integer, ForeignKey("student.student_id"), unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Student(Base):
    __tablename__ = "student"

    student_id = Column(Integer, primary_key=True, index=True)
    student_no = Column(String(20), unique=True, nullable=False)
    name = Column(String(50), nullable=False)
    class_name = Column(String(50), nullable=False)
    face_image_path = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FaceFeature(Base):
    __tablename__ = "face_feature"

    feature_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student.student_id"), nullable=False)
    feature_vector = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Attendance(Base):
    __tablename__ = "attendance"

    record_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student.student_id"), nullable=False)
    check_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False)
    is_live = Column(Boolean, nullable=False, default=False)
    live_method = Column(String(50), nullable=True)
    emotion = Column(String(20), nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Activity(Base):
    __tablename__ = "activity"

    activity_id = Column(Integer, primary_key=True, index=True)
    activity_name = Column(String(100), nullable=False)
    image_path = Column(String(255), nullable=False)
    event_date = Column(Date, nullable=False)
    participant_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ActivityParticipant(Base):
    __tablename__ = "activity_participant"

    participant_id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activity.activity_id"), nullable=False)
    student_id = Column(Integer, ForeignKey("student.student_id"), nullable=False)
    confidence = Column(Float, nullable=True)
    emotion = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
