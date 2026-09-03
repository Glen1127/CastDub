from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RightsError(ValueError):
    """Raised when a job lacks the authority required for processing."""


@dataclass(frozen=True)
class VoiceGrant:
    character_id: str
    voice_cloning_approved: bool
    cross_language_approved: bool
    permitted_target_languages: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "VoiceGrant":
        return cls(
            character_id=str(value["character_id"]),
            voice_cloning_approved=bool(value.get("voice_cloning_approved", False)),
            cross_language_approved=bool(value.get("cross_language_approved", False)),
            permitted_target_languages=tuple(value.get("permitted_target_languages", [])),
        )


@dataclass(frozen=True)
class RightsManifest:
    source_title: str
    translation_approved: bool
    dubbing_approved: bool
    overseas_distribution_approved: bool
    voice_grants: tuple[VoiceGrant, ...]

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "RightsManifest":
        return cls(
            source_title=str(value["source_title"]),
            translation_approved=bool(value.get("translation_approved", False)),
            dubbing_approved=bool(value.get("dubbing_approved", False)),
            overseas_distribution_approved=bool(
                value.get("overseas_distribution_approved", False)
            ),
            voice_grants=tuple(
                VoiceGrant.from_mapping(grant)
                for grant in value.get("voice_grants", [])
            ),
        )

    def assert_authorized(self, target_language: str) -> None:
        missing = [
            label
            for label, approved in (
                ("translation", self.translation_approved),
                ("dubbing", self.dubbing_approved),
                ("overseas_distribution", self.overseas_distribution_approved),
            )
            if not approved
        ]
        if missing:
            raise RightsError("Missing project rights: " + ", ".join(missing))
        if not self.voice_grants:
            raise RightsError("At least one explicit character voice grant is required")

        for grant in self.voice_grants:
            if not grant.voice_cloning_approved or not grant.cross_language_approved:
                raise RightsError(
                    f"Character {grant.character_id!r} lacks voice-cloning or cross-language approval"
                )
            if target_language not in grant.permitted_target_languages:
                raise RightsError(
                    f"Character {grant.character_id!r} is not approved for {target_language}"
                )


JOB_DIRECTORIES = (
    "source",
    "separated",
    "transcript",
    "timeline",
    "voices",
    "translations",
    "synthesis",
    "mix",
    "subtitles",
    "output",
    "qc",
    "logs",
)


def load_rights(path: Path) -> RightsManifest:
    with path.open("r", encoding="utf-8") as handle:
        return RightsManifest.from_mapping(json.load(handle))


def create_project(
    workspace: Path,
    slug: str,
    target_language: str,
    rights: RightsManifest,
) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", slug):
        raise ValueError("Slug must use 2–63 lowercase letters, digits, or hyphens")

    rights.assert_authorized(target_language)
    project_dir = workspace.expanduser().resolve() / slug
    if project_dir.exists():
        raise FileExistsError(f"Project already exists: {project_dir}")

    project_dir.mkdir(parents=True)
    for directory in JOB_DIRECTORIES:
        (project_dir / directory).mkdir()

    manifest = {
        "schema_version": 1,
        "slug": slug,
        "source_title": rights.source_title,
        "target_language": target_language,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "awaiting_media_import",
    }
    (project_dir / "project.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return project_dir
