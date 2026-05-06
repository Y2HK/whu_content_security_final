# 部署说明

## 1. 运行环境

- Python 3.10+
- Node.js 18+
- Windows 10/11 或其他支持 Python、Node.js 的系统

## 2. 后端启动

在 `backend` 目录下执行：

```bash
copy .env.example .env
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

启动后可访问：

- Swagger 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

默认教师账号：

- 用户名：`teacher`
- 密码：`teacher123`

密码哈希方案使用 `pbkdf2_sha256`，避免部分 Windows 环境下 `bcrypt` 兼容性问题。

## 3. 前端启动

在 `frontend` 目录下执行：

```bash
npm install
npm run dev
```

默认开发地址：

- `http://localhost:5173`

接口地址配置在：

- `frontend/.env.local`

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## 4. 演示建议流程

1. 启动后端服务
2. 启动前端服务
3. 使用默认教师账号登录
4. 在“学生管理”中手动新增学生或导入 `docs/sample-students.csv`
5. 上传学生照片建立基础人脸数据
6. 在“基础考勤”中使用摄像头拍照或上传图片进行考勤
7. 在“合照识别”页面上传图片并查看活动名单
8. 在“统计分析”页面查看情绪与活动统计图

## 5. 当前版本说明

当前版本已完成课程设计基础版的主要业务流程，但以下能力仍为预留或占位：

- 真实人脸识别模型
- 真实活体检测模型
- 细粒度权限控制
- 抗照片/视频攻击能力

这些能力不会影响当前版本的基础演示和文档提交。
