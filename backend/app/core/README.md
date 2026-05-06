# core 模块说明

## 职责
系统核心基础设施，包含配置管理、安全加密和依赖注入。

## 文件说明

| 文件 | 职责 |
|------|------|
| `config.py` | 读取 `.env` 环境变量，提供全局配置对象 `settings` |
| `security.py` | JWT 生成/验证、bcrypt 密码哈希、AES-256-GCM 特征向量加解密 |
| `dependencies.py` | FastAPI 依赖注入：`get_db`(数据库会话)、`get_current_user`(当前用户)、`require_teacher`(教师权限校验) |

## 关键配置项

- `FACE_FEATURE_KEY`: 人脸特征加密密钥（需32字节）
- `FACE_SIMILARITY_THRESHOLD`: 单人识别阈值（默认0.6）
- `GROUP_FACE_SIMILARITY_THRESHOLD`: 合照识别阈值（默认0.55）

## 使用方式

```python
from app.core.config import settings
from app.core.security import create_access_token, encrypt_feature
from app.core.dependencies import get_current_user, require_teacher
```
