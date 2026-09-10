# CastDub — Codex Edition installation

This is the complete installation contract for `v1.0`. CastDub never downloads
a model during an episode job. Run each model installer only after reviewing its
licence and resource requirements.

## Supported machine

- macOS on Apple Silicon; M4 is the qualified reference platform.
- Python 3.12 or 3.13 for the core. Model workers use isolated Python 3.12 environments.
- 16 GB unified memory minimum; 24 GB or more recommended for production.
- Allow at least 10 GB for CastDub's two required model workers, plus private
  source video, generated takes, caches, and deliverables.
- Windows, Linux, Intel Mac, CUDA, and CPU-only execution are not qualified in v1.0.

## Required components

| Component | Purpose | Download / disk | Peak memory estimate | Login | Terms |
| --- | --- | ---: | ---: | --- | --- |
| Codex | Natural-language execution of the bundled Skill | Installed separately | Account dependent | Codex sign-in | OpenAI product terms |
| Python 3.12/3.13 + `uv` | Core and isolated workers | Under 1 GB before workers | Under 1 GB | No | PSF / MIT |
| FFmpeg + FFprobe | Audio, subtitles, mixing and video | About 0.5 GB | Job dependent | No | Build-dependent open-source licences |
| Qwen3-TTS 12Hz 1.7B Base | Required multilingual voice cloning | About 4.2 GB weights; allow 5–6 GB with environment | About 8–12 GB planning estimate | Public Hugging Face download normally needs no login | Apache-2.0 model card; operator must review |
| SenseVoiceSmall | Required emotion and vocal-event analysis | 0.94 GB weights; allow 2.5–4 GB with environment | About 2–4 GB planning estimate | No login | Model terms must be reviewed; do not redistribute weights |
| CastDub Production Skill | Gives Codex the episode workflow | Under 1 MB | Negligible | No additional login | Apache-2.0 repository code |

The memory figures are conservative planning estimates, not guarantees. Media
resolution, concurrency, reference length, and model revisions change actual use.

## 1. Install system tools

With Homebrew:

```bash
brew install python@3.12 ffmpeg uv
```

Verify that FFmpeg includes the subtitle and Rubber Band filters:

```bash
ffmpeg -filters | grep -E 'subtitles|rubberband'
```

Install Codex using the current instructions at
<https://developers.openai.com/codex/> and sign in before starting a CastDub task.

## 2. Install CastDub core

```bash
git clone https://github.com/Glen1127/CastDub.git
cd CastDub
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
castdub doctor
castdub demo --output-dir /tmp/castdub-demo
```

The core has no ML dependencies and performs no model download.

## 3. Install the Codex Skill

```bash
./scripts/install-codex-skill.sh
```

Start a new Codex task after installation. Example request:

```text
使用 CastDub，把 EP02 制作成英语国际化版本。
```

## 4. Install required local model workers

Review the upstream terms first, then run:

```bash
./scripts/install-tts-worker.sh --accept-model-license
./scripts/install-performance-worker.sh --accept-model-license
```

The first command creates `.venv-tts`, installs `mlx-audio==0.4.5`, downloads
the pinned `Qwen/Qwen3-TTS-12Hz-1.7B-Base` revision to
`models/Qwen3-TTS-12Hz-1.7B-Base`, and writes a receipt and log.

The second creates `.venv-performance`, installs the pinned SenseVoice runtime,
downloads `FunAudioLLM/SenseVoiceSmall` to `models/SenseVoiceSmall`, and writes
its receipt and log.

Expected final paths:

```text
.venv-tts/bin/python
.venv-performance/bin/python
models/Qwen3-TTS-12Hz-1.7B-Base/
models/Qwen3-TTS-12Hz-1.7B-Base.receipt.json
models/SenseVoiceSmall/
models/SenseVoiceSmall.receipt.json
```

All environments, weights, receipts, private media, work products, and logs are
excluded from Git. After the downloads complete, episode production can use
explicit local paths without fetching weights at runtime.

## Optional and deferred providers

Demucs, WhisperX, pyannote, CosyVoice, and emotion2vec are **not required** for
the Draft-first Codex Edition v1.0 route. Do not download them for the initial
setup. They are reserved for missing-Draft/source-separation fallbacks or future
provider support; pyannote models may require a Hugging Face login and gated
licence acceptance.

## Inputs still required per episode

Installation does not supply media or rights. For each job provide:

- a matching Jianying/Douyin Draft;
- the matching subtitle-free source video for automatic final output;
- a target BCP-47 language such as `en-US` or `es-ES`;
- confirmed translation, dubbing, voice-cloning, and distribution rights.

The Skill stops before model installation, voice reuse across characters, or
publishing when the corresponding licence or rights decision is unresolved.
