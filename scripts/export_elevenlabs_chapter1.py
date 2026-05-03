#!/usr/bin/env python3
"""
Export Salvager Chapter 1 dialogue to ElevenLabs Text-to-Dialogue sized chunks.

Docs: eleven_v3 only; sum of inputs[].text <= 2000 chars per request.
Outputs JSON: { "model_id", "chunks": [ { "chunk_index", "char_total", "inputs": [ ... ] } ] }

Sources (pick one):
  --screenplay   cp_01_screenplay.md (SKETCH|BAM|ITON|TOMMY|SAMANTHA blocks).
  --chapter-yaml chapter_01_audio_script.yaml (requires PyYAML: pip install -r requirements-export.txt).

Usage (screenplay):
  python3 export_elevenlabs_chapter1.py --screenplay ../cp_01_screenplay.md \\
    --voice-map ../story_database/audio_drama/elevenlabs/voice_map.yaml \\
    --out ../story_database/audio_drama/elevenlabs/generated/chapter_01_dialogue_chunks.json

Usage (YAML, after sync check):
  python3 export_elevenlabs_chapter1.py --chapter-yaml ../story_database/audio_drama/chapter_01_audio_script.yaml \\
    --voice-map ../story_database/audio_drama/elevenlabs/voice_map.yaml \\
    --out ../story_database/audio_drama/elevenlabs/generated/chapter_01_dialogue_chunks.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore


SPEAKER_LINE = re.compile(
    r"^(?P<name>SKETCH|BAM|ITON|TOMMY|SAMANTHA)(?P<vo>\s+\(V\.O\.\))?\s*$"
)


def load_voice_ids(voice_map_path: Path) -> tuple[dict[str, str], str]:
    """Minimal YAML subset: voices: / bam: / elevenlabs_voice_id: value."""
    text = voice_map_path.read_text(encoding="utf-8")
    model_id = "eleven_v3"
    m_model = re.search(r"^\s*model_id:\s*(\S+)\s*$", text, re.MULTILINE)
    if m_model:
        model_id = m_model.group(1).strip().strip('"').strip("'")

    voices: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        vm = re.match(r"^  (?P<key>[a-z0-9_]+):\s*$", line)
        if vm:
            current = vm.group("key")
            continue
        if current:
            im = re.match(r"^\s+elevenlabs_voice_id:\s*(.+?)\s*$", line)
            if im:
                val = im.group(1).strip().strip('"').strip("'")
                voices[current] = val
    return voices, model_id


def screenplay_to_segments(screenplay: str) -> list[dict[str, str]]:
    """Return ordered {voice_key, text} from speaker blocks only (skips action)."""
    segments: list[dict[str, str]] = []
    paragraphs = re.split(r"\n\s*\n", screenplay)
    for para in paragraphs:
        lines = [ln.rstrip() for ln in para.strip().splitlines() if ln.strip() != ""]
        if not lines:
            continue
        head = lines[0].strip()
        m = SPEAKER_LINE.match(head)
        if not m:
            continue
        name = m.group("name")
        is_vo = m.group("vo") is not None
        body_lines = lines[1:]
        if not body_lines:
            continue
        text = " ".join(x.strip() for x in body_lines if x.strip())
        if not text:
            continue
        vk = _screenplay_name_to_voice_key(name, is_vo)
        if vk:
            segments.append({"voice_key": vk, "text": text})
    return segments


def _screenplay_name_to_voice_key(name: str, is_vo: bool) -> str | None:
    if name == "SKETCH":
        return "sketch"
    if name == "ITON":
        return "uncle_iton"
    if name == "TOMMY":
        return "tommy"
    if name == "SAMANTHA":
        return "samantha"
    if name == "BAM":
        return "bam_interior" if is_vo else "bam"
    return None


def _normalize_block_text(text: object) -> str:
    if not isinstance(text, str):
        return ""
    return " ".join(text.split())


def _yaml_line_to_voice_key(speaker: str, line_type: str | None) -> str | None:
    sp = (speaker or "").strip().lower()
    lt = (line_type or "dialogue").strip().lower()
    if sp == "bameron_kold":
        return "bam"
    if sp == "sketch":
        return "sketch"
    if sp == "uncle_iton":
        return "uncle_iton"
    if sp == "tommy":
        return "tommy"
    if sp == "samantha":
        return "samantha"
    if sp == "grams":
        return "bam_interior"
    if sp == "crowd_chorus":
        return "uncle_iton"
    if lt == "stage_business" and sp == "uncle_iton":
        return "uncle_iton"
    return None


def chapter_yaml_to_segments(
    data: dict, *, include_optional_grams: bool
) -> list[dict[str, str]]:
    """Flatten chapter blocks: each block's `lines` in order, then `vo_over` in order."""
    segments: list[dict[str, str]] = []
    blocks = data.get("blocks")
    if not isinstance(blocks, list):
        return segments

    for block in blocks:
        if not isinstance(block, dict):
            continue

        for item in block.get("lines") or []:
            if not isinstance(item, dict):
                continue
            speaker = str(item.get("speaker", ""))
            line_type = item.get("type")
            text = _normalize_block_text(item.get("text"))
            if not text:
                continue
            vk = _yaml_line_to_voice_key(speaker, str(line_type) if line_type else None)
            if not vk:
                continue
            segments.append({"voice_key": vk, "text": text})

        for item in block.get("vo_over") or []:
            if not isinstance(item, dict):
                continue
            speaker = str(item.get("speaker", ""))
            text = _normalize_block_text(item.get("text"))
            if not text:
                continue
            if speaker.lower() == "bameron_kold":
                segments.append({"voice_key": "bam_interior", "text": text})

        opt = block.get("optional_insert_line")
        if include_optional_grams and isinstance(opt, dict):
            sp = str(opt.get("speaker", "")).lower()
            text = _normalize_block_text(opt.get("text"))
            if sp == "grams" and text:
                segments.append({"voice_key": "bam_interior", "text": f"[as Grams] {text}"})

    return segments


