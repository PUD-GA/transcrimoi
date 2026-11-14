#!/usr/bin/env python3
"""Comparaison réelle Ultra F16 / Fluid Q8, sans modifier le backend du produit."""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import platform
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.paths import EXPERIMENT_MODELS, EXPERIMENTS, FIXTURES
from tests.tools.compare_ultra import extract_wave
from tests.tools.run_corpus import tokens, word_errors
from transcrimoi import __version__
from transcrimoi.assignment import OMITTED_ASR_TOKENS
from transcrimoi.backend import Backend
from transcrimoi.job import Job
from transcrimoi.model_verification import verify_model
from transcrimoi.process import run_process
from transcrimoi.srt import parse_srt
from transcrimoi.storage import atomic_text, read_json, sha256_file, write_json


class MeasuredBackend:
    """Mesure le RSS maximal de l'ASR seul avec GNU time sous Linux, sinon null."""
    def __init__(self, backend: Backend, rss_path: Path):
        self.backend = backend
        self.provenance = backend.provenance
        self.rss_path = rss_path
        self.measure = platform.system() == "Linux" and Path("/usr/bin/time").is_file()

    def asr_command(self, audio: Path, threads: int) -> list[str]:
        command = self.backend.asr_command(audio, threads)
        if self.measure:
            return ["/usr/bin/time", "-f", "%M", "-o", str(self.rss_path), *command]
        return command

    def diarization_command(self, audio: Path) -> list[str]:
        return self.backend.diarization_command(audio)


def score(reference: str, hypothesis: str) -> dict:
    expected = tokens(reference)
    errors = word_errors(expected, tokens(hypothesis))
    return {"errors": errors, "reference_words": len(expected),
            "wer": errors / len(expected) if expected else None}


def summarize(results: list[dict]) -> dict:
    summary = {}
    for model in ("ultra-f16", "fluid-q8"):
        corpus = [item for item in results if item["suite"] == "corpus" and item["model"] == model]
        count = sum(item["srt_score"]["reference_words"] for item in corpus)
        errors = sum(item["srt_score"]["errors"] for item in corpus)
        raw_errors = sum(item["raw_score"]["errors"] for item in corpus)
        summary[model] = {"corpus_cases": len(corpus), "reference_words": count,
                          "srt_errors": errors, "srt_wer": errors / count if count else None,
                          "raw_wer": raw_errors / count if count else None,
                          "asr_seconds": round(sum(item["asr_seconds"] for item in corpus), 3),
                          "asr_peak_rss_kib": max((item["asr_peak_rss_kib"] for item in corpus
                                                   if item["asr_peak_rss_kib"] is not None), default=None)}
    return summary


def markdown(report: dict) -> str:
    lines = ["# Comparaison Ultra F16 / Fluid Speech Pro Q8_0", "",
             "Même pipeline CPU, Silero, Nemotron, attribution et segmentation. Aucun clean mode.",
             "Une exécution par condition ; modèles ET précisions différents, pas un benchmark statistique.",
             "WER contre les SRT synthétiques fournis, pas une référence humaine indépendante.",
             "RSS : pic du processus ASR seul (GNU time/Linux), pas la mémoire totale de l'application.",
             "Horodatages validés structurellement ; leur justesse n'est pas mesurée.", "",
             "| Cas | Modèle | ASR (s) | Pic ASR (Mio) | Blocs | WER SRT (%) | WER brut (%) |",
             "|---|---|---:|---:|---:|---:|---:|"]
    def percent(value):
        return f"{value * 100:.2f}" if value is not None else "—"
    for item in report["results"]:
        rss = item["asr_peak_rss_kib"]
        memory = f"{rss / 1024:.1f}" if rss is not None else "—"
        lines.append(f"| {item['case']} | {item['model']} | {item['asr_seconds']} | {memory} | "
                     f"{item['cues']} | {percent(item['srt_score']['wer'])} | {percent(item['raw_score']['wer'])} |")
    for item in report["results"]:
        if item["suite"] == "wamatipsia":
            lines += ["", f"## {item['case']} — {item['model']}", "",
                      item["text"].replace("|", "\\|").replace("\n", " ")]
    return "\n".join(lines) + "\n"


