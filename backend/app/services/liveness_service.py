def get_liveness_placeholder() -> dict:
    return {
        "implemented": False,
        "result": None,
        "message": "当前阶段未启用活体检测，仅保留接口用于后续扩展。",
    }
