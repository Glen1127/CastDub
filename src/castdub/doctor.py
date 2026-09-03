from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _ffmpeg_filters() -> str:
    executable = shutil.which("ffmpeg")
    if executable is None:
        return ""
    result = subprocess.run(
        [executable, "-hide_banner", "-filters"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


def inspect_environment(model_path: Path | None = None) -> dict[str, Any]:
    filters = _ffmpeg_filters()
    python_ok = sys.version_info >= (3, 12)
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    core_ok = python_ok and ffmpeg_path is not None and ffprobe_path is not None

    configured_model = model_path
    if configured_model is None and os.environ.get("CASTDUB_MODEL_ROOT"):
        configured_model = Path(os.environ["CASTDUB_MODEL_ROOT"])

    return {
        "schema_version": 1,
        "core_ready": core_ok,
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "core": {
            "python_3_12_or_newer": python_ok,
            "ffmpeg": ffmpeg_path,
            "ffprobe": ffprobe_path,
            "rubberband_filter": "rubberband" in filters,
            "subtitle_filter": "subtitles" in filters,
        },
        "optional_workers": {
            "mlx": _module_available("mlx"),
            "mlx_audio": _module_available("mlx_audio"),
            "torch": _module_available("torch"),
            "demucs": _module_available("demucs"),
            "whisperx": _module_available("whisperx"),
            "pyannote_audio": _module_available("pyannote.audio"),
        },
        "model": {
            "configured_path": str(configured_model) if configured_model else None,
            "available": bool(configured_model and configured_model.exists()),
        },
        "downloads_performed": False,
    }
