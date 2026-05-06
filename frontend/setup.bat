@echo off
chcp 65001 > nul
echo ============================================
echo  班级考勤系统 - 前端环境初始化脚本
echo ============================================
echo.

echo [1/2] 安装 Node.js 依赖...
npm install
if errorlevel 1 (
    echo      ✗ 依赖安装失败，请确保已安装 Node.js 18+
    pause
    exit /b 1
)
echo      ✓ 依赖安装完成

echo [2/2] 检查配置文件...
if not exist .env.local (
    echo VITE_API_BASE_URL=http://localhost:8000/api/v1 > .env.local
    echo      ✓ .env.local 已创建
) else (
    echo      ✓ .env.local 已存在
)

echo.
echo ============================================
echo  初始化完成！
echo  开发启动: npm run dev
echo  生产构建: npm run build
echo ============================================
pause
