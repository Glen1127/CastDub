# Releasing

1. Use Python 3.12 or 3.13 and ensure FFmpeg/FFprobe are on `PATH`.
2. Run `scripts/release-check.sh` from the repository root.
3. Confirm `git status --short` contains no release-scope changes.
4. Review `CHANGELOG.md`, then create an annotated `vX.Y.Z` tag.
5. Push the commit and tag to the public repository.
6. Attach the wheel and source archive from `dist/` to the release.
7. Never attach episode media, voice profiles, model files, logs, or work
   directories. The only exception is a separately authorised, QC-approved,
   rights-labelled demonstration clip uploaded as a GitHub user attachment.
