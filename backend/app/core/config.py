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
    EMOTION_PROVIDER: str = "hsemotion_onnx"
    HSEMOTION_MODEL_PATH: Path = MODEL_DIR / "hsemotion" / "enet_b0_8_best_vgaf.onnx"
    FERPLUS_MODEL_PATH: Path = MODEL_DIR / "emotion-ferplus-8.onnx"
    EMOTION_DETECTOR_BACKEND: str = "opencv"
    EMOTION_MIN_CONFIDENCE: float = 0.2
    CAMERA_EMOTION_MIN_CONFIDENCE: float = 0.2
    FACE_SIMILARITY_THRESHOLD: float = 0.6
    GROUP_FACE_SIMILARITY_THRESHOLD: float = 0.55
    DEFAULT_TEACHER_USERNAME: str = "teacher"
    DEFAULT_TEACHER_PASSWORD: str = "teacher123"
    ENABLE_LIVENESS: bool = True
    LIVENESS_THRESHOLD: float = 0.5
    CUSTOM_MODEL_PATH: Path = MODEL_DIR / "custom_live.pth"
    CDCN_MODEL_PATH: Path = MODEL_DIR / "cdcn_live.pth"
    SILENT_FACE_MODEL_PATH: Path = MODEL_DIR / "silent_face"
    MINIFASNET_MODEL_PATH: Path = MODEL_DIR / "minifasnet_v2.onnx"
    FACE_DATA_DIR: Path = BASE_DIR.parent / "data" / "face_data"
    AUTO_IMPORT_FACE_DATA: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
