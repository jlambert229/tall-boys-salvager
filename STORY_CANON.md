# Salvager story canon (index)

This folder tracks **Salvager** inside the **Tall Boys** universe. **Structured canon** lives under `story_database/` as split YAML files. **`merge_manifest.yaml`** lists load order if you merge keys in tooling.

## Files

| Path | Purpose |
| --- | --- |
| `content.md` | Series-facing blurb (may describe events not yet in manuscript chapters). |
| `cp_01.md` | Chapter 1 prose. |
| `cp_01_screenplay.md` | Chapter 1 script draft (derivative of prose). |
| `story_database/meta.yaml` | Universe metadata and `sources` registry. |
| `story_database/*.yaml` | Canon slices: characters, factions, locations, tech, themes, hooks, etc. |
| `story_database/merge_manifest.yaml` | Merge order for flat JSON or LLM context exports. |
| `story_database/audio_drama/` | **Audio drama pack:** voice sheets, pronunciation, sound palette, Chapter 1 sound script, blurb teaser notes. |
| `STORY_CANON.md` | This index and editing conventions. |

The old single file **`story_database.yaml`** at the `salvager/` root (if still present) is obsolete; use `story_database/` only.

## How to extend the database

1. Edit the **smallest** slice file (for example `characters.yaml`) when the manuscript **states or clearly implies** a fact.
2. Every entity should include `sources` listing one or more of: `cp_01`, `cp_01_screenplay`, `blurb`. Prefer `cp_01` over the screenplay when both exist.
3. Use **`plot_hooks.yaml`** for anything that appears **only** in `content.md` until a chapter confirms it.
4. Prefer stable **`id`** keys (snake_case) so later chapters can reference the same record.
5. When a detail **changes** in a later draft, add `revision_notes` rather than silently deleting history (recommended).

## Audio drama workflow

1. Read `story_database/audio_drama/README.md`.
2. Cast from `voice_profiles.yaml`; lock pronunciations from `pronunciation_registry.yaml`.
3. Build the episode from `chapter_01_audio_script.yaml` (blocks are ordered; `duration_hint_sec` is cumulative rough planning time, not locked).
4. Design beds and stems using `sound_palette_yorp.yaml`.
5. Optional marketing trailer: `series_teaser_from_blurb.yaml` (still **blurb_only** until scripted).

## Quick counts (database v1)

**Receipt:** Generated from `salvager/cp_01.md`, `salvager/content.md`; screenplay omitted as duplicate for counting.

- **Characters (named or specific):** Bam, Sketch, Uncle Iton, Grams, Tommy, Samantha, Suzzie Keener (mentioned).
- **Factions / threat types:** Yorpers, C-FEF, UPV, ROV6, gang bosses.
- **Locations:** Yorp, Vaux VI (historical), alley base, gutted train station, beyond-city ranch rumor.
- **Plot hooks (blurb only):** empire pilot, trust vs betrayal, Sketch scrutiny, escalation.

## Validation

Slice YAML under `story_database/` should parse with PyYAML or Ruby YAML. The audio script uses long folded strings (`>-`) in a few blocks; keep indentation valid if you edit those lines.
