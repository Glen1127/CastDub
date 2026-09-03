# Episode input contract

## Always required

For episode `EP02`, the default project layout is:

```text
<project-root>/
  resource/
    剧集Project/EP02/            complete Jianying/Douyin draft
```

The draft directory may have accidental surrounding whitespace. Resolve it by comparing the trimmed directory name, but record the exact path used.

The draft must contain its main draft JSON and every locally referenced audio/video material needed for production.

## Conditionally required clean master

Automatic final-video output additionally requires:

```text
resource/剧集/EP02（无字幕版）.mp4
```

Editor-package and localized-draft output do not require a separate clean master. A full-duration, subtitle-free composite already inside the draft may satisfy this requirement only after duration, dimensions, edit, and subtitle absence are verified. Individual draft clips or short previews do not qualify.

The clean master must match the episode, edit, duration, frame rate, and aspect ratio represented by the draft.

## Optional inputs

```text
resource/字幕/EP02 中文字幕.srt
resource/字幕/EP02 <target-language>字幕.srt
resource/rights/EP02.json
```

Subtitles are evidence and translation references, not authoritative final target captions. Prefer draft timing and verify against audible dialogue.

## Rights record

Before voice synthesis, record confirmation of:

- source-content processing rights;
- translation and dubbing rights;
- voice-cloning permission for each character;
- permitted target languages;
- intended distribution territory and release status.

Do not publish or externally upload source media. Local production approval does not imply release approval.

## Matching checks

- Episode ID appears consistently in the selected draft and, when present, video path.
- For final output, draft duration and clean-master duration differ by no more than the configured tolerance (default 1 second).
- Draft media references resolve or are explicitly classified as unused.
- Video dimensions, frame rate, and audio layout are recorded.
- Existing episode outputs are not overwritten without explicit intent.

If multiple candidate drafts or videos match, stop and ask the user to select exact paths.
