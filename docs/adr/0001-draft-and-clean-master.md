# ADR 0001: Draft is production source; clean master is the final renderer source

Status: accepted

## Context

A Jianying/Douyin draft contains timeline structure and packaged source clips,
audio, music, effects, captions, and edit metadata. It does not necessarily
contain a full-duration, subtitle-free composite. Re-rendering proprietary edit
effects outside Jianying is slow and unreliable.

The inspected EP01 and EP02 packages contain many component clips, but their
top-level videos are only about five seconds and do not match the complete
episodes.

## Decision

- A complete matching draft is required for every job.
- Editor-package and localized-draft output can run without a separate clean
  master.
- Automatic final-video output requires a matching full-duration,
  subtitle-free picture master.
- A composite found inside a draft may serve as that master only after explicit
  verification.
- Final rendering preserves the clean picture and replaces audio, adding target
  subtitles when requested.

## Consequences

The editor route remains flexible and can hand control back to Jianying. The
automatic final route is faster, deterministic, independent of proprietary
effect rendering, and preserves picture quality. Users requesting both routes
provide the clean master once and receive both deliverable packages.
