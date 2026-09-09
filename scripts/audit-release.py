from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path


FORBIDDEN_PARTS = {"resource", "resources", "models", "work", "logs", "projects"}
FORBIDDEN_SUFFIXES = {
    ".ass", ".m4a", ".mkv", ".mov", ".mp3", ".mp4", ".onnx", ".pt",
    ".pth", ".safetensors", ".srt", ".vtt", ".wav",
}
FORBIDDEN_TEXT = (b"/" + b"Users" + b"/", b"glen" + b"x")


def members(path: Path) -> list[tuple[str, bytes]]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return [(name, archive.read(name)) for name in archive.namelist()]
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            return [
                (item.name, archive.extractfile(item).read())
                for item in archive.getmembers()
                if item.isfile()
            ]
    raise ValueError(f"Unsupported release archive: {path}")


def audit(path: Path) -> list[str]:
    failures: list[str] = []
    for name, content in members(path):
        relative = Path(name)
        parts = {part.lower() for part in relative.parts[1:]}
        empty_marker = relative.name == ".gitkeep" and not content.strip()
        if (
            (parts & FORBIDDEN_PARTS and not empty_marker)
            or relative.suffix.lower() in FORBIDDEN_SUFFIXES
        ):
            failures.append(f"private/generated path: {name}")
        if any(marker in content for marker in FORBIDDEN_TEXT):
            failures.append(f"personal absolute path in: {name}")
    return failures


def main(argv: list[str]) -> int:
    archives = [Path(value) for value in argv]
    failures = [failure for path in archives for failure in audit(path)]
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"release audit passed: {len(archives)} archive(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
