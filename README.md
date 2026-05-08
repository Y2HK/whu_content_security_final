# 班级考勤系统

## 项目简介

这是一个面向《内容安全实验》课程设计的班级考勤系统基础版，采用 B/S 架构，支持：

- 学生管理
- 教师/学生注册与权限隔离
- 基础考勤
- 合照识别
- 情绪统计
- DeepFace 面部情绪分析模型
- Excel 导出

当前版本已完成除以下能力外的大部分工作：

- 真实人脸识别模型接入
- 活体检测
- 抗攻击能力

情绪分析已从原占位逻辑升级为 DeepFace 表情识别模型；后端会在考勤图片和合照上传时同步分析 `happy / neutral / surprise / sad / angry / fear / disgust` 7 类表情。若本地尚未安装模型依赖或模型加载失败，系统会自动降级为可演示结果，保证基础流程可运行。

后端默认密码哈希方案使用 `pbkdf2_sha256`，以提高 Windows 环境下的安装兼容性。

## 项目结构

- `backend/`：FastAPI 后端
- `frontend/`：Vue 3 前端
- `docs/`：部署文档与示例数据
- `progress-status.md`：阶段进度说明

## 如何运行

### 推荐方式：使用 Python 脚本

在项目根目录执行：

### 第一步：安装项目依赖

```bash
python install_deps.py
```

这个脚本会自动完成：

- 后端 `.env` 初始化
- 后端虚拟环境创建
- 后端 Python 依赖安装
- 后端数据库初始化
- 前端 Node.js 依赖安装
- 前端 `.env.local` 初始化

如果执行时提示未找到 `npm`，请先确认：

- 已安装 Node.js 18+
- `npm` 已加入系统 PATH
- 安装或修改 PATH 后已重新打开终端

### 第二步：快速启动项目

```bash
python quick_start.py
```

这个脚本会自动：

- 启动后端服务
- 启动前端开发服务
- 在 Windows 中弹出两个独立终端窗口

启动后访问：

- Swagger：`http://localhost:8000/docs`
- 前端页面：`http://localhost:5173`

## 备选方式：继续使用 bat 脚本

如果你愿意，也可以继续使用：

```powershell
.\install-deps.bat
.\quick-start.bat
```

## 手动运行方式

如果你不想用一键脚本，也可以手动分开运行。

### 后端

```bash
cd backend
setup.bat
python run.py
```

### 前端

新开一个终端窗口：

```bash
cd frontend
setup.bat
npm run dev
```

## 默认账号

- 用户名：`teacher`
- 密码：`teacher123`

## 示例数据

- 前端导入模板：`frontend/sample-students.csv`
- 部署说明：`docs/deploy.md`
- 阶段进度：`progress-status.md`

## 适用说明

当前版本适合：

- 课程设计基础功能演示
- 前后端联调
- 课程报告撰写
- 后续继续扩展真实识别与安全能力
