@echo off
chcp 65001 > nul
setlocal

echo ============================================
echo  班级考勤系统 - 一键快速启动脚本
echo ============================================
echo.

echo [1/3] 检查后端虚拟环境...
if not exist "backend\venv\Scripts\python.exe" (
    echo      ✗ 未检测到后端虚拟环境，请先运行 install-deps.bat
    pause
    exit /b 1
)
echo      ✓ 后端虚拟环境存在

echo [2/3] 检查前端依赖...
if not exist "frontend\node_modules" (
    echo      ✗ 未检测到前端依赖，请先运行 install-deps.bat
    pause
    exit /b 1
)
echo      ✓ 前端依赖存在

echo [3/3] 启动前后端服务...
start "Backend Server" cmd /k "cd /d %~dp0backend && call venv\Scripts\activate.bat && python run.py"
start "Frontend Server" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ============================================
echo  服务已启动！
echo  Swagger: http://localhost:8000/docs
echo  前端页面: http://localhost:5173
echo  默认账号: teacher / teacher123
echo ============================================
pause
