# QC and delivery contract

## Blocking QC

- Rights and target-language permission confirmed.
- Every utterance has a named/approved character or an explicit non-character system voice.
- No unapproved cross-character voice reuse.
- Spoken target text matches the final target subtitle.
- No missing, truncated, duplicated, or overlapping lines outside intentional dialogue overlap.
- Every line fits its approved window; any tempo correction stays within project limits.
- Original music, ambience, and effects are present without audible source-dialogue leakage that changes meaning.
- Final video uses the clean no-subtitle master and contains no source-language burned subtitles.
- Output duration, frame rate, dimensions, audio layout, and subtitle safe area pass validation.

Lip sync is non-blocking in the first production phase.

## Human spot checks

Review opening lines, each first character appearance, every role transition, all performance-reference lines, emotional peaks, rapid exchanges/overlaps, countdowns, and ending. A native-language reviewer must approve translation and pronunciation before release.

## Required episode layout

```text
projects/<episode-job>/
  import/                 source map and import report
  translations/           versioned target scripts
  performance-references/ episode delivery references
  voice-profiles/         episode-local role evidence
  synthesis/              raw, cleaned, fitted, rejected takes
  mix/                    dialogue-only and full-mix masters
  provenance/             parameters, hashes, decisions
  qc/                     reports and logs
  deliverables/
    editor/               dialogue-only WAV, full-mix WAV, target/bilingual subtitles, timeline
    final/                burned-subtitle MP4, sidecar subtitles, QC
    reports/              elapsed time and local/API cost estimates
```

The cumulative library lives at `asset-library/series/<series-id>/characters/<character-id>/` and is not duplicated or reset per episode.

## Naming

Use `<episode>.<BCP-47-language>.<artifact>` consistently, for example:

- `EP02.es-ES.dialogue-only.wav`
- `EP02.es-ES.full-mix.wav`
- `EP02.es-ES.srt`
- `EP02.zh-es-ES.srt`
- `EP02.es-ES.mp4`

Manifests must include size, hash, creation time, source paths, provider/model, character profile IDs, translation version, and QC status.
