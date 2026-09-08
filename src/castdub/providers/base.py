from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence


@dataclass(frozen=True)
class TimedUtterance:
    cue_id: str
    start_ms: int
    end_ms: int
    text: str
    speaker_cluster: str | None = None


@dataclass(frozen=True)
class SynthesizedTake:
    audio_path: Path
    duration_ms: int
    model_revision: str
    parameters: dict[str, str | int | float | bool]


@dataclass(frozen=True)
class PerformanceDescriptor:
    emotion: str
    intensity: float
    speaking_rate: float
    pause_boundaries_ms: tuple[int, ...]
    breath_boundaries_ms: tuple[int, ...]
    reference_audio: Path
    vocal_events: tuple[str, ...] = ()


class SeparatorProvider(Protocol):
    def separate(self, source_audio: Path, output_dir: Path) -> dict[str, Path]: ...


class AlignmentProvider(Protocol):
    def align(
        self, source_audio: Path, subtitle_path: Path
    ) -> Sequence[TimedUtterance]: ...


class DiarizationProvider(Protocol):
    def diarize(self, dialogue_audio: Path) -> Sequence[TimedUtterance]: ...


class PerformanceAnalysisProvider(Protocol):
    def analyse(
        self, utterance: TimedUtterance, reference_audio: Path
    ) -> PerformanceDescriptor: ...


class TranslationProvider(Protocol):
    def translate_scene(
        self, utterances: Sequence[TimedUtterance], target_language: str
    ) -> Sequence[TimedUtterance]: ...


class TTSProvider(Protocol):
    def synthesize(
        self,
        text: str,
        voice_profile: Path,
        target_language: str,
        target_duration_ms: int,
        output_path: Path,
        performance: PerformanceDescriptor | None = None,
    ) -> SynthesizedTake: ...
