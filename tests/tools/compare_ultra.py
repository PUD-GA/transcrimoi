#!/usr/bin/env python3
"""Essai croisé v3/Ultra F16 × padding, sans changer le backend de production."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import sys
import time
import wave

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.paths import EXPERIMENT_MODELS, EXPERIMENTS, RUNS
from transcrimoi.backend import Backend
from transcrimoi.process import run_process
from transcrimoi.schema import parse_asr
from transcrimoi.storage import atomic_text, read_json, sha256_file, write_json


def extract_wave(source: Path, output: Path, start: float, end: float, padding_ms: int) -> float:
    """Même PCM pour les deux modèles ; zéros ajoutés sans couper l'extrait."""
    if not all(isinstance(t, (int, float)) and not isinstance(t, bool) and math.isfinite(t) for t in (start, end)):
        raise ValueError("Bornes finies attendues")
    if type(padding_ms) is not int or padding_ms < 0:
        raise ValueError("Padding entier positif ou nul attendu")
    with wave.open(str(source), "rb") as audio:
        if (audio.getnchannels(), audio.getframerate(), audio.getsampwidth()) != (1, 16000, 2):
            raise ValueError("WAV PCM 16 bits mono 16 kHz attendu")
        if not 0 <= start < end <= audio.getnframes() / 16000:
            raise ValueError("Coupe hors média ou vide")
        first, last = round(start * 16000), round(end * 16000)
        if first == last:
            raise ValueError("Coupe vide après arrondi aux échantillons")
        audio.setpos(first)
        pcm = audio.readframes(last - first)
        if len(pcm) != (last - first) * 2:
            raise ValueError("Audio tronqué")
    pad = b"\0\0" * (padding_ms * 16)
    with output.open("xb") as stream, wave.open(stream, "wb") as dest:
        dest.setnchannels(1)
        dest.setsampwidth(2)
        dest.setframerate(16000)
        dest.writeframes(pad + pcm + pad)
    return (last - first + padding_ms * 32) / 16000


def markdown(report: dict) -> str:
    lines = ["# Comparaison Parakeet v3 / Ultra F16", "",
             "Essai réel sur les mêmes échantillons audio. Aucun LLM, dictionnaire ou forçage de langue.",
             "Le padding indiqué est ajouté de chaque côté. Les temps natifs incluent le chargement du modèle.",
             "Une seule exécution par condition, sans référence humaine : pas de WER ni de qualification globale.", "",
             "| Coupe | Début source (s) | Modèle | Padding (ms) | Temps (s) | Mots natifs | Texte plat natif |",
             "|---|---:|---|---:|---:|---:|---|"]
    for item in report["results"]:
        text = item["text"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {item['cut_index']} | {item['start']} | {item['model']} | {item['padding_ms_each_side']} | "
                     f"{item['seconds']} | {item['word_count']} | {text} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=EXPERIMENTS / "ultra-f16.lock.json")
    parser.add_argument("--output-dir", type=Path, default=RUNS / "wamatipsia/diagnostic-ultra")
    parser.add_argument("--download-model", action="store_true", help="Télécharger v3 et Ultra F16 s'ils sont absents (~2,88 Go)")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        parser.error("Le dossier de sortie existe déjà ; choisir un nouveau --output-dir")
    config = read_json(args.config)
    backend = Backend.verified(ROOT)
    if backend.provenance["build"]["native_commit"] != config["native_commit"]:
        raise ValueError("Commit natif différent de celui de l'expérience")
    if args.download_model:
        from scripts.prepare_backend import download
        download(config["baseline_model"], config["model_repository"], config["model_revision"],
                 directory=EXPERIMENT_MODELS)
        download(config["model"], config["model_repository"], config["model_revision"])
    baseline = EXPERIMENT_MODELS / config["baseline_model"]["file"]
    if (baseline.stat().st_size != config["baseline_model"]["size"]
            or sha256_file(baseline) != config["baseline_model"]["sha256"]):
        raise ValueError("Modèle témoin v3 absent ou corrompu")
    ultra = ROOT / "models" / config["model"]["file"]
    if ultra.stat().st_size != config["model"]["size"] or sha256_file(ultra) != config["model"]["sha256"]:
        raise ValueError("Ultra absent ou corrompu")
    source, cuts_path = ROOT / config["source"], ROOT / config["cuts"]
    if sha256_file(source) != config["source_sha256"]:
        raise ValueError("Audio source différent de celui de l'expérience")
    cuts = read_json(cuts_path)["segments"]
    output_dir.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "status": "running", "date_utc": datetime.now(timezone.utc).isoformat(),
              "platform": platform.platform(), "experiment": config, "backend": backend.provenance,
              "cuts_sha256": sha256_file(cuts_path), "results": []}
    write_json(output_dir / "report.json", report)
    try:
        for index in config["cut_indices"]:
            cut = cuts[index]
            for padding_ms in config["padding_ms_each_side"]:
                audio = output_dir / f"cut-{index}-pad-{padding_ms}.wav"
                duration = extract_wave(source, audio, cut["start"], cut["end"], padding_ms)
                audio_hash = sha256_file(audio)
                for name, model in (("v3-f16", baseline), ("ultra-f16", ultra)):
                    prefix = f"cut-{index}-pad-{padding_ms}-{name}"
                    result_file = output_dir / (prefix + ".json")
                    # Les coupes sont déjà fixées : surtout pas de deuxième VAD.
                    command = [str(backend.cli), "transcribe", "--model", str(model), "--input", str(audio),
                               "--decoder", "tdt", "--json", "--threads", str(config["threads"])]
                    print(json.dumps({"cut_index": index, "padding_ms": padding_ms, "model": name, "status": "started"}), flush=True)
                    start = time.monotonic()
                    run_process(command, result_file, output_dir / (prefix + ".log"))
                    seconds = round(time.monotonic() - start, 3)
                    raw = read_json(result_file)
                    words = parse_asr(raw, duration)
                    item = {"cut_index": index, "start": cut["start"], "end": cut["end"],
                            "model": name, "padding_ms_each_side": padding_ms,
                            "audio_sha256": audio_hash, "duration_with_padding": duration,
                            "seconds": seconds, "word_count": len(words), "text": raw["text"],
                            "command": command, "native_output_sha256": sha256_file(result_file)}
                    report["results"].append(item)
                    write_json(output_dir / "report.json", report)
                    print(json.dumps({**item, "command": None, "status": "completed"}, ensure_ascii=False), flush=True)
        report["status"] = "completed"
        write_json(output_dir / "report.json", report)
        atomic_text(output_dir / "comparison.md", markdown(report), overwrite=False)
    except BaseException as error:
        report.update(status="failed", error=str(error))
        write_json(output_dir / "report.json", report)
        raise


if __name__ == "__main__":
    main()
