"""SRT texte UTF-8 et préfixes Speaker N: observés dans CorpusSynth."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re

from .schema import Cue, number
from .storage import atomic_text

STAMP = r"(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})"
TIMING = re.compile(rf"^{STAMP} --> {STAMP}$")
SPEAKER = re.compile(r"^Speaker (\d+):\s*(.*)$", re.DOTALL)


def milliseconds(seconds: float) -> int:
    value = number(seconds)
    if value < 0:
        raise ValueError("Temps négatif")
    return int((Decimal(str(value)) * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def timestamp(ms: int) -> str:
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def render_srt(cues: list[Cue]) -> str:
    blocks = []
    previous = -1
    for i, cue in enumerate(cues, 1):
        start, end = milliseconds(cue.start), milliseconds(cue.end)
        if start < previous or end <= start:
            raise ValueError("Bloc SRT désordonné ou vide après arrondi")
        text = cue.text.strip().replace("\r\n", "\n")
        if not text or "\n\n" in text or "\r" in text:
            raise ValueError("Texte SRT vide ou contenant un séparateur de blocs")
        if cue.speaker is not None:
            if type(cue.speaker) is not int or cue.speaker < 0:
                raise ValueError("Locuteur SRT invalide")
            text = f"Speaker {cue.speaker}: {text}"
        blocks.append(f"{i}\n{timestamp(start)} --> {timestamp(end)}\n{text}\n")
        previous = start
    return "\n".join(blocks)


def parse_srt(text: str) -> list[Cue]:
    text = text.lstrip("\ufeff").replace("\r\n", "\n").strip()
    if not text:
        return []
    cues = []
    for expected, block in enumerate(re.split(r"\n[ \t]*\n", text), 1):
        lines = block.split("\n")
        if len(lines) < 3 or lines[0].strip() != str(expected):
            raise ValueError(f"Numéro ou bloc SRT invalide : {expected}")
        match = TIMING.fullmatch(lines[1])
        if match is None:
            raise ValueError(f"Horodatage SRT invalide : {lines[1]}")
        fields = [int(x) for x in match.groups()]
        def seconds(parts: list[int]) -> float:
            h, m, s, ms = parts
            return (h * 3_600_000 + m * 60_000 + s * 1000 + ms) / 1000
        content = "\n".join(lines[2:]).strip()
        speaker = SPEAKER.fullmatch(content)
        cues.append(Cue(seconds(fields[:4]), seconds(fields[4:]),
                        speaker[2] if speaker else content, int(speaker[1]) if speaker else None))
    render_srt(cues)  # Validation des bornes, de l'ordre et du texte.
    return cues


def export_srt(path: Path, cues: list[Cue], *, overwrite: bool = False) -> None:
    atomic_text(path, render_srt(cues), overwrite=overwrite)