def run_case(backend: Backend, source: Path, directory: Path, *, suite: str, name: str,
             label: str, threads: int, reference: str | None = None) -> dict:
    measured = MeasuredBackend(backend, directory / "asr-rss-kib.txt")
    def event(value):
        print(f"{suite}/{name}/{label}: {value['phase']} {value['status']}", flush=True)
    start = time.monotonic()
    result = Job(measured, threads=threads, event=event).run(
        source, directory / "result.srt", directory / "work")
    elapsed = time.monotonic() - start
    state = read_json(directory / "work/state.json")
    raw = read_json(directory / "work/asr.json")
    srt = " ".join(cue["text"] for cue in result["cues"])
    item = {"suite": suite, "case": name, "model": label,
            "source_sha256": sha256_file(source), "duration": result["duration"],
            "seconds": round(elapsed, 3), "asr_seconds": state["completed"]["asr"]["seconds"],
            "asr_peak_rss_kib": int(measured.rss_path.read_text().strip()) if measured.measure else None,
            "timestamps_structurally_valid": True, "word_count": len(result["words"]),
            "cues": len(result["cues"]), "unknown_words": result["unknown_words"],
            "native_word_count": result["native_word_count"], "omitted_token_count": result["omitted_token_count"],
            "context_words": sum(w["reason"].startswith("context_") for w in result["words"]),
            "text": raw["text"], "output_sha256": sha256_file(directory / "result.srt"),
            "srt_score": score(reference, srt) if reference is not None else {"wer": None},
            "raw_score": score(reference, raw["text"]) if reference is not None else {"wer": None}}
    if not result["words"] or not result["cues"]:
        raise ValueError(f"Aucune parole sur l'extrait parlé {name}/{label}")
    return item


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=EXPERIMENTS / "fluid-q8.lock.json")
    parser.add_argument("--output-dir", required=True, type=Path, help="Nouveau dossier local")
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("--suite", choices=("smoke", "corpus", "wamatipsia", "all"), default="all")
    args = parser.parse_args()
    directory = args.output_dir.resolve()
    if directory.exists():
        parser.error("Le dossier de sortie existe déjà ; choisir un nouveau --output-dir")
    config = read_json(args.config)
    backend = Backend.verified(ROOT)
    if backend.provenance["build"]["native_commit"] != config["native_commit"]:
        raise ValueError("Commit natif différent de celui de l'expérience")
    baseline = EXPERIMENT_MODELS / config["baseline_model"]["file"]
    candidate = ROOT / "models" / config["model"]["file"]
    if not candidate.is_file():
        candidate = EXPERIMENT_MODELS / config["model"]["file"]
    if args.download_model:
        from scripts.prepare_backend import download
        download(config["baseline_model"], config["baseline_repository"], config["baseline_revision"],
                 directory=EXPERIMENT_MODELS)
        download(config["model"], config["model_repository"], config["model_revision"], directory=candidate.parent)
    variants = []
    for label, path, metadata in (("ultra-f16", baseline, config["baseline_model"]),
                                  ("fluid-q8", candidate, config["model"])):
        verify_model(path, size=metadata["size"], sha256=metadata["sha256"])
        variants.append((label, replace(backend, asr_model=path,
                         provenance={**backend.provenance, "experiment_asr": metadata})))
    directory.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "status": "running", "date_utc": datetime.now(timezone.utc).isoformat(),
              "platform": platform.platform(), "machine": platform.machine(), "experiment": config,
              "backend": backend.provenance, "application": __version__,
              "omitted_asr_tokens": sorted(OMITTED_ASR_TOKENS), "normalization": "NFKC, casefold, apostrophes unifiées, ponctuation ignorée",
              "order": "Ultra puis Fluid pour chaque cas ; une seule exécution, ordre non randomisé",
              "results": []}
    write_json(directory / "report.json", report)
    try:
        cases = []
        if args.suite in ("smoke", "corpus", "all"):
            manifest_path = FIXTURES / "corpus_manifest.json"
            if sha256_file(manifest_path) != config["corpus_manifest_sha256"]:
                raise ValueError("Inventaire du corpus différent de celui de l'expérience")
            manifest = read_json(manifest_path)
            for pair in manifest["pairs"]:
                source = ROOT / pair["audio"]
                if sha256_file(source) != pair["audio_sha256"]:
                    raise ValueError(f"Corpus différent de la référence : {source}")
                if args.suite == "smoke":
                    ffmpeg = shutil.which("ffmpeg")
                    if not ffmpeg:
                        raise FileNotFoundError("FFmpeg introuvable")
                    source = directory / "smoke.wav"
                    run_process([ffmpeg, "-nostdin", "-v", "error", "-i", str(ROOT / pair["audio"]),
                                 "-t", "30", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(source)],
                                directory / "extract.stdout", directory / "extract.log")
                    cases.append(("smoke", "first-30s", source, None))
                    break
                reference = ROOT / pair["srt"]
                if sha256_file(reference) != pair["srt_sha256"]:
                    raise ValueError(f"SRT de référence modifié : {reference}")
                text = " ".join(c.text for c in parse_srt(reference.read_text(encoding="utf-8-sig")))
                cases.append(("corpus", source.stem, source, text))
        if args.suite in ("wamatipsia", "all"):
            settings = config["wamatipsia"]
            source, cuts_path = ROOT / settings["source"], ROOT / settings["cuts"]
            if sha256_file(source) != settings["source_sha256"]:
                raise ValueError("Audio WamaTipsIA différent de la référence")
            report["cuts_sha256"] = sha256_file(cuts_path)
            if report["cuts_sha256"] != settings["cuts_sha256"]:
                raise ValueError("Coupes WamaTipsIA différentes de celles de l'expérience")
            cuts = read_json(cuts_path)["segments"]
            for index in settings["cut_indices"]:
                cut = cuts[index]
                audio = directory / f"cut-{index}.wav"
                extract_wave(source, audio, cut["start"], cut["end"], 0)
                cases.append(("wamatipsia", f"cut-{index}", audio, None))
        for suite, name, source, reference in cases:
            for label, variant in variants:
                item = run_case(variant, source, directory / suite / name / label,
                                suite=suite, name=name, label=label, threads=config["threads"], reference=reference)
                report["results"].append(item)
                report["summary"] = summarize(report["results"])
                write_json(directory / "report.json", report)
                atomic_text(directory / "comparison.md", markdown(report))
        report["status"] = "completed"
        write_json(directory / "report.json", report)
    except BaseException as error:
        report.update(status="failed", error=str(error))
        write_json(directory / "report.json", report)
        raise
    print(f"Rapport : {directory / 'report.json'}", flush=True)


if __name__ == "__main__":
    main()
