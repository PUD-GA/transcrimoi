#!/usr/bin/env python3
"""Essai réel du corpus synthétique local, distinct des doubles de test."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
import sys
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.paths import FIXTURES, RUNS
from transcrimoi.backend import Backend
from transcrimoi.job import Job
from transcrimoi.srt import parse_srt
from transcrimoi.storage import read_json, sha256_file, write_json


def tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    return re.findall(r"[^\W_]+(?:'[^\W_]+)?", text, flags=re.UNICODE)


def word_errors(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for i, expected in enumerate(reference, 1):
        current = [i]
        for j, actual in enumerate(hypothesis, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (expected != actual)))
        previous = current
    return previous[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=RUNS / "synth")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--case", action="append", help="Nom sans extension, répétable ; tous par défaut")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    backend = Backend.verified(ROOT)
    manifest = read_json(FIXTURES / "corpus_manifest.json")
    report = {
        "schema_version": 1, "date_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "native_commit": backend.provenance["build"]["native_commit"],
        "backend": "cpu", "threads_asr": args.threads,
        "reference": "SRT synthétiques fournis, pas des annotations humaines de validation WER/DER",
        "normalization": "NFKC, casefold, apostrophe typographique unifiée ; tokens alphanumériques avec apostrophe interne ; ponctuation ignorée, chiffres non développés",
        "cases": [],
    }
    for pair in manifest["pairs"]:
        name = Path(pair["audio"]).stem
        if args.case and name not in args.case:
            continue
        source = ROOT / pair["audio"]
        if sha256_file(source) != pair["audio_sha256"]:
            raise ValueError(f"Corpus modifié : {source}")
        output = args.output_dir / "srt" / (name + ".srt")
        work = args.output_dir / "work" / name
        def event(value: dict):
            print(json.dumps({"case": name, **value}, ensure_ascii=False), flush=True)
        start = time.monotonic()
        result = Job(backend, threads=args.threads, event=event).run(source, output, work, overwrite=args.overwrite)
        elapsed = time.monotonic() - start
        reference_cues = parse_srt((ROOT / pair["srt"]).read_text(encoding="utf-8-sig"))
        reference_words = tokens(" ".join(c.text for c in reference_cues))
        raw = read_json(work / "asr.json")
        hypothesis_words = tokens(" ".join(cue["text"] for cue in result["cues"]))
        errors = word_errors(reference_words, hypothesis_words)
        raw_errors = word_errors(reference_words, tokens(raw["text"]))
        state = read_json(work / "state.json")
        item = {
            "name": name, "output": str(output.resolve()), "duration_seconds": result["duration"],
            "wall_seconds_this_run": round(elapsed, 3), "real_time_factor_this_run": round(elapsed / result["duration"], 4),
            "phase_seconds_original": {key: value.get("seconds") for key, value in state["completed"].items()},
            "reference_blocks": pair["blocks"], "generated_blocks": len(result["cues"]),
            "reference_speakers": len(pair["speakers"]), "observed_speaker_slots": result["speakers_observed"],
            "unknown_words": result["unknown_words"], "asr_words": len(result["words"]),
            "native_word_count": result["native_word_count"], "omitted_token_count": result["omitted_token_count"],
            "word_errors_against_supplied_srt": errors, "reference_word_count": len(reference_words),
            "wer_against_supplied_srt": errors / len(reference_words) if reference_words else None,
            "wer_source": "Texte des blocs SRT générés, préfixes Speaker exclus",
            "raw_asr_wer_against_supplied_srt": raw_errors / len(reference_words) if reference_words else None,
            "native_unknown_tokens": sum(item["w"].strip() == "<unk>" for item in raw["words"]),
            "generated_srt_sha256": sha256_file(output),
        }
        report["cases"].append(item)
        write_json(args.output_dir / "report.json", report)
    if not report["cases"]:
        parser.error("Aucun cas sélectionné")


if __name__ == "__main__":
    main()
