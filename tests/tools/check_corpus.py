#!/usr/bin/env python3
"""Vérifie le corpus fourni ; fige son inventaire uniquement sur demande."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.paths import FIXTURES, SYNTH
from transcrimoi.srt import parse_srt, render_srt
from transcrimoi.storage import read_json, sha256_file, write_json


def inventory() -> dict:
    srts = sorted((SYNTH / "srt").glob("*.srt"))
    if not srts:
        raise FileNotFoundError(f"Corpus synthétique local absent ou vide : {SYNTH}")
    pairs = []
    for srt in srts:
        audio = SYNTH / "audio" / (srt.stem + ".mp3")
        duration = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(audio)], text=True))
        cues = parse_srt(srt.read_text(encoding="utf-8-sig"))
        assert parse_srt(render_srt(cues)) == cues, f"Aller-retour incorrect : {srt}"
        assert all(c.end <= duration for c in cues), f"Temps hors média : {srt}"
        pairs.append({
            "srt": srt.relative_to(ROOT).as_posix(), "srt_sha256": sha256_file(srt),
            "audio": audio.relative_to(ROOT).as_posix(), "audio_sha256": sha256_file(audio),
            "duration_seconds": duration, "blocks": len(cues),
            "speakers": sorted({c.speaker for c in cues if c.speaker is not None}),
            "unattributed_blocks": sum(c.speaker is None for c in cues),
            "first_start": cues[0].start, "last_end": cues[-1].end,
            "overlapping_adjacent_blocks": sum(b.start < a.end for a, b in zip(cues, cues[1:])),
        })
    return {"schema_version": 1, "authority": "Corpus fourni par l'utilisateur comme entrée valide de SonalPi2", "pairs": pairs}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-manifest", action="store_true", help="Figer explicitement la référence, ne pas utiliser en CI")
    args = parser.parse_args()
    value = inventory()
    path = FIXTURES / "corpus_manifest.json"
    if args.write_manifest:
        write_json(path, value)
    elif value != read_json(path):
        raise SystemExit("Corpus différent du manifeste de référence")
    for pair in value["pairs"]:
        print(f"{Path(pair['srt']).name}: {pair['blocks']} blocs, locuteurs {pair['speakers']}, {pair['duration_seconds']:.2f} s")


if __name__ == "__main__":
    main()
