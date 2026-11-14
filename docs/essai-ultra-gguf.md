# Essai Ultra F16 GGUF — WamaTipsIA

> Rapport historique : au moment de ces essais, v3 restait le modèle par défaut.
> Ultra F16 a depuis été adopté explicitement dans `backend.lock.json`, lors de
> l’ajout de l’[interface minimale](interface-minimale.md), puis remplacé par Fluid Q8_0
> par choix utilisateur. Voir l’[essai Fluid](essai-fluid-speech-pro.md).
> Les résultats ci-dessous et les anciens SRT ne sont pas modifiés.

## Comparaison sur quatre extraits

Le fichier `models/ultra-f16.gguf` a été vérifié par sa taille (1 441 900 448 octets)
et son SHA-256 (`5414aea5536178726e8dca20cdfc91cfa3e5443a83a65c4d08acd1c5df65323f`).
Références figées dans `tests/experiments/ultra-f16.lock.json`.
Les chemins ci-dessous reflètent le rangement actuel ; les artefacts historiques restent inchangés.

Les 16 conditions ont été exécutées : quatre extraits × deux modèles (v3/Ultra)
× deux paddings (0/250 ms par côté), avec le même runtime CPU, quatre threads et
les mêmes échantillons audio. Aucun LLM ni forçage de langue.

- Début, 2,132–29,504 s : Ultra écrit « Ok, normalement c'est enregistré… » avec
  ou sans padding. Le mélange observé avec v3 sans padding n'apparaît pas.
- Vers 9 min, 536,756–562,764 s : Ultra restitue en français le passage sur les
  coûts environnementaux et les centres de données, même sans padding. C'était
  le cas où le padding seul ne suffisait pas avec v3.
- Vers 44 min, 2634,880–2660,972 s : le passage reste en français avec les deux
  modèles ; Ultra ne montre pas de régression de langue visible.
- Vers 79 min, 4732,000–4756,652 s : Ultra écrit la conclusion en français avec
  ou sans padding, contrairement au mélange v3 sans padding.

Ce constat est qualitatif : pas de transcription humaine de référence ni de WER
validé pour ces extraits. Des erreurs de noms propres subsistent, par exemple
« Tip Cia » / « Tip CA ». L'absence de mélange visible sur quatre extraits ne
qualifie pas toute la vidéo.

Le premier extrait de 27,372 s a pris 3,807 s avec Ultra sans padding (chargement
natif compris). Une seule exécution sur une station Xeon : pas une promesse pour
un ordinateur modeste.

Artefacts détaillés : `tests/runs/wamatipsia/diagnostic-ultra/report.json` et
`comparison.md`. Le moteur par défaut dans `backend.lock.json` reste v3.

## Essai de la vidéo complète

Un traitement séparé utilise Ultra F16, le même Silero, la même diarisation
Nemotron F16 et les mêmes règles d'attribution/segmentation. **Sans padding** :
il s'agit d'isoler le changement de modèle et de conserver la chronologie sans
nouvelle correction d'offset.

- Lanceur historique archivé : `tests/runs/wamatipsia/run_ultra_full.py` (script ponctuel, non portable, ne pas relancer tel quel).
- Audio : `tests/sources/wamatipsia/WamaTipsIA.wav`, WAV mono 16 kHz, durée 4 968,191 s.
- Sortie locale : `tests/runs/wamatipsia/ultra-full/WamaTipsIA.ultra-f16.srt`.
- Copie Windows réalisée dans le dossier Téléchargements de l’utilisateur.
- Journaux, checkpoints et rapport : `tests/runs/wamatipsia/ultra-full/`.

**Statut : terminé.** Le SRT local et sa copie Windows ont la même empreinte
SHA-256 : `cecdc5c4e44b488d61a6d8bbbc46207aa8d62af384f2c41b55bb0a63dacbf8fa`.
Le SRT v3 précédent est conservé et son empreinte a été revérifiée.

- Durée audio : 1 h 22 min 48 s.
- Temps de la tâche : environ 11 min sur le Xeon de développement, dont
  527,084 s d'ASR et 127,487 s de diarisation.
- Sortie : 994 blocs, deux locuteurs observés, 10 272 mots/tokens natifs.
- 31 mots/tokens sans attribution certaine, répartis dans 27 blocs sans préfixe.
  Leur interprétation à l'import dans SonalPi2 reste à vérifier.
- Début et passages vers 9, 44 et 79 minutes contrôlés textuellement : le mélange
  français/anglais du résultat v3 n'y apparaît plus. Les noms propres et le reste
  de la transcription doivent encore être relus ; aucun WER humain n'est fourni.

Le téléchargement Photon s'exécutait en parallèle : ce n'est pas un benchmark
isolé. Le fichier est prêt pour un essai d'import et de relecture dans SonalPi2.
L'essai Photon CPU a également abouti : voir [le compte rendu](essai-photon-cpu.md).
