"""CLI développeur indépendante de l'interface optionnelle transcrimoi.gui."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import sys
import threading

from .backend import Backend
from .exports import DEFAULT_FORMAT, FORMATS, cues_from_result, export_document, validate_output
from .job import Job
from .process import Cancelled
from .runtime import project_root
from .srt import parse_srt
from .storage import read_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="transcrimoi")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-srt", help="Vérifier la structure et les préfixes d'un SRT")
    validate.add_argument("file", type=Path)
    verify = commands.add_parser("verify-backend", help="Revérifier intégralement le moteur et les modèles (SHA-256)")
    verify.add_argument("--project-root", type=Path, default=project_root())
    transcribe = commands.add_parser("transcribe", help="Transcrire avec le backend CPU préparé")
    transcribe.add_argument("source", type=Path)
    transcribe.add_argument("--output", "-o", required=True, type=Path)
    transcribe.add_argument("--work-dir", type=Path, required=True, help="Checkpoints et journaux, réutilisables")
    transcribe.add_argument("--project-root", type=Path, default=project_root())
    transcribe.add_argument("--threads", type=int, default=4, help="Threads ASR ; diarisation : défaut natif")
    transcribe.add_argument("--format", choices=[item.id for item in FORMATS], default=DEFAULT_FORMAT)
    transcribe.add_argument("--overwrite", action="store_true", help="Autoriser explicitement le remplacement du document")
    transcribe.add_argument("--json-events", action="store_true")
    export = commands.add_parser("export", help="Réexporter un result.json existant sans moteur ni modèles")
    export.add_argument("result", type=Path)
    export.add_argument("--output", "-o", required=True, type=Path)
    export.add_argument("--format", choices=[item.id for item in FORMATS], default=DEFAULT_FORMAT)
    export.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    previous_handlers = {}
    try:
        if args.command == "validate-srt":
            cues = parse_srt(args.file.read_text(encoding="utf-8-sig"))
            print(json.dumps({"blocks": len(cues), "speakers": sorted({c.speaker for c in cues if c.speaker is not None}),
                              "unattributed_blocks": sum(c.speaker is None for c in cues)}, ensure_ascii=False))
            return 0
        if args.command == "verify-backend":
            Backend.verified(args.project_root.resolve(), force_models=True)
            print("Moteur et modèles vérifiés intégralement (SHA-256).")
            return 0
        source = args.result if args.command == "export" else args.source
        validate_output(source, args.output, args.format)
        if args.output.exists() and not args.overwrite:
            raise FileExistsError(f"Document existant, non écrasé : {args.output}")
        if args.command == "export":
            cues = cues_from_result(read_json(args.result))
            export_document(args.output, cues, args.format, overwrite=args.overwrite)
            print(f"{args.output} — export {args.format}, {len(cues)} segments")
            return 0
        if args.threads < 1:
            raise ValueError("--threads doit être positif")
        cancel = threading.Event()
        def cancelled(signum, frame):
            cancel.set()
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.signal(signum, cancelled)
        def event(value: dict) -> None:
            if args.json_events:
                print(json.dumps(value, ensure_ascii=False), flush=True)
            else:
                print(f"{value['phase']} : {value['status']}", file=sys.stderr, flush=True)
        event({"schema_version": 1, "phase": "backend_verification", "status": "started"})
        backend = Backend.verified(args.project_root.resolve())
        event({"schema_version": 1, "phase": "backend_verification", "status": "completed"})
        job = Job(backend, threads=args.threads, cancel=cancel, event=event)
        result = job.run(args.source, args.output, args.work_dir, overwrite=args.overwrite, output_format=args.format)
        if not args.json_events:
            print(f"{args.output} — {len(result['cues'])} segments, {result['unknown_words']} mots sans locuteur")
            if result["omitted_token_count"]:
                print(f"{result['omitted_token_count']} marqueur(s) <unk> omis de l’export ; détails dans {args.work_dir / 'result.json'}")
        return 0
    except (Cancelled, KeyboardInterrupt):
        print("Traitement annulé ; phases validées conservées.", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
