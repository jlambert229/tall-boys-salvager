# ElevenLabs configuration (Salvager Chapter 1)

This folder wires **Salvager** audio drama text to **ElevenLabs** in two supported ways: **Text-to-Dialogue API** (multi-speaker, `eleven_v3`) and **Projects** (long-form, manual blocks).

## 1. Text-to-Dialogue API (recommended for scripted turns)

**Receipt:** [Text to Dialogue](https://elevenlabs.io/docs/overview/capabilities/text-to-dialogue) (ElevenLabs docs, fetched 2026-05-03).

| Rule | Detail |
| --- | --- |
| Model | **`eleven_v3` only** for Text-to-Dialogue. |
| Request size | **Total characters across all `inputs[].text` ≤ 2,000 per request.** Split the chapter into chunks and **concatenate** MP3 (or PCM) in your DAW. |
| Speakers | No hard cap on speaker count; each `input` picks a `voice_id`. |
| Consistency | Output is nondeterministic; use optional **`seed`** for repeatability. |
| Ownership | You own output; **commercial use** needs a **paid** plan per docs. |

### Voice roles (`voice_map.yaml`)

| Key | Use |
| --- | --- |
| `bam` | Spoken dialogue (`BAM` without V.O. in the screenplay). |
| `bam_interior` | Internal monologue (`BAM (V.O.)`). Often the **same** `voice_id` as `bam`; use a second voice only if you want a clear “head voice.” |
| `sketch` | All `SKETCH` lines. |
| `uncle_iton` | All `ITON` lines. |
| `tommy` | `TOMMY` in screenplay (fire ring). |
| `samantha` | `SAMANTHA` if you add spoken lines later (walla-only in Chapter 1 as written). |

Fill **`elevenlabs_voice_id`** with UUIDs from the ElevenLabs app (Voice Library or your clones).

### Eleven v3 audio tags (square brackets)

**Receipt:** Same docs page: emotional and non-speech cues use **square brackets** in the text, for example `[sigh]`, `[whispering]`, `[laughing]`. Results may vary (feature under active development).

Use **sparingly** for Salvager:

- Interior: `[quietly]` or `[thoughtful]` before a `bam_interior` line.
- Sketch: `[flatly]` or `[deadpan]` on key lines if delivery is too warm.
- Tracer beat: optional `[tense silence]` only if you are **not** mixing real SFX in post.

Do **not** rely on brackets for full sound design; keep explosions, footfalls, and beds for **post** (see `sound_palette_yorp.yaml`).

### Chunked JSON for the API

From `salvager/` (install PyYAML only if you use `--chapter-yaml`):

```bash
pip install -r scripts/requirements-export.txt   # once, if using --chapter-yaml

python3 scripts/export_elevenlabs_chapter1.py \
  --screenplay cp_01_screenplay.md \
  --voice-map story_database/audio_drama/elevenlabs/voice_map.yaml \
  --out story_database/audio_drama/elevenlabs/generated/chapter_01_dialogue_chunks.json
```

Optional: export from the beat YAML after you confirm it matches the screenplay (order is `lines` then `vo_over` per block):

```bash
python3 scripts/export_elevenlabs_chapter1.py \
  --chapter-yaml story_database/audio_drama/chapter_01_audio_script.yaml \
  --voice-map story_database/audio_drama/elevenlabs/voice_map.yaml \
  --out story_database/audio_drama/elevenlabs/generated/chapter_01_dialogue_chunks.yaml_source.json
```

The script emits **arrays of `{ "voice_id", "text" }`** per chunk, each chunk under the character budget. If any `voice_id` is still `REPLACE_`, it prints a warning. JSON field `source` records which file was used.

### Render to MP3 (rough cut)

Use `scripts/render_elevenlabs_chapter1.py` to POST each chunk to ElevenLabs Text-to-Dialogue and stitch the results with `ffmpeg`.

**Pre-flight checklist (do once):**

| Step | Action |
| --- | --- |
| 1 | Get an API key: ElevenLabs > Settings > API Keys. |
| 2 | Pick or clone voices: Voice Library / Voice Lab. Copy the voice UUID for each role (`bam`, `bam_interior`, `sketch`, `uncle_iton`, `tommy`, `samantha`). |
| 3 | Edit `voice_map.yaml`: replace each `REPLACE_WITH_VOICE_UUID` with a real voice UUID. |
| 4 | Re-run the exporter so chunks JSON has real IDs (or pass `--voice-map` to the renderer to substitute in place). |
| 5 | `pip install -r scripts/requirements-export.txt` (adds `requests`). |
| 6 | Install ffmpeg: `sudo apt install ffmpeg` (Linux) or `brew install ffmpeg` (macOS). |
| 7 | `export ELEVENLABS_API_KEY=sk_...`. |

**Recommended first run (cost-cheap voice sanity check):**

```bash
# Dry run: prints chunk count + total characters, no API call.
python3 scripts/render_elevenlabs_chapter1.py \
  --input  story_database/audio_drama/elevenlabs/generated/chapter_01_dialogue_chunks.json \
  --dry-run

# Render only chunk 0 (~1900 chars, ~2-3 min of audio). Listen before committing.
python3 scripts/render_elevenlabs_chapter1.py \
  --input  story_database/audio_drama/elevenlabs/generated/chapter_01_dialogue_chunks.json \
  --chunks 0 \
  --no-stitch
```

**Full chapter render + stitch:**

```bash
python3 scripts/render_elevenlabs_chapter1.py \
  --input  story_database/audio_drama/elevenlabs/generated/chapter_01_dialogue_chunks.json \
  --output-dir story_database/audio_drama/elevenlabs/generated/audio \
  --master story_database/audio_drama/elevenlabs/generated/chapter_01_master.mp3
```

**Single-voice smoke test (read every line in one neutral voice; no per-role voice setup needed):**

```bash
python3 scripts/render_elevenlabs_chapter1.py \
  --input  story_database/audio_drama/elevenlabs/generated/chapter_01_dialogue_chunks.json \
  --single-voice <voice_uuid>
```

**Behaviour:**

| Flag | Meaning |
| --- | --- |
| `--dry-run` | Print chunk count, total characters, intended endpoints. No API calls. |
| `--chunks 0,2,5` or `--chunks 0-3` | Render a subset only. Other chunks are skipped (and excluded from stitch). |
| `--voice-map <path>` | Re-resolve `REPLACE_*` placeholders from voice_map.yaml at render time. |
| `--single-voice <uuid>` | Override every input with one voice for fast smoke listening. |
| `--seed <int>` | Pass a seed for reproducibility. |
| `--force` | Overwrite chunk_NN.mp3 files that already exist (default skips). |
| `--no-stitch` | Render chunks but skip the ffmpeg concat step. |
| `--endpoint <url>` | Override the default Text-to-Dialogue endpoint if ElevenLabs renames it. |

**Cost expectation:** The current screenplay-sourced chunks JSON is **4 chunks / ~6,100 characters total** (56 dialogue inputs). Text-to-Dialogue may be billed at a higher per-character rate than standard TTS depending on your plan; check your subscription's monthly character allowance before a full pass. Always run `--chunks 0` first and listen before spending the rest of the quota.

> Run `--dry-run` to confirm the live numbers before committing.

**Reference:** [Text-to-Dialogue convert](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert).

## 2. Projects (Studio long-form)

For **manual** chapter assembly in the browser:

1. Create a **Project**, pick **`eleven_v3`** (or the model Projects offers for multi-speaker blocks).
2. Use **one block per short beat** so regeneration stays cheap.
3. Use **Insert divider** inside a block when you need **narration + dialogue** in one paragraph (per ElevenLabs Projects help: multi-speaker within a paragraph).
4. Paste from `cp_01_screenplay.md`: keep **`BAM (V.O.)`** sections as **interior** (same voice as Bam or a second assigned voice per block).

Projects do **not** read `voice_map.yaml`; that file is for **API** and documentation parity.

## 3. Pronunciation

Use ElevenLabs **pronunciation dictionary** or inline respelling for odd terms (`Capian`, `Yorp`, `C-F-E-F` spelled out). Source prompts: `../pronunciation_registry.yaml`.

## 4. SSML

Classic SSML (`<break time="500ms"/>`) applies to **single-speaker TTS** flows. **Text-to-Dialogue** is driven by **plain text + v3 bracket tags** per current docs. Prefer **bracket tags** and **punctuation** for Dialogue; use **post** for precise ms pauses.
