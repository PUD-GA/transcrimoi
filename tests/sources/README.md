# Sources locales des essais — ne pas publier

Ce dossier regroupe les **médias de test**, pas le code source de l’application.
Tout son contenu est ignoré par Git, sauf ce README.

```text
synth/                  Ancien CorpusSynth
  audio/                Quatre MP3 fournis
  srt/                  SRT de référence SonalPi2, à garder confidentiels aussi
  docs/                 Guide associé au corpus
reel/                   Ancien CorpusReel : entretien réel fourni
wamatipsia/
  WamaTipsIA.wav         WAV extrait utilisé pour les diagnostics
  cuts.json             Coupes VAD utilisées par l’expérience v3/Ultra
```

Le WAV WamaTipsIA a été retrouvé dans les résultats d’essais. Aucun fichier vidéo
original n’a été retrouvé dans le projet ; on ne reconstruit pas une provenance inconnue.
Les SRT générés de cet entretien sont des **résultats**, pas des références humaines :
ils restent dans `tests/runs/wamatipsia/`.

Ne pas ajouter de transcription, note, média ou archive à Git, même si le corpus est
synthétique. L’inventaire partageable est dans `tests/fixtures/corpus_manifest.json`.
Ne pas utiliser `git add -f` pour contourner ces protections.
Voir [le guide des tests](../README.md).
