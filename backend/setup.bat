@echo off
chcp 65001 > nul
echo ============================================
echo  班级考勤系统 - 后端环境初始化脚本
echo ============================================
echo.

if not exist .env (
    echo [1/5] 复制环境变量模板...
    copy .env.example .env
    echo      ✓ .env 已创建，请根据实际需要修改配置
) else (
    echo [1/5] .env 已存在，跳过
)

echo [2/5] 创建虚拟环境...
python -m venv venv
if errorlevel 1 (
    echo      ✗ 创建虚拟环境失败，请确保已安装 Python 3.10+
    pause
    exit /b 1
)
echo      ✓ 虚拟环境创建成功

echo [3/5] 激活虚拟环境并安装依赖...
call venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo      ✗ 依赖安装失败
    pause
    exit /b 1
)
echo      ✓ 依赖安装完成

echo [4/5] 创建必要目录...
mkdir uploads 2> nul
mkdir models 2> nul
echo      ✓ 目录创建完成

echo [5/5] 初始化数据库...
python -m app.db.init_db
if errorlevel 1 (
    echo      ✗ 数据库初始化失败
    pause
    exit /b 1
)
echo      ✓ 数据库初始化完成
echo.
echo ============================================
echo  初始化完成！
echo  启动命令: python run.py
echo  Swagger文档: http://localhost:8000/docs
echo  默认教师账号: teacher / teacher123
echo ============================================
pause
