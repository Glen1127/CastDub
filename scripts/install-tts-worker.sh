#!/bin/sh
set -eu

if [ "${1:-}" != "--accept-model-license" ]; then
  echo "Review the Qwen3-TTS model terms, then rerun with --accept-model-license." >&2
  exit 2
fi

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TTS_PYTHON="$PROJECT_ROOT/.venv-tts/bin/python"
MODEL_DIR="$PROJECT_ROOT/models/Qwen3-TTS-12Hz-1.7B-Base"
INSTALL_LOG="$PROJECT_ROOT/logs/install-qwen3-tts.log"
MODEL_RECEIPT="$PROJECT_ROOT/models/Qwen3-TTS-12Hz-1.7B-Base.receipt.json"
MODEL_ID="Qwen/Qwen3-TTS-12Hz-1.7B-Base"

mkdir -p "$PROJECT_ROOT/logs" "$PROJECT_ROOT/models"
uv venv "$PROJECT_ROOT/.venv-tts" --python 3.12 --allow-existing >>"$INSTALL_LOG" 2>&1
uv pip install --python "$TTS_PYTHON" \
  'mlx-audio==0.4.5' \
  'huggingface_hub==1.30.0' >>"$INSTALL_LOG" 2>&1

MODEL_REVISION=$(
  curl -fsSL "https://huggingface.co/api/models/$MODEL_ID" |
    "$TTS_PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["sha"])'
)

"$PROJECT_ROOT/.venv-tts/bin/hf" download \
  "$MODEL_ID" \
  --revision "$MODEL_REVISION" \
  --local-dir "$MODEL_DIR" >>"$INSTALL_LOG" 2>&1

"$TTS_PYTHON" - "$MODEL_DIR" "$MODEL_ID" "$MODEL_REVISION" "$MODEL_RECEIPT" <<'PY'
import json
import sys
from pathlib import Path

model_dir = Path(sys.argv[1]).resolve()
model_id = sys.argv[2]
revision = sys.argv[3]
receipt = Path(sys.argv[4])
required = (model_dir / "config.json", model_dir / "model.safetensors")
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise SystemExit(f"Missing model files: {missing}")

import mlx
import mlx_audio

model_bytes = sum(path.stat().st_size for path in model_dir.rglob("*") if path.is_file())
receipt.write_text(
    json.dumps(
        {
            "model": model_id,
            "revision": revision,
            "model_path": str(model_dir),
            "mlx_audio": "0.4.5",
            "model_bytes": model_bytes,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY

echo "TTS worker ready"
echo "Python: $TTS_PYTHON"
echo "Model: $MODEL_DIR"
echo "Receipt: $MODEL_RECEIPT"
echo "Log: $INSTALL_LOG"
