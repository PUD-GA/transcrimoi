"""Contrat interne minimal : temps en secondes du média original."""
from __future__ import annotations

from dataclasses import dataclass
import math

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str
    confidence: float | None = None


@dataclass(frozen=True)
class Turn:
    start: float
    end: float
    speaker: int


@dataclass(frozen=True)
class AssignedWord:
    word: Word
    speaker: int | None
    reason: str


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str
    speaker: int | None


def number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Nombre fini attendu, reçu {value!r}")
    return float(value)


def interval(start: object, end: object, duration: float, *, zero_ok: bool = False) -> tuple[float, float]:
    a, b = number(start), number(end)
    if a < 0 or b < a or (a == b and not zero_ok):
        raise ValueError(f"Intervalle temporel invalide : {a}, {b}")
    # Le runtime utilise une grille ASR de 80 ms. Seule la dernière trame peut
    # dépasser légèrement le média ; on la borne, jamais un vrai décalage.
    if b > duration + 0.081 or a > duration:
        raise ValueError(f"Temps hors média ({duration}s) : {a}, {b}")
    b = min(b, duration)
    if a == b and not zero_ok:
        raise ValueError("Intervalle vide après bornage")
    return a, b


def parse_asr(value: object, duration: float) -> list[Word]:
    if not isinstance(value, dict) or not isinstance(value.get("text"), str) or not isinstance(value.get("words"), list):
        raise ValueError("Sortie ASR invalide : text et words attendus")
    words = []
    previous = -1.0
    for item in value["words"]:
        if not isinstance(item, dict) or not isinstance(item.get("w"), str) or not item["w"].strip():
            raise ValueError("Mot ASR vide ou invalide")
        a, b = interval(item.get("start"), item.get("end"), duration, zero_ok=True)
        if a < previous:
            raise ValueError("Mots ASR désordonnés")
        conf = None if item.get("conf") is None else number(item["conf"])
        if conf is not None and not 0 <= conf <= 1:
            raise ValueError("Confiance native hors [0,1]")
        words.append(Word(a, b, item["w"].strip(), conf))
        previous = a
    if value["text"].strip() and not words:
        raise ValueError("Texte ASR sans mots horodatés")
    return words


def parse_diarization(value: object, duration: float) -> list[Turn]:
    if not isinstance(value, dict) or not isinstance(value.get("segments"), list):
        raise ValueError("Sortie diarisation invalide : segments attendus")
    turns = []
    for item in value["segments"]:
        if not isinstance(item, dict):
            raise ValueError("Segment de diarisation invalide")
        speaker = item.get("speaker")
        if type(speaker) is not int or not 0 <= speaker < 8:
            raise ValueError("Identifiant de locuteur invalide")
        a, b = interval(item.get("start"), item.get("end"), duration)
        turns.append(Turn(a, b, speaker))
    # Le CLI --stream annonce toujours speakers=8 (capacité), pas le nombre
    # observé. On ne l'utilise jamais comme nombre de personnes présentes.
    return sorted(turns, key=lambda turn: (turn.start, turn.speaker, turn.end))
