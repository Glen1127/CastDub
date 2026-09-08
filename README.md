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

The repository contains a resumable, rights-gated CLI route through
Jianying/Douyin import, character and translation approval, reusable character
profiles, local performance analysis, Qwen3-TTS synthesis, duration fitting,
take and background approval, mixing, subtitle reconstruction, delivery
packaging, blocking QC, and job completion. The remaining product milestone is
the non-technical local workbench plus real-provider release qualification.

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

If this machine cannot reach PyPI or Hugging Face, install the approved local
performance worker manually when network access is available:

```bash
cd /path/to/drama-localisation-studio
./scripts/install-performance-worker.sh --accept-model-license
```

The script creates only `.venv-performance`, downloads
`FunAudioLLM/SenseVoiceSmall` into `models/SenseVoiceSmall`, pins the resolved
model revision in `models/SenseVoiceSmall.receipt.json`, and writes the full log
to `logs/install-sensevoice.log`. These paths are excluded from Git.

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

Run the registered input check and persist the result:

```bash
PYTHONPATH=src python -m castdub preflight \
  --store /private/work/jobs.sqlite3 \
  --job-id example-series:EP01:en-US
```

Import the verified Draft into an editable timeline. The command stops at the
mandatory character-approval gate and is safe to rerun:

```bash
PYTHONPATH=src python -m castdub import-episode \
  --store /private/work/jobs.sqlite3 \
  --job-id example-series:EP01:en-US
```

Edit the generated `role-mapping.template.json`, set every
`approved_character_id`, and set `approved` to `true`. Then run:

```bash
PYTHONPATH=src python -m castdub approve-roles \
  --store /private/work/jobs.sqlite3 \
  --job-id example-series:EP01:en-US \
  --mapping /private/work/role-mapping.approved.json
```

The command accepts only characters covered by the rights manifest and creates
the translation/performance worklist for the next approval stage.

After editing every `approved_target_text` and marking every row `approved`,
lock the translation while preserving role, timing, source text, and reference
audio:

```bash
PYTHONPATH=src python -m castdub approve-translation \
  --store /private/work/jobs.sqlite3 \
  --job-id example-series:EP01:en-US \
  --worklist /private/work/translation.approved.jsonl
```

Prepare the stable-character voice selection separately from line-level
performance references:

```bash
PYTHONPATH=src python -m castdub prepare-voices \
  --store /private/work/jobs.sqlite3 \
  --job-id example-series:EP01:en-US \
  --library-root /private/work/asset-library
```

Approve either the existing stable profile or one explicit episode reference
for every character:

```bash
PYTHONPATH=src python -m castdub approve-voices \
  --store /private/work/jobs.sqlite3 \
  --job-id example-series:EP01:en-US \
  --approval /private/work/voice-profiles.approved.json
```

Analyse each approved source performance with an explicitly installed local
worker and pinned local model revision. The command never downloads a model:

```bash
PYTHONPATH=src python -m castdub analyse-performance \
  --store /private/work/jobs.sqlite3 \
  --job-id example-series:EP01:en-US \
  --worker-python /private/tools/studio-performance/bin/python \
  --model-path /private/models/SenseVoiceSmall \
  --model-revision APPROVED_REVISION
```

Generate target dialogue with the existing local Qwen3-TTS/MLX worker. Every
request records its character, stable identity reference, same-character
performance reference, text, target window, provider, and model revision:

```bash
PYTHONPATH=src python -m castdub synthesize \
  --store /private/work/jobs.sqlite3 \
  --job-id example-series:EP01:en-US \
  --worker-python /private/tools/mlx-audio/bin/python \
  --model-path /private/models/Qwen3-TTS-Base \
  --model-revision APPROVED_REVISION
```

Takes that exceed the target window by more than 12% stop for text adaptation;
they are not forcibly accelerated. After auditioning every generated take,
approve the unchanged take set before mixing:

```bash
PYTHONPATH=src python -m castdub approve-takes \
  --store /private/work/jobs.sqlite3 \
  --job-id example-series:EP01:en-US \
  --approval /private/work/takes.approved.json
```

Review the generated `background.template.json`. Select only music, ambience,
or effects confirmed not to contain source dialogue, or provide one approved
official M&E track. Then render the dialogue-only and full-mix masters:

```bash
PYTHONPATH=src python -m castdub prepare-mix \
  --store /private/work/jobs.sqlite3 \
  --job-id example-series:EP01:en-US

PYTHONPATH=src python -m castdub render-mix \
  --store /private/work/jobs.sqlite3 \
  --job-id example-series:EP01:en-US \
  --approval /private/work/background.approved.json
```

Create the editor package and, in `final` mode, the burned-subtitle MP4 from
the registered clean master. Target subtitles are generated from the approved
spoken text, using bottom-centre `Alignment=2` and `MarginV=18`:

```bash
PYTHONPATH=src python -m castdub render-delivery \
  --store /private/work/jobs.sqlite3 \
  --job-id example-series:EP01:en-US
```

Run blocking QC and mark the episode complete only after QC passes:

```bash
PYTHONPATH=src python -m castdub run-qc \
  --store /private/work/jobs.sqlite3 \
  --job-id example-series:EP01:en-US

PYTHONPATH=src python -m castdub complete-episode \
  --store /private/work/jobs.sqlite3 \
  --job-id example-series:EP01:en-US
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
