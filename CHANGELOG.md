# Changelog

This project follows [Semantic Versioning](https://semver.org/).

## 1.0.0 - 2026-09-10

### Added

- CastDub — Codex Edition product identity and natural-language quick start.
- Codex Production Skill guidance for automatic character resolution, scene
  translation and duration adaptation, voice-reference selection, complete
  timeline repair, and low-token execution.
- One-command local installation of the bundled Production Skill.
- Explicit local Qwen3-TTS/MLX and SenseVoice worker installers, with model
  licence gates, pinned runtimes, receipts, and full resource estimates.
- Chinese-first GitHub landing page with an authorised EP02 A/B demonstration.

### Fixed

- Bound every Qwen3-TTS request to the character's approved stable voice audio
  and matching transcript instead of replacing identity with a per-line
  performance reference. This prevents same-character timbre drift.
- Made the release check select the current version's wheel and source archive
  when older build artifacts are also present in `dist/`.
- Persisted approved utterance-boundary corrections across resynthesis and
  capped provider-generated leading silence before timeline placement.
- Added an approved, checksummed picture-master override so reconstructed
  subtitle-free footage survives every final-video rerender.
- Validate each generated Qwen take against every approved episode voice
  profile, retry identity drift automatically, and fail closed when no
  candidate preserves the intended character.

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
