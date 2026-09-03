# Installation plan

No command in this document should be run until the user approves the dependency and model download list.

## Already available on the audited M4 Mac

- Python 3.12 and uv.
- FFmpeg 8 with libass, Rubber Band, VideoToolbox, AAC, and loudness filters.
- Node 22, pnpm 10, and SQLite.
- Working MLX/Metal runtime.
- Working local Qwen3-TTS 1.7B Base weights at the configured provider path.

## Phase-one environments

- `studio-core`: application, subtitles, media orchestration, mixing, and QC.
- `studio-analysis`: pinned PyTorch, Demucs, WhisperX, and pyannote stack.
- `studio-tts-mlx`: MLX-Audio 0.4.5, matching the locally verified runtime.

## Phase-one model downloads

- Demucs `htdemucs_ft`.
- faster-whisper `large-v3-turbo`.
- Chinese wav2vec2 forced-alignment model.
- `pyannote/speaker-diarization-community-1` after local Hugging Face login and acceptance of its conditions.

Qwen3-TTS weights are reused by path and are not copied. CosyVoice is deferred until a pilot character fails the Qwen acceptance test.
