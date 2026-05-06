# schemas 模块说明

## 职责
Pydantic 数据模型层，定义请求/响应的数据结构和校验规则。

## 文件说明

| 文件 | 内容 |
|------|------|
| `auth.py` | UserLogin(登录请求), TokenResponse(Token响应), UserInfo(用户信息) |
| `student.py` | StudentCreate(创建学生), StudentResponse(学生列表项) |
| `attendance.py` | AttendanceCheckResponse(考勤结果), AttendanceRecord(考勤记录项) |
| `group.py` | ActivityCreate(创建活动), ActivityResponse(活动列表), GroupUploadResponse(合照识别结果) |
| `emotion.py` | EmotionStatistics(情绪统计), EmotionTimeline(情绪时间线项) |

## 设计原则

- **请求模型**（Create/Login）：仅包含客户端传入的字段
- **响应模型**（Response）：包含完整数据，用于 API 文档自动生成
- **数据库模型**（models.py）与 **Schema 模型**分离，避免耦合

## 使用方式

```python
from app.schemas.student import StudentCreate, StudentResponse
from fastapi import APIRouter

router = APIRouter()

@router.post("/", response_model=StudentResponse)
def create(data: StudentCreate):
    # data 自动经过 Pydantic 校验
    pass
```
