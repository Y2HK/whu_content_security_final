from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./attendance.db"
    SECRET_KEY: str = "change-me-in-course-design"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MODEL_DIR: Path = BASE_DIR / "models"
    ENABLE_EMOTION_MODEL: bool = True
    EMOTION_DETECTOR_BACKEND: str = "opencv"
    FACE_SIMILARITY_THRESHOLD: float = 0.6
    GROUP_FACE_SIMILARITY_THRESHOLD: float = 0.55
    DEFAULT_TEACHER_USERNAME: str = "teacher"
    DEFAULT_TEACHER_PASSWORD: str = "teacher123"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
