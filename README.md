# CastDub — Codex Edition

> **将 CastDub Skill 放进 Codex，用一句自然语言，把影视素材自动制作成多语言国际化成片。**

[![CI](https://github.com/Glen1127/CastDub/actions/workflows/ci.yml/badge.svg)](https://github.com/Glen1127/CastDub/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Glen1127/CastDub)](https://github.com/Glen1127/CastDub/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB)](https://www.python.org/)
[![License](https://img.shields.io/badge/Code-Apache--2.0-blue)](LICENSE)
[![Edition](https://img.shields.io/badge/Codex%20Edition-v1.0-111827)](https://github.com/Glen1127/CastDub/releases/tag/v1.0.0)

[中文说明](#项目特点) · [English](#english)

安装 CastDub 和 Production Skill 后，只需对 Codex 说：

```text
使用 CastDub，把 EP02 制作成英语国际化版本。
```

Codex 会智能执行 Draft 解析、角色与跨集声音匹配、影视化翻译改写、本地声音克隆、情绪和时长适配、原声混音、字幕重建、QC 与最终成片合成。用户不需要回到剪辑软件逐条替换音频或字幕。

## EP02 实际效果

以下为同一画面、同一台词时段的对比。英文版保留原画面、配乐与音效，替换角色对白并重新生成与实际发音一致的英文字幕。

<table>
  <tr>
    <th width="50%">中文原版</th>
    <th width="50%">English dub</th>
  </tr>
  <tr>
    <td><img src="docs/assets/ep02-comparison-zh.jpg" alt="EP02 中文原版画面与中文字幕"></td>
    <td><img src="docs/assets/ep02-comparison-en.jpg" alt="EP02 英文配音画面与英文字幕"></td>
  </tr>
</table>

▶ **[观看 8 秒中英配音 A/B 对比](https://github.com/Glen1127/CastDub/releases/download/v1.0.0/EP02.zh-en-US.comparison.mp4)**

画面始终左右并排；前 4 秒播放中文原声，后 4 秒播放英文配音，方便直接比较声音、情绪、气口和时长。

> EP02 截图与试听片段经权利人许可，仅用于展示本项目效果；不属于 Apache-2.0 授权范围，未经许可不得复用或再发布。

## 项目特点

- **多角色稳定音色**：每个角色绑定可跨集累积的声音档案，禁止未经确认跨角色复用。
- **情绪与气口迁移**：稳定音色参考与逐句表演参考分离，保留原角色的情绪、节奏、停顿和呼吸感。
- **按原时间线配音**：译文先做影视化改写，再逐句合成和时长闭环；不以粗暴加速代替台词适配。
- **保留配乐与音效**：优先使用官方 M&E；否则对背景候选做人工审批后再混音，避免残留中文对白。
- **字幕来自最终台词**：英文/其他语言字幕由批准后的目标语言台词与最终音频生成，绝不把中文字幕改标签冒充译文。
- **双交付模式**：既输出供剪辑师替换的中间文件，也可输出已合成的完整国际化视频。
- **可追溯与可续跑**：角色、译文、声音参考、模型版本、生成参数、审批记录和 QC 结果全部留档。
- **本地优先**：核心状态机不联网、不自动下载模型；私有视频和声音资料默认留在本机。

## 输入与输出

最有效率的输入是：某一集的剪映/抖音 Draft 工程 + 对应无字幕原视频 + 权利证明。Draft 提供已经剪好的时间线和素材关系；无字幕母版用于高效、可靠地自动封装最终成片。

| 类型 | 内容 |
| --- | --- |
| 必需输入 | Draft 工程、无字幕视频、目标语言、翻译/配音/声音复制/发行授权清单 |
| 可选输入 | 原始 SRT、角色表、术语表、官方 M&E、已确认的跨集声音档案 |
| 编辑交付 | 目标语言 SRT/VTT/ASS、对白独立音轨、含配乐音效的混音、可编辑台词—角色—时间线 |
| 最终交付 | 目标语言 MP4、英文/双语字幕、角色声音档案、模型与参数记录、QC 报告 |

## 工作流

```text
Draft + 无字幕母版 + 授权清单
  → 导入并核对素材/时间线
  → 识别对白、说话人、情绪和气口
  → 自动解析角色并复用跨集声音档案；歧义时才询问
  → 按场景自动翻译改写并记录可追溯版本
  → 按角色克隆声音、逐句生成和时长适配
  → 审批配音 take 与无中文对白的背景轨
  → 混音、重建字幕、封装编辑包与成片
  → 阻断式 QC 与可追溯报告
```

首阶段验收重点是角色、声音、情绪、节奏、字幕和混音可信；口型同步不是 Codex Edition v1.0 的验收门槛。

## 当前版本

`CastDub — Codex Edition v1.0` 已实现可续跑、带授权门禁的智能生产流程：剪映/抖音 Draft 导入、自动角色映射、场景翻译改写、跨集声音档案、本地表演分析、Qwen3-TTS 合成、时长适配、take/背景检查、混音、字幕重建、双模式交付、阻断式 QC 和任务完成。

完整流程已在 Apple Silicon 上用真实多角色剧集验证。图形工作台，以及基于 WhisperX/pyannote 的独立说话人发现，仍属于后续里程碑，不是 Codex Edition v1.0 已完成 API。

## 安装前先确认

当前 `v1.0` 只正式支持 **Apple Silicon Mac**，并且完整生产不是只安装 Python 包就能运行：

| 必需项 | 用途 | 是否需要另外下载 |
| --- | --- | --- |
| Codex | 通过自然语言执行 CastDub Skill | 是，需要安装并登录 |
| Python 3.12/3.13、`uv` | 核心程序与隔离 worker | 是 |
| FFmpeg、FFprobe | 音轨、字幕、混音、视频封装 | 是 |
| Qwen3-TTS 12Hz 1.7B Base + MLX-Audio | 多语言角色声音克隆 | **是，约 4.2 GB 模型；完整生产必需** |
| SenseVoiceSmall | 情绪和声音事件分析 | **是，约 0.94 GB 模型；完整生产必需** |
| CastDub Production Skill | 让 Codex 理解并执行完整流程 | 是，仓库内置，一条命令安装 |

建议至少 16 GB 统一内存、预留 10 GB 模型和环境空间；24 GB 以上更适合正式生产。Demucs、WhisperX、pyannote、CosyVoice 在 Draft-first v1.0 中不是必装项。

**完整安装步骤、模型许可、Hugging Face 登录条件、磁盘/内存估算及安装后路径：[`docs/installation-plan.md`](docs/installation-plan.md)。请先读该文件，不要只执行下面的核心安装。**

## 快速开始

要求 Python 3.12 或 3.13，并确保 `ffmpeg`、`ffprobe` 位于 `PATH`。安装核心不会下载任何模型：

```bash
git clone https://github.com/Glen1127/CastDub.git
cd CastDub
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
castdub doctor
castdub demo --output-dir /tmp/castdub-demo
./scripts/install-codex-skill.sh
```

完整生产还必须安装两个本地 worker：

```bash
./scripts/install-tts-worker.sh --accept-model-license
./scripts/install-performance-worker.sh --accept-model-license
```

重新打开 Codex 或开始一个新任务，然后直接用自然语言指定剧集和目标语言。大规模音视频处理由本地模型和工具完成；Skill 让 Codex 只读取紧凑的结构化生产信息并智能执行，因此无需把大型媒体装入上下文。

架构与生产目录分别见 [`docs/architecture.md`](docs/architecture.md) 和 [`docs/production-layout.md`](docs/production-layout.md)。

## 授权与隐私门禁

- 处理前必须确认翻译、配音、声音复制和海外发行权。
- 每个克隆声音必须绑定明确获权的角色；跨角色复用需单独批准。
- 源视频、声音参考、生成音频、模型权重和长日志不得提交到仓库。
- 发布前必须经过角色、译文、声音、take、背景轨和 QC 审批。
- 示例媒体与代码授权分离；代码使用 Apache-2.0，演示素材不自动获得开源许可。

## Agent Skill

Codex Edition 的核心生产规范位于 [`skills/drama-localisation-production/SKILL.md`](skills/drama-localisation-production/SKILL.md)。运行 `./scripts/install-codex-skill.sh` 即可安装到当前用户的 Codex Skills 目录；内部 Skill 名称为 `$drama-localisation-production`，为兼容现有流程暂不改名。

## 完整 CLI 工作流

<details>
<summary>展开 Codex Edition v1.0 命令参考</summary>

以下命令覆盖本地自检、模型 worker、剧集注册、各审批门禁、合成、混音、交付和 QC。

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
cd /path/to/CastDub
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

</details>

## English

CastDub — Codex Edition is a natural-language-driven, local-first production
pipeline for multi-character screen localisation. Install its Production Skill
in Codex, identify an episode and target language, and Codex intelligently runs
the traceable local workflow from matching Jianying/Douyin Draft and clean
master to editor assets and a finished internationalised video.

Codex Edition `v1.0` has been qualified on real multi-character episodes on
Apple Silicon. The GUI and standalone WhisperX/pyannote speaker discovery remain
future work. Lip sync is intentionally not a first-stage acceptance gate.

Quick start:

```bash
git clone https://github.com/Glen1127/CastDub.git
cd CastDub
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
castdub doctor
castdub demo --output-dir /tmp/castdub-demo
./scripts/install-codex-skill.sh
```

Only process media and voices for which you hold translation, dubbing, voice
cloning, and distribution rights. The EP02 demonstration media is shown with
the rights holder's permission and is not licensed under Apache-2.0.
