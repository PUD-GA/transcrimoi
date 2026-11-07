"""Attribution déterministe et segmentation pour un document de travail."""
from __future__ import annotations

from dataclasses import dataclass
import re

from .schema import AssignedWord, Cue, Turn, Word
from .srt import milliseconds


@dataclass(frozen=True)
class Segmentation:
    # Valeurs initiales à qualifier dans SonalPi2, pas des contraintes SRT.
    max_duration: float = 15.0
    max_characters: int = 240
    max_gap: float = 0.8
    nearest_gap: float = 0.15


def merge_turns(turns: list[Turn]) -> list[Turn]:
    """Union par locuteur pour ne jamais compter deux fois un recouvrement."""
    merged: list[Turn] = []
    for turn in sorted(turns, key=lambda t: (t.speaker, t.start, t.end)):
        if merged and merged[-1].speaker == turn.speaker and merged[-1].end >= turn.start:
            previous = merged.pop()
            merged.append(Turn(previous.start, max(previous.end, turn.end), turn.speaker))
        else:
            merged.append(turn)
    return sorted(merged, key=lambda t: (t.start, t.speaker))


def assign_words(words: list[Word], turns: list[Turn], *, nearest_gap: float = 0.15) -> list[AssignedWord]:
    """Balayage temporel ; égalité => indéterminé, jamais l'ID le plus petit."""
    turns = merge_turns(turns)
    active: list[Turn] = []
    cursor = 0
    assigned = []
    for word in words:
        while cursor < len(turns) and turns[cursor].start <= word.end + nearest_gap:
            active.append(turns[cursor])
            cursor += 1
        active = [t for t in active if t.end >= word.start - nearest_gap]
        overlaps: dict[int, float] = {}
        distances: dict[int, float] = {}
        for turn in active:
            overlap = max(0.0, min(word.end, turn.end) - max(word.start, turn.start))
            if overlap > 0:
                overlaps[turn.speaker] = overlaps.get(turn.speaker, 0.0) + overlap
            gap = max(0.0, turn.start - word.end, word.start - turn.end)
            distances[turn.speaker] = min(distances.get(turn.speaker, float("inf")), gap)
        speaker = None
        reason = "no_speech"
        if overlaps:
            best = max(overlaps.values())
            winners = [s for s, score in overlaps.items() if abs(score - best) < 1e-6]
            if len(winners) == 1:
                speaker, reason = winners[0], "overlap"
            else:
                reason = "overlap_tie"
        elif distances:
            best = min(distances.values())
            winners = [s for s, score in distances.items() if abs(score - best) < 1e-6]
            if best <= nearest_gap and len(winners) == 1:
                speaker, reason = winners[0], "nearest"
            elif best <= nearest_gap:
                reason = "nearest_tie"
        assigned.append(AssignedWord(word, speaker, reason))
    return assigned


CLOSING_PUNCTUATION = re.compile(r"^[,.!?;:…]+$")


def is_closing_punctuation(text: str) -> bool:
    return CLOSING_PUNCTUATION.fullmatch(text) is not None


def resolve_contextual_speakers(words: list[AssignedWord]) -> list[AssignedWord]:
    """Attribue les absences au contexte le plus proche ; une égalité favorise l'avant."""
    resolved = list(words)
    index = 0
    while index < len(resolved):
        if resolved[index].speaker is not None or is_closing_punctuation(resolved[index].word.text):
            index += 1
            continue
        end = index + 1
        while (end < len(resolved) and resolved[end].speaker is None
               and not is_closing_punctuation(resolved[end].word.text)):
            end += 1

        previous = next((resolved[i] for i in range(index - 1, -1, -1)
                         if resolved[i].speaker is not None
                         and not is_closing_punctuation(resolved[i].word.text)), None)
        following = next((resolved[i] for i in range(end, len(resolved))
                          if resolved[i].speaker is not None
                          and not is_closing_punctuation(resolved[i].word.text)), None)
        speaker = None
        reason = None
        if previous is not None and following is not None:
            previous_gap = max(0.0, resolved[index].word.start - previous.word.end)
            following_gap = max(0.0, following.word.start - resolved[end - 1].word.end)
            if previous.speaker == following.speaker:
                speaker, reason = previous.speaker, "context_same_speaker"
            elif previous_gap <= following_gap + 1e-9:
                reason = ("context_previous_tie" if abs(previous_gap - following_gap) <= 1e-9
                          else "context_nearest_previous")
                speaker = previous.speaker
            else:
                speaker, reason = following.speaker, "context_nearest_next"
        elif previous is not None:
            speaker, reason = previous.speaker, "context_only_previous"
        elif following is not None:
            speaker, reason = following.speaker, "context_only_next"
        if speaker is not None:
            for i in range(index, end):
                resolved[i] = AssignedWord(resolved[i].word, speaker, reason)
        index = end

    # La ponctuation fermante est une information textuelle, pas une nouvelle voix.
    # Elle hérite uniquement du token lexical qui la précède immédiatement.
    for index, item in enumerate(resolved):
        if not is_closing_punctuation(item.word.text) or item.speaker is not None:
            continue
        previous = index - 1
        while previous >= 0 and is_closing_punctuation(resolved[previous].word.text):
            previous -= 1
        if previous >= 0 and resolved[previous].speaker is not None:
            resolved[index] = AssignedWord(item.word, resolved[previous].speaker, "punctuation_previous")
    return resolved


def join_words(words: list[str]) -> str:
    text = " ".join(words)
    # Pas de correction linguistique : uniquement les espaces des tokens isolés.
    text = re.sub(r"\s+([,.!?;:…])", r"\1", text)
    text = re.sub(r"(['’])\s+", r"\1", text)
    return text.strip()


def segment_words(words: list[AssignedWord], duration: float, config: Segmentation) -> list[Cue]:
    cues: list[Cue] = []
    group: list[AssignedWord] = []

    def emit() -> None:
        if not group:
            return
        timed = [w for w in group if not is_closing_punctuation(w.word.text)] or group
        start = min(w.word.start for w in timed)
        end = max(w.word.end for w in timed)
        # Les signes de ponctuation peuvent avoir start=end dans l'ASR.
        # Conserver ces tokens ; garantir au bloc au moins 1 ms exportable.
        if milliseconds(end) <= milliseconds(start):
            end = min(duration, (milliseconds(start) + 1) / 1000)
            if milliseconds(end) <= milliseconds(start):
                start = max(0, (milliseconds(end) - 1) / 1000)
        cues.append(Cue(start, end, join_words([w.word.text for w in group]), group[0].speaker))

    for item in words:
        if group:
            # Un signe fermant complète toujours le bloc lexical précédent. Son
            # horodatage natif, parfois placé dans le silence, ne crée pas de bloc.
            if is_closing_punctuation(item.word.text):
                group.append(item)
                continue
            previous = group[-1]
            proposed = join_words([w.word.text for w in group] + [item.word.text])
            split = (
                item.speaker != previous.speaker
                or item.word.start - previous.word.end > config.max_gap
                or item.word.end - group[0].word.start > config.max_duration
                or len(proposed) > config.max_characters
                or previous.word.text.endswith((".", "?", "!", "…"))
            )
            if split:
                emit()
                group = []
        group.append(item)
    emit()
    return cues
