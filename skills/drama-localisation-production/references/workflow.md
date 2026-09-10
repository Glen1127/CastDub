# Canonical episode workflow

## 1. Audit and immutable import

Run the preflight script. Copy no source media. Create an episode work directory and write an import manifest containing exact paths, hashes, stream metadata, draft ID, duration, and tool versions.

## 2. Parse the draft

Extract, without rendering the draft:

- text tracks and timing;
- audio/video material references;
- audio track type, source range, target range, speed, and volume;
- dialogue, music, ambience, and effects classification;
- character clues from filenames, track placement, subtitles, and nearby picture.

Write a compact source map and editable utterance timeline. Never paste the full draft JSON into model context.

## 3. Resolve characters

Match each speaking segment automatically to the cumulative series voice library by stable character ID. Combine Draft grouping, repeated material references, dialogue and scene context, picture clues, and prior episode evidence; filenames alone are provenance, not identity. Register new episode samples as candidates and write the selected mapping as an auditable approval artifact. Never replace `selected.wav` automatically. Ask the user only about unresolved or conflicting speakers.

## 4. Build performance references

Maintain two layers without conflating them:

- stable character reference for cross-episode timbre;
- episode performance reference for line-level emotion, pace, pauses, breaths, and delivery.

For Qwen3-TTS Base, the stable character sample and its exact transcript are the
voice-cloning prompt. Do not replace that prompt with the per-line performance
audio; doing so changes identity between lines. Performance audio may drive
emotion/event descriptors and duration decisions. A provider may consume both
only after its identity-safe multi-conditioning path has been explicitly tested.

Prefer clean, non-overlapping reference audio. Record source path, start, duration, transcript, character, and approval state.

## 5. Translate and adapt by scene

Use Codex to translate with scene context, relationships, titles, terminology, emotion, and target market in view. Preserve plot meaning while shortening or restructuring lines to fit their original windows. Store source text, target text, version, execution state, emotion, and target duration per utterance. Do not stop merely because the deterministic engine represents this result as an approval artifact.

## 6. Synthesize and fit duration

Generate each line from its approved stable character profile and the approved
performance descriptors. Cap provider-generated leading silence to a short
natural pre-roll before placing the take on the timeline. Persist any approved
utterance-boundary repair in `approvals/timing-corrections.v1.json`; resynthesis
must apply it before mixing and subtitle generation. If a line overruns:

1. improve the target-language adaptation;
2. adjust punctuation and pauses;
3. regenerate;
4. apply only small formant-preserving time correction.

Reject clipping, missing words, wrong language, wrong character, unstable timbre, and excessive speed. Keep rejected takes and parameters in provenance.

## 7. Reconstruct audio

Render a full-length dialogue-only master. Build the background from official M&E when supplied, otherwise from draft music/effect/ambience tracks. Use source separation only when the draft cannot provide a viable background, and flag residual dialogue/background damage for human review. Mix target dialogue with background, duck when necessary, and enforce peak/loudness policy.

## 8. Build subtitles

Create captions from the approved target script and final synthesized speech bounds. Split for readability without changing spoken text. Produce target SRT/VTT as required and a source/target bilingual subtitle. Do not copy the timing or wording of a superseded subtitle blindly.

## 9. Render from the clean master

Keep the clean picture unchanged except for the requested burned subtitles. If
the supplied master contains source subtitles in any interval, reconstruct the
affected picture from matching Draft video segments and record the approved,
checksummed result in `approvals/picture-master.v1.json`. Delivery must reuse
that approved picture on every rerender instead of falling back to the original
contaminated file. Replace audio with the full mix. Default subtitle style:
bottom-centre, `Alignment=2`, `MarginV=18`, white text, dark outline, safe
readable size. Do not use the draft as the mandatory final renderer.

## 10. QC and package

Run deterministic validation, then inspect targeted samples at the opening, every character change, emotional peaks, overlaps/countdowns, and the ending. Check full-timeline coverage rather than only reported timestamps. Package editor and final routes separately and write a usage/time report.
