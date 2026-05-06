# db 模块说明

## 职责
数据库层，负责 SQLite 连接、ORM 模型定义和数据库初始化。

## 文件说明

| 文件 | 职责 |
|------|------|
| `database.py` | SQLAlchemy Engine + SessionLocal 创建，提供 `get_db()` 生成器 |
| `models.py` | 7张数据表的 ORM 模型定义（User, Student, FaceFeature, Attendance, Activity, ActivityParticipant） |
| `init_db.py` | 建表脚本 + 默认教师账号初始化 |

## 数据表清单

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `user` | 系统用户（教师/学生账号） | username, password_hash, role, student_id |
| `student` | 学生基本信息 | student_no, name, class_name |
| `face_feature` | 人脸特征向量（AES加密存储） | student_id, feature_vector |
| `attendance` | 考勤记录 | student_id, check_time, is_live, emotion |
| `activity` | 合照活动记录 | activity_name, image_path, event_date |
| `activity_participant` | 活动参与关系 | activity_id, student_id, confidence, emotion |

## 使用方式

```python
from app.db.database import get_db
from app.db.models import Student, Attendance
```
