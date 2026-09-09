# Changelog

This project follows [Semantic Versioning](https://semver.org/).

## 0.1.0 - 2026-09-09

### Added

- Rights-gated, resumable Jianying/Douyin episode workflow.
- Human-approved character mapping, translations, voice profiles, and takes.
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
