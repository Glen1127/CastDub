# Contributing

Contributions are welcome when they preserve the project's local-first,
rights-gated design.

## Development

Use Python 3.12 or 3.13. The core test suite has no runtime dependency beyond
the standard library:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Keep changes small and include a regression test for behavior changes. Provider
integrations must remain optional and must not download models during import,
tests, or environment inspection.

## Media and voices

Do not submit copyrighted production media, third-party drafts, subtitles,
voice references, cloned voices, model weights, credentials, or generated
deliverables. Tests must use synthetic or explicitly redistributable fixtures.

All voice reuse must remain scoped to the approved character. Changes that
bypass rights, character, translation, or final-release approvals will not be
accepted.
