@echo off
chcp 65001 > nul
echo ============================================
echo  班级考勤系统 - 测试运行脚本
echo ============================================
echo.

call venv\Scripts\activate.bat

echo [1/3] 运行后端单元测试...
pytest tests/ -v --tb=short
if errorlevel 1 (
    echo      ✗ 部分测试未通过
) else (
    echo      ✓ 所有测试通过
)

echo [2/3] 生成测试覆盖率报告...
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

echo [3/3] 覆盖率报告已生成: htmlcov/index.html
echo.
pause
