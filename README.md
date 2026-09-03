# Drama Localisation Studio

## Agent skill

The reusable production workflow lives at
[`skills/drama-localisation-production/SKILL.md`](skills/drama-localisation-production/SKILL.md).
Copy that whole skill directory into a compatible agent's skills directory, or
give its `SKILL.md` to an agent that supports filesystem and process tools.

Local-first, open-source production tooling for authorised multi-character film
and drama localisation: character-aware performance analysis, stable
cross-language voice cloning, emotion/prosody transfer, automatic dubbing,
duration fitting, soundtrack preservation, and subtitle reconstruction.

The first milestone converts a 3–5 minute Chinese scene with at least three speaking characters into an English dubbed video while preserving the original picture, music, ambience, and effects. Lip synchronisation is explicitly not a first-stage acceptance gate.

## Non-negotiable gates

- Translation, dubbing, voice cloning, and overseas distribution rights must be approved before processing.
- Every cloned voice is bound to an explicitly authorised character profile.
- Cross-character voice reuse is rejected unless separately authorised.
- Source media, voice references, generated audio, model weights, and logs are never committed.
- Final English subtitles are generated from the approved English script and aligned dubbed audio, never relabelled Chinese subtitles.

## Planned pipeline

```text
video + matching Chinese SRT
  -> inspect streams and prefer official M&E when available
  -> Demucs fallback for dialogue/background separation
  -> SRT-assisted WhisperX alignment + ASR discrepancy report
  -> pyannote speaker clustering
  -> human character mapping and voice-profile approval
  -> scene-aware translation and duration-aware adaptation
  -> per-character Qwen3-TTS synthesis
  -> iterative duration fit and mix
  -> English video, subtitles, editable timeline, voice profiles, QC report
```

## Current status

The repository contains a working CLI pilot, Jianying/Douyin draft import and
export, rights gates, reusable character profiles, local Qwen3-TTS synthesis,
duration fitting, subtitles, mixing, delivery packaging, and QC foundations.
The next milestone turns those pieces into a resumable episode state machine and
a non-technical local workbench.

## Local development

The current skeleton uses only Python's standard library:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m castdub --help
```

Inspect the machine without installing packages or downloading models:

```bash
PYTHONPATH=src python -m castdub doctor
```

Render a six-second, three-character synthetic delivery to verify the complete
media path without a model or licensed input:

```bash
PYTHONPATH=src python -m castdub demo --output-dir /tmp/castdub-demo
```

Reverse a finished episode into factual shot data, optional semantic analysis,
an editor-neutral blueprint, and an independent Jianying project copy:

```bash
PYTHONPATH=src python -m castdub reverse resource/剧集/EP01.mp4 \
  --output resource/剧集/EP01.reverse \
  --jianying-template 'resource/剧集Project/EP01 '
```

The command never installs packages or downloads models. PySceneDetect is the
preferred shot detector; FFmpeg supplies a deterministic fallback. OpenCV,
Qwen3-VL through an OpenAI-compatible local endpoint, Demucs `htdemucs_ft`, and
faster-whisper report `unavailable` until explicitly configured with installed
code and local model paths. See `readiness.json` in the output directory.

Register an authorised episode as a resumable job:

```bash
PYTHONPATH=src python -m castdub start-episode \
  --store /private/work/jobs.sqlite3 \
  --series-id example-series \
  --episode-id EP01 \
  --target-language en-US \
  --output-mode final \
  --rights /private/work/rights.json \
  --draft-root /private/source/EP01-draft \
  --source-video /private/source/EP01-clean.mp4
```

Create an empty production job after preparing a rights JSON document:

```bash
PYTHONPATH=src python -m castdub init-project \
  --workspace /path/to/private/workspace \
  --slug pilot-001 \
  --rights /path/to/rights.json \
  --target-language en-US
```

See `docs/installation-plan.md` before installing analysis or TTS dependencies.
See `docs/roadmap.md` for the executable open-source milestones.
