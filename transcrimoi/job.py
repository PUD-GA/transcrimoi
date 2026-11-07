"""Pipeline de développement utilisable sans interface, avec checkpoints validés."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Callable
import wave

from . import __version__
from .assignment import Segmentation, assign_words, resolve_contextual_speakers, segment_words
from .backend import Backend
from .process import Cancelled, run_process
from .schema import SCHEMA_VERSION, parse_asr, parse_diarization
from .srt import export_srt
from .storage import fingerprint, read_json, sha256_file, write_json


@contextmanager
def work_lock(path: Path):
    """Verrou libéré aussi après un crash, sans fichier sentinelle périmé."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if os.name == "posix":
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError(f"Dossier de travail déjà utilisé : {path.parent}") from error
        else:
            import msvcrt
            if path.stat().st_size == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError(
                    f"Verrouillage du dossier de travail impossible : {path.parent}. "
                    "Dossier déjà utilisé ou verrouillage non pris en charge ; utiliser un disque local."
                ) from error
        try:
            yield
        finally:
            if os.name == "posix":
                fcntl.flock(stream, fcntl.LOCK_UN)
            else:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        if (audio.getnchannels(), audio.getframerate(), audio.getsampwidth()) != (1, 16000, 2):
            raise ValueError("Audio de travail attendu : WAV PCM 16 bits mono 16 kHz")
        if audio.getnframes() == 0:
            raise ValueError("Média vide")
        return audio.getnframes() / audio.getframerate()


class Job:
    def __init__(self, backend: Backend, *, threads: int = 4,
                 segmentation: Segmentation = Segmentation(),
                 event: Callable[[dict], None] | None = None,
                 cancel: threading.Event | None = None,
                 ffmpeg: Path | None = None):
        if threads < 1:
            raise ValueError("Le nombre de threads doit être positif")
        self.backend = backend
        self.threads = threads
        self.segmentation = segmentation
        self.event = event or (lambda value: None)
        self.cancel = cancel or threading.Event()
        self.ffmpeg = ffmpeg

    def emit(self, phase: str, status: str, **fields) -> None:
        self.event({"schema_version": SCHEMA_VERSION, "phase": phase, "status": status, **fields})

    def check_cancel(self) -> None:
        if self.cancel.is_set():
            raise Cancelled("Traitement annulé")

    def run(self, source: Path, output: Path, work: Path, *, overwrite: bool = False) -> dict:
        source, output, work = source.resolve(), output.resolve(), work.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Média absent : {source}")
        if output.suffix.lower() != ".srt" or output == source:
            raise ValueError("La destination doit être un SRT distinct de la source")
        if output.exists() and not overwrite:
            raise FileExistsError(f"SRT existant, non écrasé : {output}")
        # La source ne doit pas être l'un de nos artefacts de travail.
        if source.is_relative_to(work):
            raise ValueError("Choisir un dossier de travail ne contenant pas la source")
        ffmpeg = str(self.ffmpeg.resolve()) if self.ffmpeg is not None else shutil.which("ffmpeg")
        if ffmpeg is None or not Path(ffmpeg).is_file():
            raise FileNotFoundError("FFmpeg introuvable")
        work.mkdir(parents=True, exist_ok=True)
        with work_lock(work / ".lock"):
            self.check_cancel()
            self.emit("verification", "started")
            provenance = {
                "schema_version": SCHEMA_VERSION, "application": __version__,
                "source": str(source), "source_sha256": sha256_file(source),
                "backend": self.backend.provenance, "ffmpeg_sha256": sha256_file(Path(ffmpeg)),
                "threads_asr": self.threads, "segmentation": asdict(self.segmentation),
                "audio_filter": "aresample=async=1:first_pts=0",
            }
            job_id = fingerprint(provenance)
            state_path = work / "state.json"
            if state_path.exists():
                state = read_json(state_path)
                if state.get("job_id") != job_id:
                    raise ValueError("Dossier de travail d'une autre source/version/configuration ; choisir un nouveau dossier")
            else:
                state = {"schema_version": SCHEMA_VERSION, "job_id": job_id,
                         "provenance": provenance, "completed": {}}
            state["status"] = "running"
            state.pop("error", None)
            write_json(state_path, state)

            def phase(name: str, path: Path, produce: Callable, validate: Callable):
                self.check_cancel()
                cached = state["completed"].get(name)
                if cached and path.exists() and sha256_file(path) == cached["sha256"]:
                    result = validate(path)
                    self.emit(name, "reused")
                    return result
                self.emit(name, "started")
                start = time.monotonic()
                produce(path)
                self.check_cancel()
                result = validate(path)
                state["completed"][name] = {"file": path.name, "sha256": sha256_file(path),
                                            "seconds": round(time.monotonic() - start, 3)}
                write_json(state_path, state)
                self.emit(name, "completed", seconds=state["completed"][name]["seconds"])
                return result

            try:
                def convert(path: Path) -> None:
                    partial = path.with_name("audio.part.wav")
                    try:
                        run_process([ffmpeg, "-nostdin", "-v", "error", "-y", "-i", str(source),
                                     "-map", "0:a:0", "-vn", "-af", provenance["audio_filter"],
                                     "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", str(partial)],
                                    work / "ffmpeg.stdout", work / "ffmpeg.log", self.cancel)
                        wav_duration(partial)
                        os.replace(partial, path)
                    finally:
                        partial.unlink(missing_ok=True)

                audio = work / "audio.wav"
                duration = phase("audio", audio, convert, wav_duration)
                words = phase("asr", work / "asr.json",
                              lambda path: run_process(self.backend.asr_command(audio, self.threads), path,
                                                       work / "asr.log", self.cancel),
                              lambda path: parse_asr(read_json(path), duration))
                turns = phase("diarization", work / "diarization.json",
                              lambda path: run_process(self.backend.diarization_command(audio), path,
                                                       work / "diarization.log", self.cancel),
                              lambda path: parse_diarization(read_json(path), duration))
                self.check_cancel()
                self.emit("assignment", "started")
                assigned = assign_words(words, turns, nearest_gap=self.segmentation.nearest_gap)
                assigned = resolve_contextual_speakers(assigned)
                cues = segment_words(assigned, duration, self.segmentation)
                unknown = sum(item.speaker is None for item in assigned)
                result = {
                    "schema_version": SCHEMA_VERSION, "job_id": job_id, "duration": duration,
                    "words": [asdict(item) for item in assigned], "turns": [asdict(t) for t in turns],
                    "cues": [asdict(c) for c in cues], "unknown_words": unknown,
                    "speakers_observed": sorted({t.speaker for t in turns}),
                }
                write_json(work / "result.json", result)
                state["completed"]["assignment"] = {
                    "file": "result.json", "sha256": sha256_file(work / "result.json")}
                write_json(state_path, state)
                self.emit("assignment", "completed", unknown_words=unknown)
                self.check_cancel()
                if sha256_file(source) != provenance["source_sha256"]:
                    raise ValueError("Le média source a changé pendant le traitement")
                self.emit("export", "started")
                export_srt(output, cues, overwrite=overwrite)
                state.update(status="completed", output=str(output), output_sha256=sha256_file(output))
                write_json(state_path, state)
                self.emit("export", "completed", path=str(output), cues=len(cues), unknown_words=unknown)
                return result
            except BaseException as error:
                state.update(status="cancelled" if isinstance(error, (Cancelled, KeyboardInterrupt)) else "failed",
                             error=str(error))
                write_json(state_path, state)
                self.emit("job", state["status"], message=str(error))
                raise
