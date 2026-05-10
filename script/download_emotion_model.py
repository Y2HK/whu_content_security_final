from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "backend" / "models" / "emotion-ferplus-8.onnx"
FERPLUS_URL = "https://huggingface.co/onnxmodelzoo/emotion-ferplus-8/resolve/main/emotion-ferplus-8.onnx"
FERPLUS_SHA256 = "a2a2ba6a335a3b29c21acb6272f962bd3d47f84952aaffa03b60986e04efa61c"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".download")

    def report(block_count: int, block_size: int, total_size: int) -> None:
        if total_size <= 0:
            return
        downloaded = min(block_count * block_size, total_size)
        percent = downloaded * 100 / total_size
        print(f"\r[DOWNLOAD] {percent:5.1f}% ({downloaded / 1024 / 1024:.1f} MB)", end="")

    urllib.request.urlretrieve(url, temp_path, reporthook=report)
    print()
    actual_sha256 = sha256_file(temp_path)
    if actual_sha256 != FERPLUS_SHA256:
        temp_path.unlink(missing_ok=True)
        raise SystemExit(
            "FER+ 模型 SHA256 校验失败："
            f"expected={FERPLUS_SHA256}, actual={actual_sha256}"
        )
    temp_path.replace(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="下载 FER+ ONNX 表情识别模型")
    parser.add_argument("--output", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--force", action="store_true", help="即使模型已存在也重新下载")
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists() and not args.force:
        actual_sha256 = sha256_file(output)
        if actual_sha256 == FERPLUS_SHA256:
            print(f"[SKIP] FER+ 模型已存在: {output}")
            return
        print("[WARN] 现有模型校验失败，重新下载。")

    print(f"[INFO] 下载 FER+ ONNX 模型到: {output}")
    download(FERPLUS_URL, output)
    print("[OK] FER+ 情绪识别模型已准备就绪。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[ABORT] 用户取消下载")
        sys.exit(130)
