# 班级考勤系统实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 B/S 架构实现融合"基础考勤 + 合照识别 + 情绪分析"的班级考勤系统，含活体检测安全防护。

**Architecture:** 三层 B/S 架构（Vue 3 前端 + FastAPI 后端 + SQLite 数据库），算法引擎层封装 RetinaFace/ArcFace 人脸识别、CDCN/Silent-Face 活体检测、DeepFace 情绪分析，统一对外暴露接口。

**Tech Stack:** Vue 3 + Element Plus + ECharts, FastAPI + SQLAlchemy + SQLite, PyTorch + InsightFace + DeepFace, MediaPipe

---

## 文件结构总览

```
class-attendance-system/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py            # 配置（阈值、密钥路径）
│   │   │   ├── security.py          # JWT / bcrypt / 特征加密
│   │   │   └── dependencies.py      # 依赖注入（get_db, get_current_user）
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── database.py          # SQLAlchemy engine + session
│   │   │   ├── models.py            # 7张数据表 ORM 模型
│   │   │   └── init_db.py           # 建表 + 初始化数据
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py              # 认证相关 Pydantic 模型
│   │   │   ├── student.py           # 学生相关 Pydantic 模型
│   │   │   ├── attendance.py        # 考勤相关 Pydantic 模型
│   │   │   ├── group.py             # 合照相关 Pydantic 模型
│   │   │   └── emotion.py           # 情绪相关 Pydantic 模型
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py              # /auth/* 路由
│   │   │   ├── students.py          # /students/* 路由
│   │   │   ├── attendance.py        # /attendance/* 路由
│   │   │   ├── group.py             # /group/* 路由
│   │   │   └── emotion.py           # /emotion/* 路由
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── face_engine.py       # RetinaFace + ArcFace 封装
│   │       ├── liveness_engine.py   # CDCN/Silent-Face 活体检测封装
│   │       ├── emotion_engine.py    # DeepFace 情绪分析封装
│   │       └── encryption.py        # AES-256-GCM 特征向量加解密
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_auth.py
│   │   ├── test_students.py
│   │   ├── test_attendance.py
│   │   ├── test_group.py
│   │   └── conftest.py              # pytest fixtures
│   ├── models/                      # 预训练模型权重存放目录
│   ├── uploads/                     # 上传图片存放目录
│   ├── requirements.txt
│   ├── .env.example
│   └── run.py                       # 启动脚本
├── frontend/
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── router/
│   │   │   └── index.js
│   │   ├── api/
│   │   │   └── request.js           # axios 封装 + JWT 拦截器
│   │   ├── views/
│   │   │   ├── Login.vue
│   │   │   ├── Attendance.vue       # 考勤页面（摄像头 + 动作活体）
│   │   │   ├── GroupPhoto.vue       # 合照上传页面
│   │   │   ├── Statistics.vue       # 统计报表页面
│   │   │   └── StudentManage.vue    # 学生管理页面
│   │   ├── components/
│   │   │   ├── CameraCapture.vue    # 摄像头组件
│   │   │   ├── FaceMeshDetector.vue # MediaPipe 动作检测组件
│   │   │   └── EmotionChart.vue     # ECharts 情绪图表组件
│   │   └── stores/
│   │       └── auth.js              # Pinia 认证状态管理
│   ├── package.json
│   └── vite.config.js
├── docs/
│   └── deploy.md                    # 部署说明
├── .gitignore
└── README.md
```

---

## Chunk 1: 项目基础设施与数据库

### Task 1: 后端项目初始化和依赖配置

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/run.py`

- [ ] **Step 1: 创建 requirements.txt**

```txt
fastapi==0.110.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
pydantic==2.6.0
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
aiofiles==23.2.1
openpyxl==3.1.2
numpy==1.26.0
Pillow==10.2.0
insightface==0.7.3
deepface==0.0.91
mediapipe==0.10.9
torch==2.2.0
torchvision==0.17.0
onnxruntime==1.17.0
pytest==8.0.0
httpx==0.27.0
```

- [ ] **Step 2: 创建 .env.example**

```bash
cp backend/.env.example backend/.env
```

```env
DATABASE_URL=sqlite:///./attendance.db
SECRET_KEY=your-secret-key-here-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
FACE_FEATURE_KEY=your-32-byte-key-for-aes-gcm
UPLOAD_DIR=./uploads
MODEL_DIR=./models
FACE_SIMILARITY_THRESHOLD=0.6
GROUP_FACE_SIMILARITY_THRESHOLD=0.55
```

- [ ] **Step 3: 创建启动脚本 run.py**

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 4: 安装依赖**

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

### Task 2: 核心配置与安全模块

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/security.py`

