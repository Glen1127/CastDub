#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE="$PROJECT_ROOT/skills/drama-localisation-production"
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
SKILLS_ROOT="$CODEX_ROOT/skills"
DESTINATION="$SKILLS_ROOT/drama-localisation-production"

if [[ -e "$DESTINATION" ]]; then
  echo "CastDub Skill is already installed: $DESTINATION" >&2
  echo "Move the existing directory aside before reinstalling." >&2
  exit 1
fi

mkdir -p "$SKILLS_ROOT"
cp -R "$SOURCE" "$DESTINATION"

echo "CastDub Skill installed: $DESTINATION"
echo "Start a new Codex task and describe the episode and target language."
