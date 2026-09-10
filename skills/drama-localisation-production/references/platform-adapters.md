# Platform adapters and handoff

## Portable package

Transfer the whole `drama-localisation-production/` directory. Keep `SKILL.md`, `references/`, `scripts/`, `assets/`, and `agents/` together. The skill contains no user-specific absolute path.

## Codex

From the CastDub repository, run `./scripts/install-codex-skill.sh`. It installs under `${CODEX_HOME:-$HOME/.codex}/skills/drama-localisation-production/` without changing the repository copy. Start a new Codex task, invoke `$drama-localisation-production` or allow implicit matching, and describe the episode and target language in natural language. `agents/openai.yaml` supplies Codex UI metadata.

## Claude Code and compatible agents

Place the folder in the platform's supported skills location, or instruct the agent to read `SKILL.md` before work. Add a short rule to the repository's `AGENTS.md` or `CLAUDE.md` only if the platform does not discover project skills automatically.

## Generic agent runner

Provide `SKILL.md` as the operating prompt and expose filesystem plus process execution. The deterministic scripts require Python 3.10+ and `ffprobe` for duration validation. The full production repository additionally provides the `castdub` CLI and local TTS adapter.

## Environment contract

Prefer explicit arguments. When environment variables are needed, use:

```text
DRAMA_LOCALISATION_ROOT   project repository root
CASTDUB_MODEL_ROOT        approved local model directory
CASTDUB_WORK_ROOT         private generated-work directory
```

Do not use a person's home directory in committed configuration.

## Handoff state

Another agent should need only:

- project root;
- episode ID;
- target BCP-47 language;
- explicit rights confirmation or rights file;
- any unresolved character decisions.

All other state must be recoverable from manifests, the episode work directory, and the cumulative character library. Never depend on chat history as production state.

## Standard invocation prompt

```text
Use $drama-localisation-production to make EP02 in <project-root> an es-ES
internationalised final video. Use the matching Jianying/Douyin draft and
subtitle-free master, reuse the series voice library, preserve source assets,
keep long logs on disk, and report only blockers and final paths.
```
