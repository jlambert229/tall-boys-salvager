# Audio drama production pack (Salvager)

YAML in this folder is **production-facing**: casting hints, sound design, pronunciation, and a **beat sound script** for Chapter 1 derived from `cp_01.md` and `cp_01_screenplay.md`.

It does **not** replace canon in `../characters.yaml` etc. It **extends** it for microphones and mixers.

## Source of truth (read this once in production)

1. **Writer and actor-facing dialogue:** `../cp_01_screenplay.md` and `../cp_01.md` stay aligned with each other when you change lines.
2. **Sound and session planning:** `chapter_01_audio_script.yaml` extends the same beats with ambients, SFX, mix notes, and optional structure (e.g. `optional_insert_line`).
3. **ElevenLabs JSON:** Regenerate after any dialogue change using `scripts/export_elevenlabs_chapter1.py`. Default path is **`--screenplay`** (canonical for TTS until you deliberately switch).
4. **`--chapter-yaml`** exists to export from the beat script when it is **verified in sync** with the screenplay (requires `pip install -r scripts/requirements-export.txt`). If the two diverge, fix text before shipping.

## Runtime, ratings, and release

- **Target table-read length** for Chapter 1 is stated in `chapter_01_audio_script.yaml` under `production_targets.target_runtime_min` (soft band; trim in table read, not by guessing in mix).
- **Explicit language** is flagged there for feed tagging (e.g. Grams line in memory).
- **Marketing vs episode:** If the public blurb promises stakes not in Chapter 1 audio, ship the **teaser** from `series_teaser_from_blurb.yaml` in the same drop (see `production_targets.release_bundle` in the chapter YAML).

## Serialization (episodic feed)

Chapters ship as **ordered installments** with shared metadata:

1. **`serialization_series.yaml`** is the **episode registry**: `play_order` lists `episode_index`, `episode_code`, `script_file`, and manuscript paths. Add a row when a new chapter script exists. Do not reorder published episodes in a feed without updating this file and any `requires_chapters` in downstream YAML.
2. **Each `chapter_NN_audio_script.yaml`** carries a **`serialization`** block: `series_slug`, `episode_code`, `cold_open`, `ending_hook`, `feed_hints`, and `block_id_prefix` (beat ids use **`CH{N}-Axx`** so tooling and humans can sort dailies by chapter).
3. **New chapter:** duplicate **`chapter_TEMPLATE_audio_script.yaml`** to `chapter_02_audio_script.yaml` (etc.), fix chapter numbers and `CH2-*` ids, then append a matching row under `play_order` in `serialization_series.yaml`.
4. **Teaser:** `series_teaser_from_blurb.yaml` is optional between episodes or before 1x01; it references the same `series_slug`.

| File | Contents |
| --- | --- |
| `serialization_series.yaml` | **Serial registry:** play order, episode codes, script file names, teaser placement rules. |
| `chapter_TEMPLATE_audio_script.yaml` | Copy when starting a new chapter beat script; includes required `serialization` keys. |
| `voice_profiles.yaml` | **Persona bible:** essence, relationships, ch1 goals, mic notes; maps to YAML `speaker` keys and ElevenLabs `voice_map` keys. |
| `pronunciation_registry.yaml` | In-universe names, acronyms, fleet strings, actor-readable prompts. |
| `sound_palette_yorp.yaml` | Recurring ambiences and world tones you can reuse across episodes. |
| `chapter_01_audio_script.yaml` | Chapter 1 beats: ambients, SFX, foley, music hints, dialogue or V.O. cues. |
| `series_teaser_from_blurb.yaml` | Optional trailer beats from `content.md` (blurb_only until scripted). |
| `elevenlabs/` | **ElevenLabs:** `voice_map.yaml`, Studio/API README, exporter, generated `chapter_01_dialogue_chunks.json`. |

Add `chapter_02_audio_script.yaml` to the table (and to `serialization_series.yaml` `play_order`) when Chapter 2 manuscript exists.
