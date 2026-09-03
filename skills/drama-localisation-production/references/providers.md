# Provider selection

## Selection rule

Choose a provider only when its installed model explicitly supports all of:

1. the target language;
2. cross-language voice cloning or an approved equivalent;
3. the current hardware/runtime;
4. the required licence and distribution use.

Do not infer support from tokenizer coverage, an `auto` language option, or a successful model load. Run a short pronunciation and identity sample before the full episode.

## Preferred local route

Use Qwen3-TTS through MLX-Audio on Apple Silicon when the installed checkpoint lists the target language and voice-cloning mode. Keep one persistent profile per character and add episode performance references per selected line.

If the target language is unsupported, stop before full synthesis. Present candidate providers with model/checkpoint name, purpose, download size, peak memory estimate, hardware support, account/login requirement, licence, and privacy implications. Install only after approval.

CosyVoice or another provider may be added behind the same utterance contract; it must not silently change character identity, timing policy, or provenance fields.

## Provider-neutral utterance contract

Each synthesis request contains:

```json
{
  "utterance_id": "u001",
  "character_id": "lead",
  "target_language": "es-ES",
  "target_text": "...",
  "target_duration_ms": 2400,
  "emotion": "...",
  "stable_voice_reference": "...",
  "performance_reference": "...",
  "reference_transcript": "..."
}
```

Each response records provider, model/checkpoint, seed and sampling parameters, raw path, fitted path, durations, tempo ratio, cache fingerprint, and QC status.
