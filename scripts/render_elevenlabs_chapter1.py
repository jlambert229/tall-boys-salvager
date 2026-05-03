#!/usr/bin/env python3
"""
Render Salvager Chapter 1 dialogue chunks to MP3 via ElevenLabs Text-to-Dialogue.

Pipeline:
  1. Read chunks JSON produced by export_elevenlabs_chapter1.py.
  2. POST each chunk's `inputs` to ElevenLabs Text-to-Dialogue (eleven_v3).
  3. Save each chunk as chunk_NN.mp3 in --output-dir.
  4. ffmpeg concat all chunks into --master master.mp3 (skip with --no-stitch).

Auth: set ELEVENLABS_API_KEY in env (or pass --api-key-env <NAME>).

Cost note: Text-to-Dialogue is typically billed at a higher rate per character
than standard TTS. The full Chapter 1 is roughly 22-30k characters; a "Creator"
tier (100k chars/mo) is the realistic minimum. Use --dry-run and --chunks 0 to
sanity check voice picks before rendering the whole chapter.

Quick start:
  pip install -r scripts/requirements-export.txt
  export ELEVENLABS_API_KEY=sk_...
  python3 scripts/render_elevenlabs_chapter1.py \\
    --input  story_database/audio_drama/elevenlabs/generated/chapter_01_dialogue_chunks.json \\
    --output-dir story_database/audio_drama/elevenlabs/generated/audio \\
    --master story_database/audio_drama/elevenlabs/generated/chapter_01_master.mp3

Cheap voice sanity check (one chunk, no stitch):
  python3 scripts/render_elevenlabs_chapter1.py --input ... --chunks 0 --no-stitch

Re-resolve placeholder voice IDs from voice_map.yaml without rerunning exporter:
  python3 scripts/render_elevenlabs_chapter1.py --input ... \\
    --voice-map story_database/audio_drama/elevenlabs/voice_map.yaml

Single-voice "read the whole script in one neutral voice" smoke test:
  python3 scripts/render_elevenlabs_chapter1.py --input ... \\
    --single-voice <voice_uuid>

Endpoint reference:
  https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert
  If ElevenLabs renames the path, override with --endpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_ENDPOINT = "https://api.elevenlabs.io/v1/text-to-dialogue"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
PLACEHOLDER_PREFIX = "REPLACE"


def _load_requests():
    """Import requests lazily so --help and --dry-run work without it installed."""
    try:
        import requests  # noqa: WPS433 (intentional lazy import)
    except ImportError as exc:
        raise SystemExit(
            "The 'requests' package is required to call the ElevenLabs API.\n"
            "Install: pip install -r scripts/requirements-export.txt"
        ) from exc
    return requests


def load_voice_ids_from_map(voice_map_path: Path) -> dict[str, str]:
    """Minimal YAML subset reader matching the exporter's parser."""
    text = voice_map_path.read_text(encoding="utf-8")
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
    return voices


def reresolve_chunks(chunks: list[dict], voice_id_map: dict[str, str]) -> int:
    """Replace placeholder voice_id values in-place. Returns count replaced."""
    replaced = 0
    for ch in chunks:
        for inp in ch.get("inputs", []):
            vid = str(inp.get("voice_id", ""))
            if vid.startswith(PLACEHOLDER_PREFIX):
                vk = inp.get("voice_key", "")
                mapped = voice_id_map.get(vk, "")
                if mapped and not mapped.startswith(PLACEHOLDER_PREFIX):
                    inp["voice_id"] = mapped
                    replaced += 1
    return replaced


def override_single_voice(chunks: list[dict], voice_id: str) -> int:
    """Force every input to a single voice_id. Returns count overridden."""
    n = 0
    for ch in chunks:
        for inp in ch.get("inputs", []):
            inp["voice_id"] = voice_id
            n += 1
    return n


def find_placeholders(chunks: list[dict]) -> dict[str, int]:
    """Return {voice_key: count_of_placeholder_lines}."""
    bad: dict[str, int] = {}
    for ch in chunks:
        for inp in ch.get("inputs", []):
            if str(inp.get("voice_id", "")).startswith(PLACEHOLDER_PREFIX):
                vk = str(inp.get("voice_key", "?"))
                bad[vk] = bad.get(vk, 0) + 1
    return bad