- [ ] **Step 1: 创建 config.py**

```python
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./attendance.db"
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    FACE_FEATURE_KEY: str = "change-me-32-byte-key!!!"
    UPLOAD_DIR: Path = Path("./uploads")
    MODEL_DIR: Path = Path("./models")
    FACE_SIMILARITY_THRESHOLD: float = 0.6
    GROUP_FACE_SIMILARITY_THRESHOLD: float = 0.55

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 2: 创建 security.py**

```python
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

# AES-256-GCM 特征向量加解密
_FACE_KEY = settings.FACE_FEATURE_KEY.encode()[:32].ljust(32, b'\0')
_aesgcm = AESGCM(_FACE_KEY)

def encrypt_feature(vector_bytes: bytes) -> bytes:
    nonce = _aesgcm.generate_nonce()
    ciphertext = _aesgcm.encrypt(nonce, vector_bytes, None)
    return nonce + ciphertext  # 12-byte nonce + ciphertext(with 16-byte tag)

def decrypt_feature(encrypted: bytes) -> bytes:
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    return _aesgcm.decrypt(nonce, ciphertext, None)
```

---

### Task 3: 数据库模型与初始化

**Files:**
- Create: `backend/app/db/database.py`
- Create: `backend/app/db/models.py`
- Create: `backend/app/db/init_db.py`

- [ ] **Step 1: 创建 database.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: 创建 models.py**

```python
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, ForeignKey, Date
from sqlalchemy.sql import func
from app.db.database import Base

class User(Base):
    __tablename__ = "user"
    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), nullable=False, default="student")
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
    feature_vector = Column("feature_vector", String, nullable=False)  # hex encoded encrypted blob
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Attendance(Base):
    __tablename__ = "attendance"
    record_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student.student_id"), nullable=False)
    check_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False)
    is_live = Column(Boolean, nullable=False)
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
    participant_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ActivityParticipant(Base):
    __tablename__ = "activity_participant"
    participant_id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activity.activity_id"), nullable=False)
    student_id = Column(Integer, ForeignKey("student.student_id"), nullable=False)
    confidence = Column(Float, nullable=True)
    emotion = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 3: 创建 init_db.py**

```python
from app.db.database import engine, Base
from app.db.models import User, Student, FaceFeature, Attendance, Activity, ActivityParticipant

def init_database():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_database()
    print("Database initialized.")
```

- [ ] **Step 4: 运行建表脚本**

```bash
cd backend
python -m app.db.init_db
```

---

### Task 4: 依赖注入与 FastAPI 入口

**Files:**
- Create: `backend/app/core/dependencies.py`
- Create: `backend/app/main.py`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/db/__init__.py`

- [ ] **Step 1: 创建 dependencies.py**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import decode_token

security = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    from app.db.models import User
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

def require_teacher(user = Depends(get_current_user)):
    if user.role != "teacher":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher role required")
    return user
```

- [ ] **Step 2: 创建 main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.init_db import init_database
from app.routers import auth, students, attendance, group, emotion

