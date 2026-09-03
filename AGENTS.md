# Agent operating rules

For authorised episode localisation, read
`skills/drama-localisation-production/SKILL.md` before acting.

- Never scan or commit `resource/`, `projects/`, `asset-library/`, models, media,
  generated voices, or long logs.
- Never download dependencies or models without explicit user approval.
- Keep licensed inputs immutable and enforce the rights gate before synthesis.
- Use compact command output; write verbose worker logs to the episode job.
