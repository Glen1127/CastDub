#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [[ -n "${PYTHON:-}" ]]; then
  python_bin="$PYTHON"
elif command -v python3.12 >/dev/null; then
  python_bin="python3.12"
else
  python_bin="python3"
fi
"$python_bin" -c 'import sys; assert (3, 12) <= sys.version_info[:2] < (3, 14), "Python 3.12 or 3.13 is required"'
command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null

PYTHONPATH=src "$python_bin" -m unittest discover -s tests -q

if command -v uv >/dev/null; then
  uv build --offline
else
  "$python_bin" -m build
fi

release_stem="$($python_bin - <<'PY'
import tomllib
from pathlib import Path

project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
stem = project["name"].replace("-", "_")
version = project["version"]
print(f"{stem}-{version}")
PY
)"
wheel="dist/${release_stem}-py3-none-any.whl"
sdist="dist/${release_stem}.tar.gz"
[[ -f "$wheel" && -f "$sdist" ]]

release_tmp="$(mktemp -d)"
"$python_bin" -m venv "$release_tmp/venv"
"$release_tmp/venv/bin/python" -m pip install --no-index --no-deps "$wheel"
"$release_tmp/venv/bin/castdub" --help >/dev/null
"$release_tmp/venv/bin/castdub" doctor >/dev/null
"$release_tmp/venv/bin/castdub" demo --output-dir "$release_tmp/demo" >/dev/null
"$python_bin" scripts/audit-release.py "$wheel" "$sdist"

echo "release check passed"
