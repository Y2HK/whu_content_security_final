# tests 模块说明

## 职责
后端单元测试和集成测试，使用 pytest + httpx TestClient。

## 文件说明

| 文件 | 职责 |
|------|------|
| `conftest.py` | 测试 fixtures：内存 SQLite 数据库、TestClient、默认测试用户 |
| `test_auth.py` | 登录/登出/Token验证测试 |
| `test_students.py` | 学生CRUD/人脸上传/批量导入测试 |
| `test_attendance.py` | 考勤打卡/记录查询/权限过滤测试 |
| `test_group.py` | 合照上传/活动查询/名单生成测试 |

## 运行测试

```bash
# Windows
run_tests.bat

# 手动运行
pytest tests/ -v
pytest tests/ --cov=app --cov-report=html
```

## 测试数据库

使用独立内存 SQLite 数据库（`test.db`），每次测试函数结束后自动清空。
