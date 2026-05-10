from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "backend" / "models" / "hsemotion" / "enet_b0_8_best_vgaf.onnx"
HSEMOTION_URL = "https://github.com/HSE-asavchenko/face-emotion-recognition/raw/main/models/affectnet_emotions/onnx/enet_b0_8_best_vgaf.onnx"
HSEMOTION_SHA256 = "fa07e841fd06c7a67ee651ea4e6e4a3a2bb5695f47b37a7da50492526f59c898"


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
    if actual_sha256 != HSEMOTION_SHA256:
        temp_path.unlink(missing_ok=True)
        raise SystemExit(
            "HSEmotion 模型 SHA256 校验失败："
            f"expected={HSEMOTION_SHA256}, actual={actual_sha256}"
        )
    temp_path.replace(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="下载 HSEmotion ONNX 表情识别模型")
    parser.add_argument("--output", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--force", action="store_true", help="即使模型已存在也重新下载")
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists() and not args.force:
        actual_sha256 = sha256_file(output)
        if actual_sha256 == HSEMOTION_SHA256:
            print(f"[SKIP] HSEmotion 模型已存在: {output}")
            return
        print("[WARN] 现有模型校验失败，重新下载。")

    print(f"[INFO] 下载 HSEmotion ONNX 模型到: {output}")
    download(HSEMOTION_URL, output)
    print("[OK] HSEmotion 情绪识别模型已准备就绪。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[ABORT] 用户取消下载")
        sys.exit(130)
