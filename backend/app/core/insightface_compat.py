from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

_ORIGINAL_ENSURE_AVAILABLE = None
_PATCHED = False


def get_pack_dir(root: str | Path, pack_name: str) -> Path:
    return Path(root).expanduser().resolve() / pack_name


def get_legacy_pack_dir(root: str | Path, pack_name: str) -> Path:
    return Path(root).expanduser().resolve() / "models" / pack_name


def has_onnx_files(path: Path) -> bool:
    return path.exists() and any(path.glob("*.onnx"))


def migrate_legacy_pack_dir(root: str | Path, pack_name: str) -> Path:
    pack_dir = get_pack_dir(root, pack_name)
    legacy_dir = get_legacy_pack_dir(root, pack_name)

    if has_onnx_files(pack_dir) or not has_onnx_files(legacy_dir):
        return pack_dir

    pack_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy_dir), str(pack_dir))

    legacy_root = legacy_dir.parent
    try:
        if legacy_root.exists() and not any(legacy_root.iterdir()):
            legacy_root.rmdir()
    except OSError:
        pass

    return pack_dir


def preload_onnxruntime_dlls() -> None:
    """On Windows, preload CUDA/cuDNN DLLs from installed NVIDIA packages."""
    try:
        import onnxruntime as ort
    except ImportError:
        return

    preload_dlls = getattr(ort, "preload_dlls", None)
    if preload_dlls is None:
        return

    try:
        preload_dlls(directory="")
    except TypeError:
        preload_dlls()
    except Exception:
        pass


def patch_face_analysis_model_root() -> None:
    global _ORIGINAL_ENSURE_AVAILABLE, _PATCHED
    if _PATCHED:
        return

    from insightface.app import face_analysis as face_analysis_module

    if _ORIGINAL_ENSURE_AVAILABLE is None:
        _ORIGINAL_ENSURE_AVAILABLE = face_analysis_module.ensure_available

    def ensure_available_local(sub_dir: str, name: str, root: str = "~/.insightface") -> str:
        if sub_dir != "models":
            return _ORIGINAL_ENSURE_AVAILABLE(sub_dir, name, root=root)

        root_path = Path(root).expanduser().resolve()
        pack_dir = migrate_legacy_pack_dir(root_path, name)
        if has_onnx_files(pack_dir):
            return str(pack_dir)

        from insightface.utils.storage import BASE_REPO_URL, download_file

        zip_path = root_path / f"{name}.zip"
        root_path.mkdir(parents=True, exist_ok=True)
        print("download_path:", pack_dir)
        download_file(f"{BASE_REPO_URL}/{name}.zip", path=str(zip_path), overwrite=True)
        pack_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(pack_dir)
        return str(pack_dir)

    face_analysis_module.ensure_available = ensure_available_local
    _PATCHED = True
