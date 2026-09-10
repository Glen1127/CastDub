---
name: drama-localisation-production
description: Use CastDub to turn an authorised Jianying/Douyin episode into a target-language editor package or finished video. Handles intelligent character mapping, scene translation, local voice-cloned dubbing, mixing, subtitles, QC, and delivery.
---

# CastDub — Codex Edition

Turn a natural-language request such as “把 EP02 制作成英语国际化版本” into one traceable production job. Treat the Jianying/Douyin draft as the structured source of dialogue, timing, music, effects, and performance references. Require a no-subtitle picture master only when automatic final-video output is requested.

## Hard gates

- Require explicit translation, dubbing, voice-cloning, and distribution rights before synthesis.
- Always require a matching draft. Require a matching no-subtitle video for final-video output; it is optional for editor-package or localized-draft output.
- Never modify source assets or overwrite a selected character voice automatically.
- Never reuse a voice across characters without explicit approval.
- Never download a model or dependency without presenting its purpose, size, memory, login, and licence requirements and receiving approval.
- Never relabel source subtitles as target-language subtitles. Build target subtitles from the final approved script and synthesized speech bounds.
- Do not make lip sync a first-pass acceptance gate.

## Start every episode

1. Read [references/input-contract.md](references/input-contract.md).
2. Infer the episode, target language, and requested delivery from the user's request and unambiguous matching files. Do not ask the user to repeat information already present in filenames or job state.
3. Run `scripts/preflight_episode.py --project-root <root> --episode <EPnn> --output-mode <editor|final> --rights-confirmed`.
4. Reuse the existing job, analysis, voices, and generated takes when their provenance still matches; otherwise create a new episode work directory. Preserve source files byte-for-byte.
5. Stop only on a hard gate, genuinely ambiguous inputs or characters, unsupported target language, or a failed blocking QC check that cannot be repaired safely.

## Intelligent execution

- Resolve characters automatically from Draft grouping, material references, dialogue context, picture clues, and the cumulative series voice library. Write the result to the normal approval artifact. Ask only about unresolved or conflicting identities.
- Translate and adapt dialogue by scene. Preserve plot, relationships, names, tone, emotion, and the original speech window; revise wording and regenerate when a take does not fit naturally.
- Select stable voice identity references and same-character performance references automatically. The TTS provider's cloning reference must remain the stable identity sample; use per-line performance audio only for descriptors unless the provider has a verified identity-safe multi-conditioning interface. Never silently replace an already selected cross-episode profile.
- Validate the generated waveform, not only its reference binding. For every take long enough for reliable speaker comparison, compare its speaker embedding with every approved character profile in the episode. Regenerate when the intended character is not the closest match or misses the configured similarity floor; stop synthesis if retries cannot pass. Mark very short interjections as unevaluable instead of claiming an identity pass.
- Execute the complete route through synthesis, duration fitting, background reconstruction, subtitle rebuilding, delivery, and QC. Treat approval files as auditable state records, not automatic reasons to interrupt the user.
- Diagnose and repair missing dialogue, delayed starts, incomplete background timelines, residual source subtitles, subtitle/text mismatch, and style drift across the entire episode before rerendering. Persist approved timing corrections and reconstructed picture masters as job inputs before resynthesis or rerendering; never rely on a one-off output patch. Do not patch only the example timestamp reported by the user.
- Keep raw media and verbose logs out of model context. Read compact manifests, targeted excerpts, and QC summaries; run deterministic local tools for media work.

## Production route

Read [references/workflow.md](references/workflow.md), then execute its stages in order:

`draft audit -> asset map -> character resolution -> performance references -> scene translation/adaptation -> per-character TTS -> duration loop -> dialogue/background mix -> target subtitles -> clean-master render -> QC -> delivery`

Use an official M&E track when present. Otherwise reconstruct background from draft music/effect tracks; use source separation only as a reviewed fallback.

## Provider routing

Before synthesis, read [references/providers.md](references/providers.md). Prefer an already installed local provider that explicitly supports the target language and cross-language voice cloning. A successful load is not proof of language support.

## Acceptance and delivery

Read [references/qc-delivery.md](references/qc-delivery.md). Deliver both:

- Editor package: target dialogue-only WAV, full-mix WAV, target SRT, source/target SRT, editable timeline, role profiles, provenance, QC.
- Final package: requires the clean picture master; includes the unchanged picture with full mix and burned target subtitles, plus sidecar subtitles and QC.

Default burned-subtitle placement is bottom-centre with `Alignment=2` and `MarginV=18`. Preserve this unless the user requests another safe area.

## Portability

Never hard-code a username, home directory, model cache, or application path. Resolve everything from `--project-root`, the episode job config, environment variables, or tool discovery. For Codex, Claude Code, OpenCode, and generic runners, read [references/platform-adapters.md](references/platform-adapters.md).

## Communication

Write verbose logs to the episode `qc/logs/` directory. Report only start, failure, completion, artifact paths, QC exceptions, unresolved roles, and decisions requiring the user. Reuse cached analysis and synthesis artifacts; do not stream model progress or load large draft JSON into chat. Keep the interaction low-token by passing paths and compact structured state between stages.
