from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
RANDOM_ATTENDANCE_SCRIPT = ROOT / "script" / "random_attendance_import.py"


def run_command(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=str(cwd), check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


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


def ensure_backend_python() -> Path:
    backend_python = BACKEND / "venv" / "Scripts" / "python.exe"
    if not backend_python.exists():
        raise SystemExit("未检测到后端虚拟环境，请先运行 python install_deps.py")

    result = subprocess.run([str(backend_python), "--version"], cwd=str(BACKEND), check=False)
    if result.returncode == 0:
        return backend_python

    print("检测到后端虚拟环境解释器失效，正在使用当前 Python 修复 venv ...")
    run_command([sys.executable, "-m", "venv", "venv"], BACKEND)

    result = subprocess.run([str(backend_python), "--version"], cwd=str(BACKEND), check=False)
    if result.returncode != 0:
        raise SystemExit("后端虚拟环境修复失败，请运行 python install_deps.py 重新安装依赖")
    return backend_python


def import_sample_attendance(backend_python: Path) -> None:
    if not RANDOM_ATTENDANCE_SCRIPT.exists():
        print("[WARN] sample attendance script not found, skipped.")
        return

    print("[INFO] importing sample attendance records ...")
    result = subprocess.run(
        [
            str(backend_python),
            str(RANDOM_ATTENDANCE_SCRIPT),
            "--min-records",
            "1",
            "--max-records",
            "2",
            "--preview-limit",
            "5",
        ],
        cwd=str(ROOT),
        check=False,
    )
    if result.returncode != 0:
        print("[WARN] sample attendance import failed, servers will still start.")


def main() -> None:
    backend_python = ensure_backend_python()
    frontend_node_modules = FRONTEND / "node_modules"

    if not frontend_node_modules.exists():
        raise SystemExit("未检测到前端依赖，请先运行 python install_deps.py")

    npm_command = resolve_npm_command()

    print("=" * 44)
    print("班级考勤系统 - 一键快速启动脚本")
    print("=" * 44)

    import_sample_attendance(backend_python)

    subprocess.Popen(
        [str(backend_python), "run.py"],
        cwd=str(BACKEND),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    subprocess.Popen(
        [*npm_command, "run", "dev"],
        cwd=str(FRONTEND),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )

    print("已启动前后端服务。")
    print("Swagger: http://localhost:8000/docs")
    print("前端页面: http://localhost:5173")
    print("默认账号: teacher / teacher123")


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("当前脚本主要面向 Windows 环境。")
    main()