def render_chunk(
    *,
    api_key: str,
    endpoint: str,
    chunk: dict,
    model_id: str,
    output_format: str,
    seed: int | None,
    timeout_sec: int,
) -> bytes:
    """POST one chunk to Text-to-Dialogue and return the audio bytes."""
    requests = _load_requests()

    body: dict = {
        "model_id": model_id,
        "inputs": [
            {"text": inp["text"], "voice_id": inp["voice_id"]}
            for inp in chunk["inputs"]
        ],
    }
    if seed is not None:
        body["seed"] = seed

    headers = {
        "xi-api-key": api_key,
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }
    params = {"output_format": output_format}

    resp = requests.post(
        endpoint,
        headers=headers,
        params=params,
        json=body,
        timeout=timeout_sec,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs API error {resp.status_code} on chunk "
            f"{chunk.get('chunk_index')}: {resp.text[:1000]}"
        )
    return resp.content


def stitch_chunks(chunk_paths: list[Path], master_path: Path) -> None:
    """ffmpeg concat all chunk mp3s into one master mp3 without re-encoding."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg not found. Install (apt install ffmpeg / brew install ffmpeg) "
            "or rerun with --no-stitch."
        )

    concat_list = master_path.with_suffix(".concat.txt")
    concat_list.parent.mkdir(parents=True, exist_ok=True)
    concat_list.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in chunk_paths) + "\n",
        encoding="utf-8",
    )

    cmd = [
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(master_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    concat_list.unlink(missing_ok=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{res.stderr[:1500]}")


def parse_chunk_subset(spec: str | None, total: int) -> list[int]:
    """Parse '0,2,5' or '0-3,7' or None (all) into a sorted unique index list."""
    if not spec:
        return list(range(total))
    out: set[int] = set()
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if "-" in tok:
            a, b = tok.split("-", 1)
            for i in range(int(a), int(b) + 1):
                out.add(i)
        else:
            out.add(int(tok))
    return sorted(i for i in out if 0 <= i < total)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True, help="chapter_01_dialogue_chunks.json")
    ap.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for chunk_NN.mp3 files (default: <input parent>/audio).",
    )
    ap.add_argument(
        "--master",
        type=Path,
        help="Stitched master mp3 path (default: <input parent>/chapter_01_master.mp3).",
    )
    ap.add_argument(
        "--voice-map",
        type=Path,
        help="Optional voice_map.yaml; replaces REPLACE_* placeholders in chunks at render time.",
    )
    ap.add_argument(
        "--single-voice",
        type=str,
        help="Override every input with this single voice_id (smoke-test reading).",
    )
    ap.add_argument(
        "--chunks",
        type=str,
        help="Render only these chunk indices (e.g. 0,2,5 or 0-3). Default: all.",
    )
    ap.add_argument(
        "--api-key-env",
        type=str,
        default="ELEVENLABS_API_KEY",
        help="Env var holding the ElevenLabs API key (default ELEVENLABS_API_KEY).",
    )
    ap.add_argument(
        "--endpoint",
        type=str,
        default=DEFAULT_ENDPOINT,
        help=f"Text-to-Dialogue endpoint (default {DEFAULT_ENDPOINT}).",
    )
    ap.add_argument("--model-id", type=str, default=None, help="Override model_id from chunks JSON.")
    ap.add_argument(
        "--output-format",
        type=str,
        default=DEFAULT_OUTPUT_FORMAT,
        help=f"ElevenLabs output_format (default {DEFAULT_OUTPUT_FORMAT}).",
    )
    ap.add_argument("--seed", type=int, help="Optional seed for reproducibility.")
    ap.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Per-request timeout in seconds (default 180).",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing chunk_NN.mp3 files (default: skip).",
    )
    ap.add_argument(
        "--no-stitch",
        action="store_true",
        help="Skip ffmpeg concat after render.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan and total characters; do not call API.",
    )
    args = ap.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    chunks = payload.get("chunks") or []
    if not chunks:
        print("No chunks in input JSON.", file=sys.stderr)
        return 1
    model_id = args.model_id or payload.get("model_id") or "eleven_v3"

    if args.voice_map:
        if not args.voice_map.exists():
            print(f"Voice map not found: {args.voice_map}", file=sys.stderr)
            return 1
        voice_id_map = load_voice_ids_from_map(args.voice_map)
        n = reresolve_chunks(chunks, voice_id_map)
        print(f"Re-resolved {n} placeholder voice_id(s) from {args.voice_map.name}")

    if args.single_voice:
        n = override_single_voice(chunks, args.single_voice)
        print(f"Single-voice override: forced {n} input(s) to voice_id={args.single_voice}")

    placeholders = find_placeholders(chunks)
    if placeholders:
        print("Voice IDs in chunks JSON still contain placeholders:", file=sys.stderr)
        for vk, n in sorted(placeholders.items()):
            print(f"  - {vk}: {n} line(s)", file=sys.stderr)
        print(
            "\nFix one of:\n"
            "  1. Edit voice_map.yaml with real voice_ids (ElevenLabs Voice Library / Voice Lab > copy ID)\n"
            "     and rerun scripts/export_elevenlabs_chapter1.py to regenerate chunks.\n"
            "  2. Or rerun this script with --voice-map <path/to/voice_map.yaml>.\n"
            "  3. Or rerun this script with --single-voice <voice_uuid> for a smoke test.",
            file=sys.stderr,
        )
        return 1

    output_dir = args.output_dir or args.input.parent / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)
    master_path = args.master or args.input.parent / "chapter_01_master.mp3"

    indices = parse_chunk_subset(args.chunks, len(chunks))
    selected = [chunks[i] for i in indices]
    chars_selected = sum(int(ch.get("char_total", 0)) for ch in selected)
    chars_all = sum(int(ch.get("char_total", 0)) for ch in chunks)

    print(f"Source: {args.input}")
    print(f"Chunks total in file: {len(chunks)} ({chars_all} chars)")
    print(f"Chunks to render now: {len(selected)} ({chars_selected} chars)")
    print(f"Model: {model_id}    output_format: {args.output_format}")
    print(f"Endpoint: {args.endpoint}")
    print(f"Output dir: {output_dir}")
    if not args.no_stitch:
        print(f"Master:     {master_path}")

    if args.dry_run:
        print("\n[dry-run] no API calls made. Done.")
        return 0

    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        print(
            f"\nMissing API key. Set: export {args.api_key_env}=sk_...\n"
            "Get one at https://elevenlabs.io/app/settings/api-keys",
            file=sys.stderr,
        )
        return 1

    chunk_paths_in_order: list[Path] = []
    started = time.time()
    for i, ch in enumerate(chunks):
        idx = ch.get("chunk_index", i)
        out_path = output_dir / f"chunk_{int(idx):02d}.mp3"
        chunk_paths_in_order.append(out_path)

        if i not in indices:
            tag = "file present" if out_path.exists() else "no file yet"
            print(f"  chunk {idx:02d}: skipped (not in subset, {tag})")
            continue

        if out_path.exists() and not args.force:
            print(f"  chunk {idx:02d}: already rendered ({out_path.name}); use --force to redo")
            continue

        n_lines = len(ch.get("inputs", []))
        n_chars = ch.get("char_total", 0)
        print(f"  chunk {idx:02d}: rendering {n_lines} line(s), {n_chars} chars ...", flush=True)

        t0 = time.time()
        try:
            audio_bytes = render_chunk(
                api_key=api_key,
                endpoint=args.endpoint,
                chunk=ch,
                model_id=model_id,
                output_format=args.output_format,
                seed=args.seed,
                timeout_sec=args.timeout,
            )
        except Exception as e:
            print(f"  chunk {idx:02d}: FAILED -> {e}", file=sys.stderr)
            return 2

        out_path.write_bytes(audio_bytes)
        print(
            f"  chunk {idx:02d}: wrote {out_path.name} "
            f"({len(audio_bytes):,} bytes, {time.time() - t0:.1f}s)"
        )

    if not args.no_stitch:
        missing = [p for p in chunk_paths_in_order if not p.exists()]
        if missing:
            print(
                "\nNot all chunks present; cannot stitch. Render the missing ones "
                "or use --no-stitch.",
                file=sys.stderr,
            )
            for p in missing:
                print(f"  missing: {p.name}", file=sys.stderr)
            return 3
        print(f"\nStitching {len(chunk_paths_in_order)} chunk(s) -> {master_path}")
        try:
            stitch_chunks(chunk_paths_in_order, master_path)
        except Exception as e:
            print(f"Stitch failed: {e}", file=sys.stderr)
            return 4
        size = master_path.stat().st_size
        print(f"Master: {master_path} ({size:,} bytes)")

    print(f"\nTotal time: {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
