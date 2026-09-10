# Architecture

The application is intentionally split across process boundaries:

1. **Studio core** owns jobs, rights, timelines, approvals, subtitles, mixing, and provenance.
2. **Analysis worker** owns PyTorch, Demucs, WhisperX, and pyannote.
3. **Performance worker** owns the optional FunASR/SenseVoice runtime for local
   emotion and vocal-event evidence.
4. **MLX TTS worker** owns MLX-Audio and Qwen3-TTS.

Workers exchange small JSON job descriptions and filesystem artifact paths. Model objects and raw audio are never passed through the web application process. Each stage writes an immutable manifest so failed work can resume without re-running earlier stages.

Identity and performance are separate controls. A character's approved stable
reference is immutable during an episode. A per-line performance reference may
be used only when it came from that same approved character. Qwen3-TTS receives
the stable reference and its exact transcript as the cloning prompt. After each
take, the worker compares the generated speaker embedding against every approved
character profile in the episode. A take long enough for reliable comparison is
accepted only when the intended character is the closest match and meets the
similarity floor; otherwise the worker retries with bounded generation settings
and fails closed. Very short interjections are recorded as unevaluable rather
than reported as identity matches.

Duration fitting is deterministic. Shorter takes receive trailing silence;
small overruns may use formant-preserving Rubber Band correction. An overrun
above 12% stops at `performance_analysed` and requires text adaptation and
regeneration before the job can reach `synthesis_completed`.

The first release uses SQLite for structured state and JSON/CSV exports for interchange. It does not require Redis, Celery, containers, or a cloud service.

## Media priority

Use an official music-and-effects track when supplied. Otherwise inspect multichannel layouts before falling back to source separation. Demucs output is always treated as an approximation and requires residual-dialogue and background-loss QC.

## Human approval points

- Anonymous speaker cluster to named character.
- Reference clips to persistent voice profile.
- Scene translation and duration adaptation.
- Final voice take and mix.
- Release eligibility.
