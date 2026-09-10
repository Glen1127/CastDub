# Changelog

This project follows [Semantic Versioning](https://semver.org/).

## 1.0.0 - 2026-09-10

### Added

- CastDub — Codex Edition product identity and natural-language quick start.
- Codex Production Skill guidance for automatic character resolution, scene
  translation and duration adaptation, voice-reference selection, complete
  timeline repair, and low-token execution.
- One-command local installation of the bundled Production Skill.
- Chinese-first GitHub landing page with an authorised EP02 A/B demonstration.

### Compatibility

- Kept the `castdub` CLI, Python package name, production directories, job
  schema, Skill directory, and existing episode assets unchanged.

## 0.1.0 - 2026-09-09

### Added

- Rights-gated, resumable Jianying/Douyin episode workflow.
- Auditable character mapping, translations, voice profiles, and takes.
- Local SenseVoice performance analysis and Qwen3-TTS/MLX synthesis workers.
- Duration fitting, dialogue/background reconstruction, subtitles, delivery,
  and blocking QC.
- Editor package and final-video output routes.
- Portable production Skill and synthetic three-character demo.

### Fixed

- Preserved late compressed background tracks across the complete timeline.
- Corrected ASS timing and retained the EP01-approved subtitle reference style.
- Recombined unclaimed split dialogue fragments so localized speech starts at
  the complete source utterance boundary.
