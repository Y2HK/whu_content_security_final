@echo off
chcp 65001 > nul
setlocal

echo ============================================
echo  班级考勤系统 - 一键依赖安装脚本
echo ============================================
echo.

echo [1/4] 检查 backend 目录...
if not exist "backend" (
    echo      ✗ 未找到 backend 目录
    pause
    exit /b 1
)
echo      ✓ backend 目录存在

echo [2/4] 初始化后端依赖...
call "backend\setup.bat"
if errorlevel 1 (
    echo      ✗ 后端依赖初始化失败
    pause
    exit /b 1
)
echo      ✓ 后端依赖初始化完成

echo [3/4] 检查 frontend 目录...
if not exist "frontend" (
    echo      ✗ 未找到 frontend 目录
    pause
    exit /b 1
)
echo      ✓ frontend 目录存在

echo [4/4] 初始化前端依赖...
pushd "frontend"
call setup.bat
if errorlevel 1 (
    popd
    echo      ✗ 前端依赖初始化失败
    pause
    exit /b 1
)
popd
echo      ✓ 前端依赖初始化完成

echo.
echo ============================================
echo  所有依赖安装完成！
echo  下一步可运行 quick-start.bat 快速启动项目
echo ============================================
pause