def pack_chunks(
    segments: list[dict[str, str]], max_chars: int
) -> list[list[dict[str, str]]]:
    chunks: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] = []
    total = 0
    for seg in segments:
        t = seg["text"]
        overhead = 2 if current else 0
        if total + overhead + len(t) > max_chars and current:
            chunks.append(current)
            current = []
            total = 0
        current.append({"voice_key": seg["voice_key"], "text": t})
        total += overhead + len(t)
    if current:
        chunks.append(current)
    return chunks


def main() -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--screenplay", type=Path, help="Fountain-style screenplay with SKETCH|BAM|ITON|TOMMY|SAMANTHA headers.")
    src.add_argument(
        "--chapter-yaml",
        type=Path,
        help="chapter_01_audio_script.yaml (needs: pip install -r scripts/requirements-export.txt).",
    )
    ap.add_argument("--voice-map", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--max-chars",
        type=int,
        default=1950,
        help="Stay under ElevenLabs 2000-char dialogue request limit (default 1950 margin).",
    )
    ap.add_argument(
        "--voice-keys-only",
        action="store_true",
        help="Emit voice_key instead of voice_id (skip voice map resolution).",
    )
    ap.add_argument(
        "--include-grams-insert",
        action="store_true",
        help="With --chapter-yaml: include optional_insert_line blocks (e.g. Grams) as bam_interior.",
    )
    args = ap.parse_args()

    if args.screenplay:
        raw = args.screenplay.read_text(encoding="utf-8")
        segments = screenplay_to_segments(raw)
        source_label = str(args.screenplay)
    else:
        if yaml is None:
            print(
                "PyYAML is required for --chapter-yaml. Install: pip install -r scripts/requirements-export.txt",
                file=sys.stderr,
            )
            return 1
        raw_yaml = yaml.safe_load(args.chapter_yaml.read_text(encoding="utf-8"))
        if not isinstance(raw_yaml, dict):
            print("chapter YAML root must be a mapping.", file=sys.stderr)
            return 1
        segments = chapter_yaml_to_segments(
            raw_yaml, include_optional_grams=args.include_grams_insert
        )
        source_label = str(args.chapter_yaml)

    if not segments:
        print("No speaker segments parsed. Check source format.", file=sys.stderr)
        return 1

    voice_ids, model_id = load_voice_ids(args.voice_map)
    missing = [k for k, v in voice_ids.items() if v.startswith("REPLACE")]
    if missing and not args.voice_keys_only:
        print(
            "Warning: voice_map still has placeholders for: "
            + ", ".join(missing)
            + " (output will include voice_id fields with REPLACE strings).",
            file=sys.stderr,
        )

    chunks_raw = pack_chunks(segments, args.max_chars)
    out_chunks = []
    for i, ch in enumerate(chunks_raw):
        inputs = []
        char_total = 0
        for item in ch:
            vk = item["voice_key"]
            txt = item["text"]
            char_total += len(txt)
            if args.voice_keys_only:
                inputs.append({"voice_key": vk, "text": txt})
            else:
                vid = voice_ids.get(vk, "")
                inputs.append({"voice_id": vid, "voice_key": vk, "text": txt})
        out_chunks.append(
            {
                "chunk_index": i,
                "char_total": char_total,
                "inputs": inputs,
            }
        )

    payload = {
        "title": "Salvager Chapter 1",
        "model_id": model_id,
        "max_chars_per_request_doc": 2000,
        "export_max_chars_used": args.max_chars,
        "source": source_label,
        "chunks": out_chunks,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(out_chunks)} chunk(s), {len(segments)} segment(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
