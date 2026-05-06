# routers 模块说明

## 职责
API 路由层，按业务模块划分，处理 HTTP 请求/响应、参数校验和权限控制。

## 文件说明

| 文件 | 路由前缀 | 职责 |
|------|----------|------|
| `auth.py` | `/auth` | 登录/登出/获取用户信息 |
| `students.py` | `/students` | 学生增删改查、人脸特征采集、批量导入 |
| `attendance.py` | `/attendance` | 动作挑战获取、考勤打卡、考勤记录查询/导出 |
| `group.py` | `/group` | 合照上传识别、活动列表/详情/统计 |
| `emotion.py` | `/emotion` | 情绪分布统计、情绪时间线查询 |

## 权限控制

| 权限装饰器 | 适用角色 | 说明 |
|-----------|----------|------|
| `get_current_user` | 登录用户 | 验证JWT Token有效性 |
| `require_teacher` | 仅教师 | 拒绝学生访问，返回403 |

## 使用方式

```python
from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user, require_teacher

router = APIRouter()

@router.get("/")
def list_items(user = Depends(require_teacher)):
    # 仅教师可访问
    pass
```
