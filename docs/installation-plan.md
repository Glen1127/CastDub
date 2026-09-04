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
- `studio-performance`: pinned PyTorch/FunASR worker for emotion and vocal-event
  analysis. Keep this separate from the MLX environment so the two runtimes do
  not force incompatible NumPy or Torch upgrades.
- `studio-tts-mlx`: MLX-Audio 0.4.5, matching the locally verified runtime.

## Phase-one model downloads

- Demucs `htdemucs_ft`.
- faster-whisper `large-v3-turbo`.
- Chinese wav2vec2 forced-alignment model.
- `pyannote/speaker-diarization-community-1` after local Hugging Face login and acceptance of its conditions.

Qwen3-TTS weights are reused by path and are not copied. CosyVoice is deferred until a pilot character fails the Qwen acceptance test.

## Performance-analysis addition awaiting approval

The next implementation stage needs a local analyser; Qwen3-TTS Base can consume
reference audio but is not the emotion classifier.

### Recommended first provider

- Model: `FunAudioLLM/SenseVoiceSmall`, fixed to an approved revision when
  downloaded.
- Purpose: per-line emotion labels plus vocal events such as laughter, crying,
  coughing and speech/non-speech cues. WhisperX remains the source of word-level
  timing; this model enriches the performance descriptor rather than replacing
  it.
- Model download: 944 MB published repository size (936 MB main weight file).
- Runtime dependencies: a separate Python environment with `torch>=2.12.1`,
  `torchaudio>=2.11.0`, `funasr>=1.3.26`, `numpy<=1.26.4`, `modelscope`,
  `huggingface` and `huggingface_hub`. UI/service-only packages in the upstream
  requirements (`gradio`, `fastapi`) are not needed for the offline worker.
- Additional disk estimate: 2.5-4 GB including the model, Python environment,
  Torch and caches. Peak unified-memory estimate on the M4 Mac: 2-4 GB during
  short-line inference. These are planning estimates and must be measured by the
  local smoke test.
- Account/login: the public repository is readable without Hugging Face login.
  The exact revision and checksums are recorded in provenance.
- Licence: the code repository is MIT, while the Hugging Face weights are marked
  `model-license`. Do not redistribute the weights or put them in release
  artifacts; the operator must review and accept the model terms before local
  download/use.
- Privacy: audio stays on the local Mac. The worker must use an explicit local
  model path after installation and must not silently fetch models during an
  episode job.

### Deferred alternative

- Model: `emotion2vec/emotion2vec_plus_base`.
- Purpose: specialised emotion embeddings/classification when SenseVoice labels
  fail the pilot acceptance test.
- Download: about 1.12 GB; published hardware estimate is about 4 GB memory.
- Runtime: FunASR/PyTorch; licence is also marked `model-license` and requires
  review. Do not install both providers for the first pilot.

### Approval boundary

Approval authorises only creation of `studio-performance`, installation of the
listed runtime packages, and downloading the pinned SenseVoiceSmall files. It
does not authorise the Demucs/WhisperX/pyannote downloads listed above, the
CosyVoice fallback, cloud processing, or redistribution of any model weights.
