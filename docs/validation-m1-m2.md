# Essais M0–M2 — 5 novembre 2026

> Rapport historique, antérieur à l’adoption d’Ultra et à l’interface. Les chemins de
> consultation ont été actualisés après rangement ; les anciens résultats restent inchangés.

## Ce qui a réellement été exécuté

- Corpus utilisateur inchangé, quatre paires MP3/SRT, 338 blocs de référence.
- Compilation CPU de parakeet.cpp `2eac2e77d9c7ef8899f7a86a46e693ac5ac1a5cd`.
- GGML `e705c5fed490514458bdd2eaddc43bd098fcce9b`, avec les correctifs fournis par
  le CMake amont. L’empreinte du diff est conservée dans `build/backend.json`.
- ASR Parakeet v3 F16, diarisation Nemotron F16, Silero F16 ; fichiers téléchargés
  depuis la révision figée et vérifiés par taille et SHA-256.
- Vrais processus natifs, pas les doubles des tests : conversion, ASR/VAD,
  diarisation progressive `--stream model`, attribution et export des quatre SRT.
- Seconde exécution avec checkpoints : les douze phases lourdes ont été réutilisées
  et les SRT régénérés à l’identique (empreintes conservées).
- Silence synthétique de 3 s : zéro mot, zéro bloc, SRT vide, fin sans erreur.
- 49 tests Python réussis ; trois tests CTest ciblés réussis.

## Environnement et résultats initiaux

Linux/WSL2 x86_64, Intel Xeon w5-3525 (16 cœurs / 32 threads logiques), environ
30 Gio de RAM disponibles au système. Build Release, GGML lié statiquement,
`GGML_NATIVE=OFF`. ASR : quatre threads ; diarisation : défaut natif (huit).
Ce poste de développement n’est pas une machine pilote 8 Go.

| Média | Durée décodée | Temps initial total¹ | Blocs produits | Locuteurs observés | Tokens sans attribution | Écart lexical² |
|---|---:|---:|---:|---|---:|---:|
| 1Coordinatrice | 223,49 s | 32,34 s | 79 | 0, 1 | 6 | 9,94 % |
| 2RetraiteAnticipee | 296,74 s | 42,06 s | 83 | 0, 1 | 4 | 22,45 % |
| 3Cuisinier | 234,56 s | 33,67 s | 77 | 0, 1 | 1 | 13,57 % |
| 4Etudiants | 214,48 s | 30,66 s | 84 | 0, 1, 2 | 12 | 3,44 % |

¹ Conversion, phases natives, attribution, export et contrôles de la tâche ;
vérification initiale commune du backend exclue. La commande complète des quatre
cas a pris **2 min 10,46 s**. Une seule exécution initiale : aucun benchmark statistique.

² Distance de Levenshtein par mots sur le **texte des blocs générés**, préfixes
`Speaker` retirés, comparé aux SRT fournis. Normalisation : NFKC, minuscules Unicode,
apostrophes unifiées, ponctuation ignorée ; nombres non développés. Ce chiffre
n’est pas une comparaison à noScribe ni une validation sur référence humaine.
Les écarts, notamment sur le deuxième média, nécessitent une inspection avant
qualification qualité ; ils ne sont pas déclarés acceptables par défaut.

`/usr/bin/time -v` rapporte un RSS maximal de 1 749 536 Kio (environ 1,67 Gio).
C’est un maximum de processus observé par cet outil, **pas** une somme synchronisée
de tous les processus ni une mesure sur entretien de deux heures.

## Artefacts locaux

- SRT à essayer dans SonalPi2 : `tests/runs/synth/srt/*.srt`.
- Sorties natives brutes, JSON attribué, audio et état : `tests/runs/synth/work/<nom>/`.
- Rapport reproductible : `tests/runs/synth/report.json`.
- Provenance historique : `tests/runs/synth/work/<nom>/state.json` ; les manifests courants
  `backend.lock.json` et `build/backend.json` décrivent désormais Fluid, pas ce premier essai v3.

Le rapport courant provient de la seconde exécution : ses `wall_seconds_this_run`
sont des temps de **réutilisation**, pas d’inférence. Les durées originales des
phases restent dans `phase_seconds_original`. Le tableau ci-dessus conserve les
temps totaux de la première exécution.

## Écarts et limites constatés

- Les nombres de locuteurs sont cohérents avec les références, mais cela ne prouve
  pas la justesse de chaque attribution ni la stabilité sur deux heures. Les IDs
  peuvent être permutés par rapport aux SRT fournis.
- 23 tokens restent sans attribution, dont beaucoup de signes de ponctuation et
  quelques mots. Ils sont exportés sans préfixe ; **ce cas n’est pas validé par le
  corpus d’entrée** et son import doit être essayé. Ne pas forcer une fausse identité.
- Deux tokens de la liste de mots native du premier média contiennent `<unk>`, alors
  qu’ils ne figurent pas dans le texte plat natif. Le prototype conserve ces sorties
  telles quelles et ne prétend pas résoudre leur sens. Le rapport distingue le score
  du SRT livré de celui du texte plat. Leur présentation reste à améliorer.
- Les SRT ont une segmentation différente des références : ce n’est pas en soi une
  erreur de contenu, mais l’ergonomie dans SonalPi2 doit être évaluée.
- La durée décodée des MP3 est un peu plus courte que la durée de conteneur (padding
  codec). L’absence de dérive doit être contrôlée face au média dans SonalPi2.
- Le CLI ASR court-circuite sa VAD pour les fichiers ≤ 30 s. L’essai de silence de
  3 s a réussi, mais ne garantit pas les bruits/non-paroles : prévoir une garde VAD
  explicite si ces essais montrent des hallucinations.
- Le runtime conserve des copies audio et des morceaux ASR en mémoire. Les essais
  courts ne qualifient donc pas la cible mémoire sur deux heures.

## Statut des jalons et suite

- **M0 :** contrat nominal établi à partir du corpus déclaré valide par l’utilisateur.
- **M1 :** démontré sur CPU Linux/WSL ; pas encore sur Metal ni en paquet portable.
- **M2 :** pipeline réel et SRT produits ; clôture fonctionnelle après essai des
  nouveaux fichiers dans SonalPi2, y compris les blocs sans attribution.
- **M3 :** sauvegardes, annulation et reprises de phases couvertes par tests ;
  qualification d’un entretien complet de deux heures encore à faire.
- **M4/M5 :** interface, installateurs et qualification des plateformes non réalisés.

Prochaines actions : vérifier les nouveaux SRT dans SonalPi2, examiner les écarts
textuels et les tokens spéciaux, puis profiler un entretien long avant de construire
l’interface utilisateur. Pas de reprise d’éditeur ni de modification de SonalPi2.
