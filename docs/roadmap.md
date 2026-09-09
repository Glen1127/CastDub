# Open-source roadmap

## Product boundary

Drama Localisation Studio is a local-first production tool for authorised
multi-character dubbing. The program owns deterministic execution and disk
state. An Agent Skill may operate the program, but production state must never
depend on a chat transcript.

The first supported route is a matching Jianying/Douyin draft plus a clean,
no-subtitle episode master. Lip synchronisation and automated publishing are
outside the v0.1 acceptance gate.

## v0.1 milestones

Current core status: every rights-gated production stage has a resumable CLI
entry point through final QC and completion. SenseVoice and Qwen3-TTS/MLX
workers, the convenience orchestrator, and a real multi-character episode have
been validated on Apple Silicon. The v0.1 release remains intentionally CLI
first.

### 1. Safe, installable core

- Protect licensed media, voices, model weights, generated work, and logs from
  source control.
- Provide `castdub doctor`, rights-gated project creation, draft import, and
  compact machine-readable results.
- Publish a Python wheel and source archive.
- Test core behavior without network access or model downloads.

### 2. Resumable episode runner

- Store job state and approvals in SQLite with immutable stage manifests.
- Add `castdub run <episode> --target <language>` as a convenience orchestrator
  over the implemented stage-level resume commands.
- Split analysis, MLX TTS, and media work into process boundaries.
- Cache analysis and synthesis by content fingerprint.
- Write verbose logs to the episode directory.

### 3. Provider route

- Jianying/Douyin draft adapter.
- Official M&E preference and reviewed Demucs fallback.
- Draft-first timing and human-approved character mapping.
- Human or configured translation provider.
- Qwen3-TTS MLX provider; CosyVoice remains an optional fallback.
- FFmpeg subtitle, dialogue, mix, and unchanged-picture render provider.

### 4. Local workbench (v0.2+)

- Episode input pairing and preflight.
- Character mapping and reference approval.
- Scene translation, duration adaptation, emotion, and breath editing.
- Per-line audition, regenerate, approve, and revert.
- QC review and editor/final package export.

### 5. Public release

- Synthetic fixtures and mock providers; no copyrighted production media.
- Apple Silicon installation and upgrade documentation.
- Third-party licence and model-gating review.
- Reproducible release checks and a version tag.

## Deferred after v0.1

- A non-technical local workbench.
- WhisperX alignment and pyannote speaker clustering for projects without a
  sufficiently structured Draft.
- Reverse-video blueprint generation.
- Lip synchronisation and automated publishing.

## v0.1 acceptance

- A fresh Apple Silicon machine can install the core and run `castdub doctor`.
- Missing rights or mismatched episode assets stop before analysis or synthesis.
- At least three characters retain separately approved voice identities.
- Target subtitles describe the final approved target speech.
- Dialogue-only, full-mix, subtitle, editable timeline, QC, and final-video
  packages are produced.
- Interrupted jobs resume without repeating completed expensive stages.
- No source media, cloned voices, model weights, secrets, or personal paths are
  present in the source or release archives.
