# Essai Fluid Speech Pro Q8_0 / Ultra F16

> **Évolution ultérieure :** Fluid Q8_0 a été adopté par choix utilisateur pour son
> potentiel multilingue et sa mémoire réduite, sans revendication de gain établi sur
> notre corpus français. La version 0.2.0 filtre désormais les seuls tokens `<unk>`
> avant attribution et segmentation, avec une trace dans le JSON et un avertissement.
> Les résultats ci-dessous précèdent ce filtrage et restent inchangés. Fluid se trouve
> maintenant dans `models/`, Ultra dans `tests/models/`. Voir la
> [mise à jour depuis Ultra](../README.md#mise-à-jour-depuis-ultra).

## Recommandation initiale après ce premier essai

**Conserver Ultra F16 comme modèle du produit.** Fluid Q8_0 fonctionne avec le runtime
existant et diminue nettement la mémoire du processus ASR, mais aucun gain de précision
n’est établi sur notre petit corpus français. Sur les médias complets, il est légèrement
plus lent dans cette exécution. Il reste un candidat intéressant pour une variante
moins gourmande ; ce n’est pas une validation de son adoption.

La comparaison change **à la fois le modèle et sa précision** : elle n’isole pas l’effet
de la quantification. Un essai Fluid F32 pourrait compléter l’analyse, mais n’a pas été
exécuté ici. Aucune modification du backend par défaut ni des anciens résultats.

## Modèles et protocole

Configuration reproductible :
[`tests/experiments/fluid-q8.lock.json`](../tests/experiments/fluid-q8.lock.json).

- Ultra F16 : `moondream/parakeet-ultra`, GGUF de 1 441 900 448 octets.
- Fluid Q8_0 : `FluidVoice-Labs/fluid-speech-pro-gguf`, GGUF de 940 663 968 octets,
  révision `fee970d9ac83f6d236632d39b67cbec12f5a9020`.
- Empreintes SHA-256 des poids vérifiées ; Fluid conservé dans `tests/models/`.
- Même runtime parakeet.cpp `2eac2e77d9c7ef8899f7a86a46e693ac5ac1a5cd`.
- Même pipeline : WAV mono 16 kHz, quatre threads ASR, Silero, Nemotron, attribution
  contextuelle et segmentation actuelles. Aucun mode « clean », dictionnaire ou LLM.
- Quatre médias synthétiques complets et quatre extraits WamaTipsIA sans padding.
- Une exécution par condition, Ultra puis Fluid pour chaque cas, dossiers neufs sans
  reprise. Ce n’est pas un benchmark statistique ni une comparaison d’architectures à
  précision identique.

Environnement : Linux/WSL2 x86-64, Intel Xeon w5-3525, Python 3.12.3.
GNU time mesure le pic RSS **du processus ASR seul**, pas celui de l’application entière
ni la somme ASR + diarisation. Les temps ASR incluent le chargement du modèle.
Cette station de développement ne représente pas un ordinateur modeste.

## Compatibilité : essai court préalable

Les 30 premières secondes du premier média synthétique ont été traitées séparément
avec les deux modèles : 104 mots/tokens horodatés chacun, export SRT réussi.
Le parseur valide les bornes, l’ordre et les valeurs des horodatages.
**Cela ne mesure pas leur justesse à l’écoute**, ni la qualité de l’import SonalPi2.

La comparaison principale a ensuite terminé ses 16 conditions sans erreur, avec des
mots horodatés et des SRT exportés pour chaque condition.

## Corpus synthétique : écarts lexicaux

Référence : les quatre SRT fournis par l’utilisateur, pas une transcription humaine
indépendante de validation. Normalisation identique à l’outil existant : NFKC,
minuscules, apostrophes unifiées, ponctuation ignorée, chiffres non développés.
Les préfixes de locuteur sont exclus du score. Ce score n’évalue pas la diarisation.

WER sur le **texte livré dans les blocs SRT** (plus bas = moins d’écarts) :

| Média | Ultra F16 | Fluid Q8_0 |
|---|---:|---:|
| 1Coordinatrice | 6,63 % | 6,77 % |
| 2RetraiteAnticipee | 9,59 % | 10,32 % |
| 3Cuisinier | 9,72 % | 10,22 % |
| 4Etudiants | 2,41 % | 2,41 % |
| **Total pondéré, 2 727 mots de référence** | **7,30 % (199 erreurs)** | **7,66 % (209 erreurs)** |

Le texte plat natif donne **7,22 % pour Ultra et 7,33 % pour Fluid** (197 et 200 erreurs).
La différence avec le SRT vient ici de tokens natifs `<unk>` présents dans la liste des
mots horodatés mais absents du texte plat. Le pipeline les conserve : **2 pour Ultra,
9 pour Fluid** sur les quatre médias (respectivement 2/0/0/0 et 2/5/2/0).
Sept des dix erreurs SRT supplémentaires de Fluid proviennent donc de ces tokens.
Leur présentation reste un sujet distinct ; ils n’ont pas été supprimés pour favoriser
un modèle dans ce test.

Ces écarts faibles sur un petit corpus ne prouvent pas une supériorité générale d’Ultra.
Ils ne confirment simplement pas de gain de Fluid Q8_0 pour notre usage actuel.

## Temps et mémoire : quatre médias complets

| Mesure | Ultra F16 | Fluid Q8_0 |
|---|---:|---:|
| Somme des temps ASR | 112,50 s | 117,72 s |
| Plus grand pic RSS ASR observé | 1 709,7 Mio | 1 229,5 Mio |
| Poids à télécharger | 1 441,9 Mo | 940,7 Mo |

Fluid réduit ici le plus grand pic RSS ASR d’environ **28 %**, soit environ 480 Mio,
et la taille des poids d’environ **35 %**. Son temps ASR cumulé est environ **5 % plus
long** sur les médias complets. Les petits extraits WamaTipsIA donnent au contraire
des temps légèrement plus courts pour Fluid : ne pas en déduire un gain de vitesse
stable sans répétitions et contrôle de l’ordre et des caches.

## Extraits WamaTipsIA

Les quatre coupes historiques (indices 0, 20, 100 et 180 : début, vers 9, 44 et 79 min)
ont été extraites une seule fois puis utilisées par les deux modèles.

- Les sorties contrôlées textuellement restent en français avec les deux modèles.
- Les textes sont proches, avec des différences de ponctuation, répétitions,
  hésitations et noms propres. Une ponctuation plus présente ne prouve pas une
  transcription plus fidèle.
- Pas de référence humaine sur ces coupes : aucun WER ni jugement de supériorité.
- La vidéo complète n’a pas été retraitée avec Fluid ; ni les longs entretiens,
  le bruit, les silences seuls, ni les performances sur Windows/macOS n’ont été
  qualifiés pour ce modèle.

## Artefacts locaux et reproduction

- `tests/runs/fluid-smoke-q8/` : essai de compatibilité sur 30 secondes.
- `tests/runs/fluid-comparison-q8/report.json` : provenance, scores, temps et mémoire.
- `tests/runs/fluid-comparison-q8/comparison.md` : tableaux et textes des extraits.
- Sous chaque cas/modèle : SRT, JSON natifs, états et journaux.
- `tests/runs/fluid-download/` : journaux du téléchargement et du lanceur.

Les médias, poids, textes et résultats détaillés restent locaux, ignorés par Git.
Le script partageable est `tests/tools/compare_fluid.py` ; les commandes et limites
sont dans le [guide des tests](../tests/README.md#expérience-ultra-f16--fluid-speech-pro-q8).
Huit nouveaux tests sans vrais modèles couvrent l’outil ; la suite complète atteint
116 tests réussis sur Linux/WSL avec les corpus locaux.

## Validation ultérieure de l’adoption et du filtrage (0.2.0)

Après adoption explicite, le préparateur a revérifié les trois modèles et mis à jour le
manifeste local. Fluid est dans `models/` ; Ultra est conservé dans `tests/models/`.
La suite atteint **126 tests réussis**, dont les cas de filtrage exact, fragments non
supprimés, traçabilité, sortie vide après filtrage, avertissements GUI/CLI et reprise.

Deux essais réels supplémentaires ont été exécutés depuis la fenêtre sous Linux/WSL :

- Silence synthétique de trois secondes : zéro bloc, zéro omission, message explicite.
- Média synthétique `2RetraiteAnticipee` complet : **82 blocs, 5 marqueurs `<unk>` omis**,
  avertissement affiché. Les sorties natives et les temps des omissions restent dans
  le dossier de travail ; le SRT ne contient plus ces marqueurs.

Artefacts locaux : `tests/runs/fluid-filter/gui-native-silence/` et
`tests/runs/fluid-filter/gui-native-speech/`. Ces essais ne valident ni les autres
langues ni Windows/macOS. Les anciens rapports de comparaison n’ont pas été modifiés.

## Limites annoncées en amont

La [fiche GGUF figée](https://huggingface.co/FluidVoice-Labs/fluid-speech-pro-gguf/blob/fee970d9ac83f6d236632d39b67cbec12f5a9020/README.md)
indique que ce format omet le petit bloc supplémentaire du modèle NeMo, particulièrement
utile sur le bruit, et ne propose pas le mode « clean ». Les scores du modèle complet
avec décodage beam-search ne sont donc pas ceux de ce test GGUF.
La fiche annonce le même commit parakeet.cpp que le nôtre ; le chargement et la sortie
horodatée ont été vérifiés concrètement ici.

Licence annoncée : CC-BY-4.0 ; attribution demandée « Fluid Speech Pro by FluidVoice ».
Voir l’[inventaire des composants tiers](composants-tiers.md).
