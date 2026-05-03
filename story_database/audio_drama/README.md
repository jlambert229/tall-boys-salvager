# Audio drama production pack (Salvager)

YAML in this folder is **production-facing**: casting hints, sound design, pronunciation, and a **beat sound script** for Chapter 1 derived from `cp_01.md` and `cp_01_screenplay.md`.

It does **not** replace canon in `../characters.yaml` etc. It **extends** it for microphones and mixers.

| File | Contents |
| --- | --- |
| `voice_profiles.yaml` | Casting age, timbre, performance notes, mic technique. |
| `pronunciation_registry.yaml` | In-universe names, acronyms, fleet strings, actor-readable prompts. |
| `sound_palette_yorp.yaml` | Recurring ambiences and world tones you can reuse across episodes. |
| `chapter_01_audio_script.yaml` | Ordered blocks: ambients, SFX, foley, music hints, dialogue or V.O. cues. |
| `series_teaser_from_blurb.yaml` | Optional trailer beats from `content.md` (blurb_only until scripted). |
| `elevenlabs/` | **ElevenLabs:** `voice_map.yaml`, Studio/API README, exporter, generated `chapter_01_dialogue_chunks.json`. |

When Chapter 2 exists, add `chapter_02_audio_script.yaml` and link it in this README.
