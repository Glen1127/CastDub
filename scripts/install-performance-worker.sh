#!/bin/sh
set -eu

if [ "${1:-}" != "--accept-model-license" ]; then
  echo "Review the SenseVoiceSmall model terms, then rerun with --accept-model-license." >&2
  exit 2
fi

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PERFORMANCE_PYTHON="$PROJECT_ROOT/.venv-performance/bin/python"
MODEL_DIR="$PROJECT_ROOT/models/SenseVoiceSmall"
INSTALL_LOG="$PROJECT_ROOT/logs/install-sensevoice.log"
MODEL_RECEIPT="$PROJECT_ROOT/models/SenseVoiceSmall.receipt.json"

mkdir -p "$PROJECT_ROOT/logs" "$PROJECT_ROOT/models"

uv venv "$PROJECT_ROOT/.venv-performance" --python 3.12 --allow-existing >>"$INSTALL_LOG" 2>&1
uv pip install --python "$PERFORMANCE_PYTHON" \
  'numpy==1.26.4' \
  'torch==2.14.0' \
  'funasr==1.4.14' \
  'huggingface_hub==1.30.0' >>"$INSTALL_LOG" 2>&1

MODEL_REVISION=$(
  curl -fsSL https://huggingface.co/api/models/FunAudioLLM/SenseVoiceSmall |
    "$PERFORMANCE_PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["sha"])'
)

"$PROJECT_ROOT/.venv-performance/bin/hf" download \
  FunAudioLLM/SenseVoiceSmall \
  --revision "$MODEL_REVISION" \
  --local-dir "$MODEL_DIR" >>"$INSTALL_LOG" 2>&1

"$PERFORMANCE_PYTHON" - "$MODEL_DIR" "$MODEL_REVISION" "$MODEL_RECEIPT" <<'PY'
import json
import sys
from pathlib import Path

model_dir = Path(sys.argv[1]).resolve()
revision = sys.argv[2]
receipt = Path(sys.argv[3])
required = (model_dir / "config.yaml", model_dir / "model.pt")
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise SystemExit(f"Missing model files: {missing}")

import funasr
import torch

receipt.write_text(
    json.dumps(
        {
            "model": "FunAudioLLM/SenseVoiceSmall",
            "revision": revision,
            "model_path": str(model_dir),
            "torch": torch.__version__,
            "funasr": getattr(funasr, "__version__", "unknown"),
            "model_bytes": (model_dir / "model.pt").stat().st_size,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY

echo "Performance worker ready"
echo "Python: $PERFORMANCE_PYTHON"
echo "Model: $MODEL_DIR"
echo "Receipt: $MODEL_RECEIPT"
echo "Log: $INSTALL_LOG"