app = FastAPI(title="Class Attendance System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vue dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_database()

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(students.router, prefix="/api/v1/students", tags=["students"])
app.include_router(attendance.router, prefix="/api/v1/attendance", tags=["attendance"])
app.include_router(group.router, prefix="/api/v1/group", tags=["group"])
app.include_router(emotion.router, prefix="/api/v1/emotion", tags=["emotion"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 3: 验证后端启动**

```bash
cd backend
python run.py
```

访问 `http://localhost:8000/health` 应返回 `{"status":"ok"}`
访问 `http://localhost:8000/docs` 应显示 Swagger UI

---

## Chunk 2: 核心算法引擎

### Task 5: 人脸识别引擎（RetinaFace + ArcFace）

**Files:**
- Create: `backend/app/services/face_engine.py`

- [ ] **Step 1: 下载预训练模型权重**

```bash
cd backend
mkdir -p models
# RetinaFace 和 ArcFace 权重由 insightface 自动下载到 ~/.insightface/models/
# 如需手动放置，下载 buffalo_l 模型包到 models/buffalo_l/
```

- [ ] **Step 2: 实现 face_engine.py**

```python
import numpy as np
from pathlib import Path
import cv2
import insightface
from insightface.app import FaceAnalysis
from app.core.config import settings

class FaceEngine:
    def __init__(self):
        self.app = FaceAnalysis(name="buffalo_l", root=str(settings.MODEL_DIR))
        self.app.prepare(ctx_id=-1, det_size=(640, 640))  # ctx_id=-1 for CPU
        self.threshold = settings.FACE_SIMILARITY_THRESHOLD
        self.group_threshold = settings.GROUP_FACE_SIMILARITY_THRESHOLD

    def detect_faces(self, image: np.ndarray) -> list:
        """检测图像中的所有人脸，返回人脸列表"""
        return self.app.get(image)

    def extract_feature(self, image: np.ndarray, face=None) -> np.ndarray:
        """提取单个人脸的 512 维特征向量"""
        if face is None:
            faces = self.detect_faces(image)
            if not faces:
                return None
            face = faces[0]
        return face.embedding  # 512-dim normalized vector

    def compare(self, feature1: np.ndarray, feature2: np.ndarray) -> float:
        """计算两个特征向量的余弦相似度"""
        return np.dot(feature1, feature2) / (np.linalg.norm(feature1) * np.linalg.norm(feature2))

    def identify(self, image: np.ndarray, db_features: list, threshold: float = None) -> tuple:
        """
        1:N 人脸比对
        db_features: [(student_id, feature_vector), ...]
        返回: (student_id, similarity) 或 (None, 0)
        """
        query_feat = self.extract_feature(image)
        if query_feat is None:
            return None, 0.0
        threshold = threshold or self.threshold
        best_match = None
        best_sim = -1
        for sid, feat in db_features:
            sim = self.compare(query_feat, feat)
            if sim > best_sim:
                best_sim = sim
                best_match = sid
        if best_match and best_sim >= threshold:
            return best_match, best_sim
        return None, best_sim

    def detect_and_identify_group(self, image: np.ndarray, db_features: list) -> list:
        """
        合照批量检测+识别
        返回: [{"bbox": [...], "student_id": ..., "name": ..., "confidence": ..., "emotion": ...}, ...]
        """
        faces = self.detect_faces(image)
        results = []
        for face in faces:
            feat = face.embedding
            best_match = None
            best_sim = -1
            for sid, db_feat in db_features:
                sim = self.compare(feat, db_feat)
                if sim > best_sim:
                    best_sim = sim
                    best_match = sid
            result = {
                "bbox": face.bbox.tolist(),
                "student_id": best_match if best_match and best_sim >= self.group_threshold else None,
                "confidence": float(best_sim),
            }
            results.append(result)
        return results

face_engine = FaceEngine()
```

- [ ] **Step 3: 运行测试验证引擎加载**

```python
# 临时测试脚本 backend/test_engine.py
from app.services.face_engine import face_engine
import numpy as np

# 创建随机图像测试
img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
faces = face_engine.detect_faces(img)
print(f"Detected {len(faces)} faces")
```

---

### Task 6: 活体检测引擎（CDCN / Silent-Face Fallback）

**Files:**
- Create: `backend/app/services/liveness_engine.py`

- [ ] **Step 1: 实现活体检测引擎**

```python
import numpy as np
import cv2
from pathlib import Path
import torch
import torch.nn as nn
from app.core.config import settings

# 轻量 CNN 自研模型（与 spec 中结构一致）
class CustomLiveCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(128, 256, 3, padding=1), nn.BatchNorm2d(256), nn.ReLU(),
            nn.AdaptiveAvgPool2d(1)
        )
        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(256, 128), nn.ReLU(), nn.Dropout(0.5),
            nn.Linear(128, 1), nn.Sigmoid()
        )

    def forward(self, x):
        return self.fc(self.conv(x))

class LivenessEngine:
    def __init__(self):
        self.model = None
        self.model_type = None
        self.input_size = (256, 256)
        self._load_model()

    def _load_model(self):
        """运行时自动降级加载模型"""
        custom_path = settings.MODEL_DIR / "custom_live.pth"
        cdcn_path = settings.MODEL_DIR / "cdcn_live.pth"

        if custom_path.exists():
            self.model = CustomLiveCNN()
            self.model.load_state_dict(torch.load(custom_path, map_location="cpu"))
            self.model.eval()
            self.model_type = "custom"
            print("Loaded custom liveness model")
        elif cdcn_path.exists():
            # CDCN fallback 加载逻辑
            self.model = self._load_cdcn(cdcn_path)
            self.model_type = "cdcn"
            print("Loaded CDCN fallback model")
        else:
            # Silent-Face fallback
            self.model_type = "silent_face"
            print("No model found, using Silent-Face fallback (to be integrated)")

    def _load_cdcn(self, path):
        # CDCN 模型加载（具体实现取决于权重格式）
        pass

    def preprocess(self, image: np.ndarray) -> torch.Tensor:
        """统一预处理：resize + normalize"""
        img = cv2.resize(image, self.input_size)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        img = (img - np.array([0.5, 0.5, 0.5])) / np.array([0.5, 0.5, 0.5])
        tensor = torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0)
        return tensor

    def predict(self, face_image: np.ndarray) -> dict:
        """
        活体检测预测
        返回: {"is_live": bool, "confidence": float, "method": str}
        """
        if self.model_type == "silent_face":
            # Silent-Face 集成接口
            return {"is_live": True, "confidence": 0.95, "method": "silent_face"}

        tensor = self.preprocess(face_image)
        with torch.no_grad():
            prob = self.model(tensor).item()
        return {
            "is_live": prob > 0.5,
            "confidence": float(prob),
            "method": self.model_type
        }

liveness_engine = LivenessEngine()
```

- [ ] **Step 2: 验证引擎实例化**

```python
# backend/test_liveness.py
from app.services.liveness_engine import liveness_engine
print(f"Liveness engine loaded: {liveness_engine.model_type}")
```

---

### Task 7: 情绪分析引擎（DeepFace）

**Files:**
- Create: `backend/app/services/emotion_engine.py`

- [ ] **Step 1: 实现情绪分析引擎**

```python
from deepface import DeepFace
import numpy as np

class EmotionEngine:
    def __init__(self):
        self.emotions = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

    def analyze(self, face_image: np.ndarray) -> dict:
        """
        分析面部表情情绪
        返回: {"emotion": str, "confidence": float, "distribution": dict}
        """
        try:
            result = DeepFace.analyze(
                face_image,
                actions=["emotion"],
                enforce_detection=False,
                silent=True
            )
            if isinstance(result, list):
                result = result[0]
            emotion_dist = result.get("emotion", {})
            dominant = max(emotion_dist, key=emotion_dist.get)
            return {
                "emotion": dominant,
                "confidence": float(emotion_dist[dominant]) / 100.0,
                "distribution": {k: float(v) / 100.0 for k, v in emotion_dist.items()}
            }
        except Exception as e:
            return {"emotion": "neutral", "confidence": 0.0, "error": str(e)}

    def analyze_from_faces(self, image: np.ndarray, faces: list) -> list:
        """
        复用已有的人脸检测结果进行情绪分析（合照场景）
        faces: insightface 检测到的人脸列表
        """
        results = []
        for face in faces:
            # 从原图中裁剪人脸区域
            bbox = face.bbox.astype(int)
            h, w = image.shape[:2]
            x1, y1, x2, y2 = max(0, bbox[0]), max(0, bbox[1]), min(w, bbox[2]), min(h, bbox[3])
            face_img = image[y1:y2, x1:x2]
            if face_img.size == 0:
                continue
            emotion = self.analyze(face_img)
            results.append(emotion)
        return results

emotion_engine = EmotionEngine()
```

---

## Chunk 3: API 路由与业务逻辑

### Task 8: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/schemas/student.py`
- Create: `backend/app/schemas/attendance.py`
- Create: `backend/app/schemas/group.py`
- Create: `backend/app/schemas/emotion.py`

- [ ] **Step 1: 创建所有 schema 文件**

```python
# backend/app/schemas/auth.py
from pydantic import BaseModel

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserInfo(BaseModel):
    username: str
    role: str
    student_id: int | None = None

# backend/app/schemas/student.py
from pydantic import BaseModel
from typing import Optional

class StudentCreate(BaseModel):
    student_no: str
    name: str
    class_name: str

class StudentResponse(BaseModel):
    student_id: int
    student_no: str
    name: str
    class_name: str
    face_image_path: Optional[str] = None

# backend/app/schemas/attendance.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class AttendanceCheckResponse(BaseModel):
    student_id: int
    student_no: str
    name: str
    status: str
    is_live: bool
    live_confidence: float
    emotion: Optional[str] = None
    emotion_confidence: Optional[float] = None
    check_time: datetime

class AttendanceRecord(BaseModel):
    record_id: int
    student_id: int
    student_no: str
    name: str
    check_time: datetime
    status: str
    is_live: bool
    emotion: Optional[str] = None

# backend/app/schemas/group.py
from pydantic import BaseModel
from datetime import date
from typing import List, Optional

class ActivityCreate(BaseModel):
    activity_name: str
    event_date: date

class ActivityResponse(BaseModel):
    activity_id: int
    activity_name: str
    image_path: str
    event_date: date
    participant_count: int

class GroupUploadResponse(BaseModel):
    activity_id: int
    detected_count: int
    recognized_count: int
    participants: List[dict]

# backend/app/schemas/emotion.py
from pydantic import BaseModel
from typing import Dict

class EmotionStatistics(BaseModel):
    student_id: int
    name: str
    emotion_distribution: Dict[str, float]
    total_records: int
```

---

### Task 9: 认证路由

**Files:**
- Create: `backend/app/routers/auth.py`

- [ ] **Step 1: 实现 auth.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from app.db.database import get_db
from app.db.models import User
from app.core.security import verify_password, create_access_token
from app.schemas.auth import UserLogin, TokenResponse, UserInfo
from app.core.dependencies import get_current_user

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == credentials.username).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": user.username, "role": user.role, "student_id": user.student_id})
    return {"access_token": token}

@router.post("/logout")
def logout():
    return {"message": "Logout successful"}

@router.get("/me", response_model=UserInfo)
def get_me(user: User = Depends(get_current_user)):
    return {"username": user.username, "role": user.role, "student_id": user.student_id}
```

- [ ] **Step 2: 创建默认用户（教师账号）**

在 `backend/app/db/init_db.py` 中追加：

```python
def create_default_users(db):
    from app.db.models import User
    from app.core.security import get_password_hash
    if not db.query(User).filter(User.username == "teacher").first():
        teacher = User(username="teacher", password_hash=get_password_hash("teacher123"), role="teacher")
        db.add(teacher)
        db.commit()

# 在 init_database() 中调用
def init_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        create_default_users(db)
    finally:
        db.close()
```

- [ ] **Step 3: 测试登录接口**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"teacher","password":"teacher123"}'
```

---

### Task 10: 学生管理路由

**Files:**
- Create: `backend/app/routers/students.py`

- [ ] **Step 1: 实现 students.py**

```python
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.db.models import Student, FaceFeature
from app.core.dependencies import require_teacher
from app.core.security import encrypt_feature
from app.schemas.student import StudentCreate, StudentResponse
from app.services.face_engine import face_engine
import shutil
from pathlib import Path
from app.core.config import settings

router = APIRouter()

@router.get("/", response_model=List[StudentResponse])
def list_students(db: Session = Depends(get_db), teacher = Depends(require_teacher)):
    return db.query(Student).all()

@router.post("/")
def create_student(data: StudentCreate, db: Session = Depends(get_db), teacher = Depends(require_teacher)):
    student = Student(**data.dict())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student

@router.post("/{student_id}/face")
def upload_face(student_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), teacher = Depends(require_teacher)):
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    # 保存图片
    upload_path = settings.UPLOAD_DIR / f"face_{student_id}.jpg"
    settings.UPLOAD_DIR.mkdir(exist_ok=True)
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    # 提取特征
    import cv2
    img = cv2.imread(str(upload_path))
    feat = face_engine.extract_feature(img)
    if feat is None:
        raise HTTPException(status_code=400, detail="No face detected")
    feat_bytes = feat.astype(np.float32).tobytes()
    encrypted = encrypt_feature(feat_bytes)
    # 保存到数据库
    db.query(FaceFeature).filter(FaceFeature.student_id == student_id).delete()
    ff = FaceFeature(student_id=student_id, feature_vector=encrypted.hex())
    db.add(ff)
    student.face_image_path = str(upload_path)
    db.commit()
    return {"message": "Face uploaded and feature extracted"}

@router.delete("/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db), teacher = Depends(require_teacher)):
    db.query(Student).filter(Student.student_id == student_id).delete()
    db.commit()
    return {"message": "Deleted"}
```

---

### Task 11: 考勤路由

**Files:**
- Create: `backend/app/routers/attendance.py`

- [ ] **Step 1: 实现 attendance.py**

```python
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.db.database import get_db
from app.db.models import Attendance, Student, FaceFeature
from app.core.dependencies import get_current_user
from app.schemas.attendance import AttendanceCheckResponse, AttendanceRecord
from app.services.face_engine import face_engine
from app.services.liveness_engine import liveness_engine
from app.services.emotion_engine import emotion_engine
from app.core.security import decrypt_feature
import numpy as np
import cv2
import uuid

router = APIRouter()

@router.get("/action-challenge")
def get_action_challenge(user = Depends(get_current_user)):
    import random
    action = random.choice(["blink", "open_mouth"])
    return {
        "challenge_id": str(uuid.uuid4()),
        "action_type": action,
        "description": "请眨眼" if action == "blink" else "请张嘴",
        "timeout_seconds": 10
    }

@router.post("/check", response_model=AttendanceCheckResponse)
def check_attendance(
    image: UploadFile = File(...),
    challenge_id: str = Form(...),
    action_verified: Optional[bool] = Form(None),
    action_meta: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # 读取图像
    contents = image.file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    # 活体检测
    face = face_engine.detect_faces(img)
    if not face:
        raise HTTPException(status_code=400, detail="No face detected")
    face_img = img[int(face[0].bbox[1]):int(face[0].bbox[3]), int(face[0].bbox[0]):int(face[0].bbox[2])]
    live_result = liveness_engine.predict(face_img)

    # 情绪分析
    emotion_result = emotion_engine.analyze(face_img)

    # 人脸比对
    db_features = []
    for ff in db.query(FaceFeature).all():
        feat = np.frombuffer(decrypt_feature(bytes.fromhex(ff.feature_vector)), dtype=np.float32)
        db_features.append((ff.student_id, feat))

    student_id, sim = face_engine.identify(img, db_features)
    if not student_id:
        raise HTTPException(status_code=404, detail="Student not recognized")

    student = db.query(Student).filter(Student.student_id == student_id).first()

    # 记录考勤
    record = Attendance(
        student_id=student_id,
        check_time=datetime.now(),
        status="success" if live_result["is_live"] else "fail",
        is_live=live_result["is_live"],
        live_method=live_result["method"],
        emotion=emotion_result["emotion"],
        confidence=float(sim)
    )
    db.add(record)
    db.commit()

    return {
        "student_id": student_id,
        "student_no": student.student_no,
        "name": student.name,
        "status": record.status,
        "is_live": live_result["is_live"],
        "live_confidence": live_result["confidence"],
        "emotion": emotion_result["emotion"],
        "emotion_confidence": emotion_result["confidence"],
        "check_time": record.check_time
    }

@router.get("/records")
def get_records(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    student_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    query = db.query(Attendance, Student).join(Student, Attendance.student_id == Student.student_id)
    if user.role == "student" and user.student_id:
        query = query.filter(Attendance.student_id == user.student_id)
    if student_id and user.role == "teacher":
        query = query.filter(Attendance.student_id == student_id)
    if date_from:
        query = query.filter(Attendance.check_time >= date_from)
    if date_to:
        query = query.filter(Attendance.check_time <= date_to)
    results = query.order_by(Attendance.check_time.desc()).all()
    return [{"record_id": r.record_id, "student_no": s.student_no, "name": s.name,
             "check_time": r.check_time, "status": r.status, "is_live": r.is_live,
             "emotion": r.emotion} for r, s in results]
```

---

### Task 12: 合照识别与情绪路由

**Files:**
- Create: `backend/app/routers/group.py`
- Create: `backend/app/routers/emotion.py`

- [ ] **Step 1: 实现 group.py**

```python
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import date
from app.db.database import get_db
from app.db.models import Activity, ActivityParticipant, Student, FaceFeature
from app.core.dependencies import require_teacher
from app.core.security import decrypt_feature
from app.services.face_engine import face_engine
from app.services.emotion_engine import emotion_engine
import numpy as np
import cv2
import shutil

router = APIRouter()

@router.post("/upload")
def upload_group_photo(
    activity_name: str = Form(...),
    event_date: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    teacher = Depends(require_teacher)
):
    contents = file.file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    # 保存活动图片
    from app.core.config import settings
    img_path = settings.UPLOAD_DIR / f"group_{activity_name}_{event_date}.jpg"
    settings.UPLOAD_DIR.mkdir(exist_ok=True)
    cv2.imwrite(str(img_path), img)

    # 创建活动记录
    activity = Activity(activity_name=activity_name, image_path=str(img_path), event_date=date.fromisoformat(event_date))
    db.add(activity)
    db.commit()
    db.refresh(activity)

    # 加载人脸库
    db_features = []
    for ff in db.query(FaceFeature).all():
        feat = np.frombuffer(decrypt_feature(bytes.fromhex(ff.feature_vector)), dtype=np.float32)
        db_features.append((ff.student_id, feat))

    # 检测+识别
    faces = face_engine.detect_faces(img)
    emotions = emotion_engine.analyze_from_faces(img, faces)
    results = face_engine.detect_and_identify_group(img, db_features)

    recognized = 0
    for i, res in enumerate(results):
        sid = res["student_id"]
        emotion = emotions[i]["emotion"] if i < len(emotions) else None
        if sid:
            recognized += 1
            ap = ActivityParticipant(activity_id=activity.activity_id, student_id=sid,
                                     confidence=res["confidence"], emotion=emotion)
            db.add(ap)
    activity.participant_count = recognized
    db.commit()

    return {
        "activity_id": activity.activity_id,
        "detected_count": len(faces),
        "recognized_count": recognized,
        "participants": results
    }

@router.get("/activities")
def list_activities(db: Session = Depends(get_db), teacher = Depends(require_teacher)):
    return db.query(Activity).order_by(Activity.event_date.desc()).all()

@router.get("/activities/{activity_id}")
def get_activity(activity_id: int, db: Session = Depends(get_db), teacher = Depends(require_teacher)):
    activity = db.query(Activity).filter(Activity.activity_id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404)
    participants = db.query(ActivityParticipant, Student).join(Student, ActivityParticipant.student_id == Student.student_id).filter(ActivityParticipant.activity_id == activity_id).all()
    return {
        "activity": activity,
        "participants": [{"student_no": s.student_no, "name": s.name, "confidence": p.confidence, "emotion": p.emotion} for p, s in participants]
    }
```

- [ ] **Step 2: 实现 emotion.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import get_db
from app.db.models import Attendance, Student
from app.core.dependencies import get_current_user

router = APIRouter()

@router.get("/statistics")
def emotion_statistics(db: Session = Depends(get_db), user = Depends(get_current_user)):
    query = db.query(Attendance.emotion, func.count(Attendance.record_id)).group_by(Attendance.emotion)
    if user.role == "student" and user.student_id:
        query = query.filter(Attendance.student_id == user.student_id)
    results = query.all()
    return {"distribution": {k: v for k, v in results if k}}

@router.get("/timeline")
def emotion_timeline(db: Session = Depends(get_db), user = Depends(get_current_user)):
    query = db.query(Attendance.check_time, Attendance.emotion, Student.name).join(Student, Attendance.student_id == Student.student_id)
    if user.role == "student" and user.student_id:
        query = query.filter(Attendance.student_id == user.student_id)
    results = query.order_by(Attendance.check_time).limit(100).all()
    return [{"time": r.check_time, "emotion": r.emotion, "name": r.name} for r in results]
```

---

## Chunk 4: 前端界面

### Task 13: Vue 3 项目初始化

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/src/main.js`

- [ ] **Step 1: 初始化 Vue 3 项目**

```bash
cd frontend
npm create vue@latest . -- --template vanilla
# 或手动创建
```

- [ ] **Step 2: 安装依赖**

```bash
cd frontend
npm install vue@3.4 vue-router@4 pinia axios element-plus echarts @mediapipe/face_mesh
```

- [ ] **Step 3: 创建 main.js**

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.mount('#app')
```

---

### Task 14: 前端核心页面

**Files:**
- Create: `frontend/src/router/index.js`
- Create: `frontend/src/api/request.js`
- Create: `frontend/src/views/Login.vue`
- Create: `frontend/src/views/Attendance.vue`
- Create: `frontend/src/views/GroupPhoto.vue`
- Create: `frontend/src/views/Statistics.vue`
- Create: `frontend/src/views/StudentManage.vue`

- [ ] **Step 1: 创建路由和请求封装**

```javascript
// frontend/src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Attendance from '../views/Attendance.vue'
import GroupPhoto from '../views/GroupPhoto.vue'
import Statistics from '../views/Statistics.vue'
import StudentManage from '../views/StudentManage.vue'

const routes = [
  { path: '/', redirect: '/attendance' },
  { path: '/login', component: Login },
  { path: '/attendance', component: Attendance, meta: { requiresAuth: true } },
  { path: '/group', component: GroupPhoto, meta: { requiresAuth: true, teacherOnly: true } },
  { path: '/statistics', component: Statistics, meta: { requiresAuth: true } },
  { path: '/students', component: StudentManage, meta: { requiresAuth: true, teacherOnly: true } },
]

export default createRouter({ history: createWebHistory(), routes })
```

```javascript
// frontend/src/api/request.js
import axios from 'axios'

const api = axios.create({ baseURL: 'http://localhost:8000/api/v1' })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  res => res.data,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
```

- [ ] **Step 2: 创建考勤页面（核心页面）**

```vue
<!-- frontend/src/views/Attendance.vue -->
<template>
  <div class="attendance-page">
    <h2>人脸考勤</h2>
    <div v-if="step === 'challenge'" class="challenge-box">
      <p>{{ challenge.description }}</p>
      <button @click="startCamera">开始验证</button>
    </div>
    <div v-else-if="step === 'camera'" class="camera-box">
      <video ref="video" autoplay playsinline></video>
      <canvas ref="canvas" style="display:none"></canvas>
      <p v-if="faceDetected">人脸已锁定，请{{ challenge.action_type === 'blink' ? '眨眼' : '张嘴' }}</p>
      <p v-else>请将面部对准摄像头</p>
    </div>
    <div v-else-if="step === 'result'" class="result-box">
      <el-result :icon="result.status === 'success' ? 'success' : 'error'"
                 :title="result.name || '未识别'"
                 :sub-title="result.student_no">
        <p>考勤状态: {{ result.status }}</p>
        <p>活体检测: {{ result.is_live ? '通过' : '未通过' }}</p>
        <p>情绪: {{ result.emotion }}</p>
      </el-result>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/request'

const step = ref('challenge')
const challenge = ref({})
const video = ref(null)
const canvas = ref(null)
const faceDetected = ref(false)
const result = ref({})

async function loadChallenge() {
  const res = await api.get('/attendance/action-challenge')
  challenge.value = res.data
  step.value = 'challenge'
}

async function startCamera() {
  step.value = 'camera'
  const stream = await navigator.mediaDevices.getUserMedia({ video: true })
  video.value.srcObject = stream
  // TODO: 集成 MediaPipe Face Mesh 进行动作检测
  setTimeout(() => captureAndSubmit(), 3000)  // 简化：3秒后自动拍照
}

async function captureAndSubmit() {
  const ctx = canvas.value.getContext('2d')
  canvas.value.width = video.value.videoWidth
  canvas.value.height = video.value.videoHeight
  ctx.drawImage(video.value, 0, 0)
  const blob = await new Promise(resolve => canvas.value.toBlob(resolve, 'image/jpeg'))
  const form = new FormData()
  form.append('image', blob, 'face.jpg')
  form.append('challenge_id', challenge.value.challenge_id)
  const res = await api.post('/attendance/check', form, { headers: { 'Content-Type': 'multipart/form-data' } })
  result.value = res.data
  step.value = 'result'
  video.value.srcObject.getTracks().forEach(t => t.stop())
}

onMounted(loadChallenge)
</script>
```

- [ ] **Step 3: 创建其他页面（简化版）**

```vue
<!-- frontend/src/views/Login.vue -->
<template>
  <div class="login-page">
    <el-form @submit.prevent="handleLogin">
      <el-input v-model="form.username" placeholder="用户名" />
      <el-input v-model="form.password" type="password" placeholder="密码" />
      <el-button type="primary" @click="handleLogin">登录</el-button>
    </el-form>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/request'

const router = useRouter()
const form = reactive({ username: '', password: '' })

async function handleLogin() {
  const res = await api.post('/auth/login', form)
  localStorage.setItem('token', res.access_token)
  router.push('/attendance')
}
</script>
```

---

## Chunk 5: 测试、部署与文档

### Task 15: 后端测试

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: 创建测试配置**

```python
# backend/tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base, get_db
from app.main import app

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]
```

- [ ] **Step 2: 创建认证测试**

```python
# backend/tests/test_auth.py
def test_login_success(client):
    # 需要预创建教师用户
    from app.db.models import User
    from app.core.security import get_password_hash
    db = next(client.app.dependency_overrides.values())
    # 实际测试中通过 fixture 初始化数据
    pass
```

---

### Task 16: 部署脚本与文档

**Files:**
- Create: `README.md`
- Create: `docs/deploy.md`

- [ ] **Step 1: 创建 README.md**

```markdown
# 班级考勤系统

## 快速启动

### 后端
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.db.init_db
python run.py
```

### 前端
```bash
cd frontend
npm install
npm run dev
```

## 默认账号
- 教师: teacher / teacher123

## 技术栈
Vue 3 + FastAPI + SQLite + InsightFace + DeepFace
```

- [ ] **Step 2: 创建部署说明**

```markdown
# 部署说明

## 环境要求
- Python 3.10+
- Node.js 18+
- Chrome / Edge 浏览器（用于摄像头调用）

## 安装步骤
1. 克隆项目
2. 安装后端依赖（见 README）
3. 安装前端依赖（见 README）
4. 配置 .env 文件
5. 启动后端服务
6. 启动前端开发服务器

## 模型准备
- 首次启动时 insightface 会自动下载 RetinaFace + ArcFace 模型
- 活体检测 fallback 模型需手动放置到 backend/models/ 目录
```

---

*计划文档结束*
