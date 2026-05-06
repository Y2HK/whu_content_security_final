from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def run_command(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=str(cwd), check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def ensure_exists(path: Path, name: str) -> None:
    if not path.exists():
        raise SystemExit(f"未找到{name}: {path}")


def resolve_npm_command() -> list[str]:
    npm_cmd = shutil.which("npm.cmd")
    if npm_cmd:
        return [npm_cmd]

    npm_exe = shutil.which("npm")
    if npm_exe:
        return [npm_exe]

    raise SystemExit(
        "未找到 npm。请先安装 Node.js 18+，并确保 npm 已加入系统 PATH，然后重新打开终端后再运行脚本。"
    )


def main() -> None:
    print("=" * 44)
    print("班级考勤系统 - 一键依赖安装脚本")
    print("=" * 44)

    ensure_exists(BACKEND, "backend 目录")
    ensure_exists(FRONTEND, "frontend 目录")

    python_executable = sys.executable or "python"
    npm_command = resolve_npm_command()

    print("[1/6] 检查并创建后端 .env ...")
    env_example = BACKEND / ".env.example"
    env_file = BACKEND / ".env"
    if not env_file.exists():
        shutil.copyfile(env_example, env_file)
        print("      ✓ 已创建 backend/.env")
    else:
        print("      ✓ backend/.env 已存在")

    print("[2/6] 创建后端虚拟环境 ...")
    run_command([python_executable, "-m", "venv", "venv"], BACKEND)
    print("      ✓ 后端虚拟环境创建完成")

    print("[3/6] 安装后端 Python 依赖 ...")
    venv_python = BACKEND / "venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        raise SystemExit("未找到后端虚拟环境 python.exe")
    run_command([str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"], BACKEND)
    print("      ✓ 后端依赖安装完成")

    print("[4/6] 初始化后端数据库 ...")
    (BACKEND / "uploads").mkdir(exist_ok=True)
    (BACKEND / "models").mkdir(exist_ok=True)
    run_command([str(venv_python), "-m", "app.db.init_db"], BACKEND)
    print("      ✓ 后端数据库初始化完成")

    print("[5/6] 安装前端 Node.js 依赖 ...")
    run_command([*npm_command, "install"], FRONTEND)
    print("      ✓ 前端依赖安装完成")

    print("[6/6] 检查前端 .env.local ...")
    frontend_env = FRONTEND / ".env.local"
    if not frontend_env.exists():
        frontend_env.write_text("VITE_API_BASE_URL=http://localhost:8000/api/v1\n", encoding="utf-8")
        print("      ✓ 已创建 frontend/.env.local")
    else:
        print("      ✓ frontend/.env.local 已存在")

    print("\n安装完成。下一步运行：python quick_start.py")


if __name__ == "__main__":
    main()
