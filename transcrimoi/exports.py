"""Formats de restitution texte ; conventions inspirées de Tadddam, sans son code."""
from __future__ import annotations

from dataclasses import dataclass, replace
from html import escape
from pathlib import Path

from .schema import Cue, SCHEMA_VERSION
from .srt import milliseconds, render_srt, timestamp
from .storage import atomic_text

DEFAULT_FORMAT = "sonal-srt"


@dataclass(frozen=True)
class ExportFormat:
    id: str
    label: str
    suffix: str
    aliases: tuple[str, ...] = ()

    @property
    def suffixes(self) -> tuple[str, ...]:
        return (self.suffix, *self.aliases)

    @property
    def file_filter(self) -> str:
        return f"{self.label} ({' '.join('*' + suffix for suffix in self.suffixes)})"


FORMATS = (
    ExportFormat("sonal-srt", "SonalPi2 — SRT avec locuteurs", ".srt"),
    ExportFormat("txt", "Texte brut — sans locuteur", ".txt"),
    ExportFormat("speaker-txt", "Locuteur · Texte — séparés par un espace", ".txt"),
    ExportFormat("speaker-tsv", "Locuteur · Texte — séparés par une tabulation", ".txt", (".tsv",)),
    ExportFormat("timed-txt", "Temps · Locuteur · Texte — espaces", ".txt"),
    ExportFormat("nvivo", "Temps · Locuteur · Texte — tabulations", ".txt", (".tsv",)),
    ExportFormat("elan", "ELAN — Début · Fin · Locuteur · Texte (tabulations)", ".txt", (".tsv",)),
    ExportFormat("vtt", "WebVTT — sous-titres sans locuteur", ".vtt"),
    ExportFormat("srt", "SRT — sous-titres sans locuteur", ".srt"),
)


def get_format(format_id: str) -> ExportFormat:
    for item in FORMATS:
        if item.id == format_id:
            return item
    raise ValueError(f"Format d’export inconnu : {format_id}")


def validate_output(source: Path | None, output: Path, format_id: str) -> None:
    item = get_format(format_id)
    if source is not None and output.resolve() == source.resolve():
        raise ValueError("La destination doit être distincte de la source")
    if output.suffix.lower() not in item.suffixes:
        raise ValueError(f"Extension attendue pour {item.label} : {', '.join(item.suffixes)}")


def _line(text: str) -> str:
    # Les colonnes TSV et les paragraphes doivent rester sur une seule ligne.
    return " ".join(text.split())


def speaker_turns(cues: list[Cue]) -> list[Cue]:
    """Regrouper les blocs consécutifs du même locuteur pour les exports de texte."""
    turns: list[Cue] = []
    for cue in cues:
        text = _line(cue.text)
        if turns and turns[-1].speaker == cue.speaker:
            previous = turns[-1]
            turns[-1] = Cue(previous.start, max(previous.end, cue.end), previous.text + " " + text, cue.speaker)
        else:
            turns.append(replace(cue, text=text))
    return turns


def _seconds(value: float) -> str:
    ms = milliseconds(value)
    return f"{ms // 1000}.{ms % 1000:03}"


def render_export(cues: list[Cue], format_id: str = DEFAULT_FORMAT) -> str:
    get_format(format_id)
    # Validation commune, sans changer le contrat SRT historique.
    sonal = render_srt(cues)
    if format_id == "sonal-srt":
        return sonal
    if format_id == "srt":
        return render_srt([replace(cue, speaker=None) for cue in cues])
    if format_id == "vtt":
        blocks = []
        for index, cue in enumerate(cues, 1):
            start = timestamp(milliseconds(cue.start)).replace(",", ".")
            end = timestamp(milliseconds(cue.end)).replace(",", ".")
            text = escape(cue.text.strip().replace("\r\n", "\n"), quote=False)
            blocks.append(f"{index}\n{start} --> {end}\n{text}\n\n")
        return "WEBVTT\n\n" + "".join(blocks)
    if format_id == "txt":
        text = " ".join(_line(cue.text) for cue in cues)
        return text + "\n" if text else ""
    lines = []
    for turn in speaker_turns(cues):
        speaker = f"SPEAKER_{turn.speaker:02d}" if turn.speaker is not None else ""
        if format_id == "speaker-txt":
            line = f"{speaker} {turn.text}".lstrip()
        elif format_id == "speaker-tsv":
            line = f"{speaker}\t{turn.text}"
        elif format_id == "timed-txt":
            line = f"{_seconds(turn.start)} {speaker} {turn.text}"
        elif format_id == "nvivo":
            line = f"{_seconds(turn.start)}\t{speaker}\t{turn.text}"
        else:  # ELAN : colonne vide conservée après le temps de fin, comme Tadddam.
            line = f"{_seconds(turn.start)}\t{_seconds(turn.end)}\t\t{speaker}\t{turn.text}"
        lines.append(line + "\n")
    return "".join(lines)


def export_document(path: Path, cues: list[Cue], format_id: str = DEFAULT_FORMAT, *, overwrite: bool = False) -> None:
    validate_output(None, path, format_id)
    atomic_text(path, render_export(cues, format_id), overwrite=overwrite)


def cues_from_result(value: object) -> list[Cue]:
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value["schema_version"] != SCHEMA_VERSION or not isinstance(value.get("cues"), list)):
        raise ValueError("Résultat de transcription invalide : schema_version et cues attendus")
    cues = []
    for item in value["cues"]:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not {"start", "end", "speaker"} <= item.keys():
            raise ValueError("Bloc du résultat invalide")
        cues.append(Cue(item["start"], item["end"], item["text"], item["speaker"]))
    render_srt(cues)
    return cues
