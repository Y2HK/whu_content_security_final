# services 模块说明

## 职责
算法引擎层，封装所有 AI/ML 模型的调用逻辑，对外提供统一接口。

## 文件说明

| 文件 | 职责 | 依赖库 |
|------|------|--------|
| `face_engine.py` | 人脸检测（RetinaFace）+ 人脸识别（ArcFace）+ 1:N比对 | insightface, numpy |
| `liveness_engine.py` | 活体检测：自研CNN / CDCN / Silent-Face 三级自动降级 | torch, torchvision |
| `emotion_engine.py` | 面部表情情绪分析（7分类） | deepface |
| `encryption.py` | AES-256-GCM 特征向量加解密（如需独立文件） | cryptography |

## 模型降级链

```
自研CNN (models/custom_live.pth)
    └── 不存在/加载失败 ──> CDCN (models/cdcn_live.pth)
                              └── 不存在 ──> Silent-Face-Anti-Spoofing
```

## 统一接口规范

所有引擎类均提供单例实例：

```python
from app.services.face_engine import face_engine
from app.services.liveness_engine import liveness_engine
from app.services.emotion_engine import emotion_engine

# 人脸检测
faces = face_engine.detect_faces(image)

# 活体检测
result = liveness_engine.predict(face_image)  # {"is_live": bool, "confidence": float}

# 情绪分析
emotion = emotion_engine.analyze(face_image)  # {"emotion": str, "confidence": float}
```
