# Series production layout

```text
asset-library/series/<series-id>/
  series.json
  characters/<character-id>/
    profile.json
    selected.wav
    references/<episode-id>.wav

projects/<episode-job>/
  import/                 Jianying import and source mapping
  synthesis/              raw, cleaned, fitted and rejected takes
  voice-profiles/         episode-local references and provenance
  mix/                    working dialogue-only and full-mix masters
  qc/                     machine-readable QC
  deliverables/
    editor/               dialogue-only WAV, full-mix WAV, SRTs, timeline
    final/                optional dubbed MP4, SRTs and QC
    reports/              time and token/cost estimates
```

The stable character ID is the identity key. A filename from a new episode is only provenance. New references are registered as candidates and cannot overwrite `selected.wav` automatically.

The editor package supports manual replacement/export in Jianying or another NLE and does not require a separate clean master. The final package is the automated end-to-end output and requires a verified clean master. Both routes share translation, TTS, timing fit, audio rendering and QC. Final delivery can copy the picture stream when subtitles remain sidecar; burned subtitles require a picture encode.
