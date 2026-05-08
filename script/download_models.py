"""
InsightFace 模型预下载脚本

下载 buffalo_l 模型包到 model/ 目录：
  - det_10g.onnx       SCRFD-10GF 人脸检测
  - 2d106det.onnx      人脸关键点 (106点)
  - w600k_r50.onnx     ArcFace 512维 特征提取
  - 1k3d68.onnx        3D 关键点 (选用)
  - genderage.onnx     性别/年龄 (选用)

用法:
  python script/download_models.py
  python script/download_models.py --root ./model
  python script/download_models.py --cpu
"""

import argparse
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.insightface_compat import (
    get_pack_dir,
    has_onnx_files,
    migrate_legacy_pack_dir,
    patch_face_analysis_model_root,
    preload_onnxruntime_dlls,
)

MODEL_PACKS = ["buffalo_l"]


def download_models(root: str, use_cpu: bool) -> None:
    try:
        from insightface.app import FaceAnalysis
    except ImportError:
        print("[ERROR] insightface 未安装，请先执行: pip install insightface onnxruntime opencv-python")
        sys.exit(1)

    patch_face_analysis_model_root()
    root_path = Path(root).resolve()
    print(f"[INFO] 模型目录: {root_path}")

    if use_cpu:
        providers = ["CPUExecutionProvider"]
        ctx_id = -1
        print("[INFO] 推理后端: CPU")
    else:
        try:
            import onnxruntime
            preload_onnxruntime_dlls()
            available = onnxruntime.get_available_providers()
            if "CUDAExecutionProvider" in available:
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
                ctx_id = 0
                print("[INFO] 推理后端: CUDA (GPU)")
            elif "DmlExecutionProvider" in available:
                providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
                ctx_id = 0
                print("[INFO] 推理后端: DirectML (GPU)")
            else:
                providers = ["CPUExecutionProvider"]
                ctx_id = -1
                print("[INFO] 推理后端: CPU (GPU 不可用)")
        except ImportError:
            providers = ["CPUExecutionProvider"]
            ctx_id = -1
            print("[INFO] 推理后端: CPU")

    for pack_name in MODEL_PACKS:
        pack_dir = migrate_legacy_pack_dir(root_path, pack_name)
        if has_onnx_files(pack_dir):
            print(f"[SKIP] {pack_name} 已存在: {pack_dir}")
            continue

        print(f"[DOWNLOAD] 正在下载 {pack_name} 模型包...")
        started = time.time()

        app = FaceAnalysis(name=pack_name, root=str(root_path), providers=providers)
        app.prepare(ctx_id=ctx_id, det_size=(640, 640))

        elapsed = time.time() - started
        pack_dir = get_pack_dir(root_path, pack_name)
        files = sorted(f.name for f in pack_dir.glob("*.onnx"))
        total_mb = sum(f.stat().st_size for f in pack_dir.glob("*")) / (1024 * 1024)

        print(f"[OK] {pack_name} 下载完成 ({elapsed:.1f}s, {total_mb:.1f} MB)")
        print(f"[OK] 模型文件: {', '.join(files)}")

    print("\n[DONE] 所有模型准备就绪。")


def main() -> None:
    default_root = PROJECT_ROOT / "model"

    parser = argparse.ArgumentParser(description="预下载 InsightFace 人脸识别模型")
    parser.add_argument("--root", type=str, default=str(default_root),
                        help=f"模型存储目录 (默认: {default_root})")
    parser.add_argument("--cpu", action="store_true",
                        help="强制使用 CPU 推理（跳过 GPU 检测）")
    args = parser.parse_args()

    os.makedirs(args.root, exist_ok=True)
    download_models(root=args.root, use_cpu=args.cpu)


if __name__ == "__main__":
    main()
