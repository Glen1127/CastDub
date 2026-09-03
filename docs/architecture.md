# Architecture

The application is intentionally split across process boundaries:

1. **Studio core** owns jobs, rights, timelines, approvals, subtitles, mixing, and provenance.
2. **Analysis worker** owns PyTorch, Demucs, WhisperX, and pyannote.
3. **MLX TTS worker** owns MLX-Audio and Qwen3-TTS.

Workers exchange small JSON job descriptions and filesystem artifact paths. Model objects and raw audio are never passed through the web application process. Each stage writes an immutable manifest so failed work can resume without re-running earlier stages.

The first release uses SQLite for structured state and JSON/CSV exports for interchange. It does not require Redis, Celery, containers, or a cloud service.

## Media priority

Use an official music-and-effects track when supplied. Otherwise inspect multichannel layouts before falling back to source separation. Demucs output is always treated as an approximation and requires residual-dialogue and background-loss QC.

## Human approval points

- Anonymous speaker cluster to named character.
- Reference clips to persistent voice profile.
- Scene translation and duration adaptation.
- Final voice take and mix.
- Release eligibility.
