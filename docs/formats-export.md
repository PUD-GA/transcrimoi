# Formats de sortie — version 0.3.0

Les neuf choix reprennent les **conventions de restitution** proposées par le projet
local Tadddam (`FRONTEND/SITE/V2/transcription.php`, aide des formats et script
`CLUSTER/transcript/transcript-pyannote.py`). L’implémentation est propre à transcrimoi :
aucun code Tadddam, Whisper, Torch ou Pyannote n’est repris/importé.

Le **SRT SonalPi2 reste le choix par défaut**, avec exactement la convention précédente.
Un seul fichier est produit par lancement ; changer de format permet de réutiliser les
phases compatibles. Pour conserver plusieurs sorties, choisir des noms distincts.

## Formats disponibles

| Choix Tadddam | Identifiant CLI | Contenu | Extension proposée |
|---|---|---|---|
| 10 — SONAL PI | `sonal-srt` | SRT avec préfixes `Speaker N: ` | `.srt` |
| 1 — Texte brut | `txt` | Texte en un seul bloc, sans temps ni étiquette de locuteur | `.txt` |
| 2 — Locuteur espace Texte | `speaker-txt` | `SPEAKER_00 Texte` | `.txt` |
| 3 — Locuteur TAB Texte | `speaker-tsv` | Locuteur, texte : deux colonnes tabulées | `.txt` ou `.tsv` |
| 4 — Temps espace Locuteur espace Texte | `timed-txt` | Début en secondes, locuteur, texte, séparés par des espaces | `.txt` |
| 5 — Temps / locuteur / texte | `nvivo` | Début en secondes, locuteur, texte : trois colonnes tabulées | `.txt` ou `.tsv` |
| 6 — ELAN | `elan` | Début, fin, colonne vide, locuteur, texte : cinq colonnes tabulées | `.txt` ou `.tsv` |
| 8 — VTT | `vtt` | WebVTT sans étiquette de locuteur | `.vtt` |
| 9 — SRT | `srt` | SRT sans étiquette de locuteur | `.srt` |

Les numéros de Tadddam sont indiqués pour correspondance ; la CLI utilise les
identifiants descriptifs ci-dessus. Les formats tabulés proposent `.txt` par défaut,
comme Tadddam ; `.tsv` est également accepté. Pas de DOCX/XLSX ni de document XML EAF.

Tous les fichiers sont écrits en UTF-8 sans BOM, avec fins de ligne LF, et protégés
contre l’écrasement par défaut, y compris une création concurrente de la destination.
Une extension incompatible avec le format choisi est refusée avant le traitement.

## Règles de restitution

### Formats texte et tabulés

Les blocs consécutifs du même locuteur sont regroupés en un paragraphe/ligne, même
s’ils sont séparés par une pause, jusqu’au changement de locuteur. Le début est celui
du premier bloc ; la fin ELAN couvre l’intégralité du groupe, pas seulement le premier
bloc. Les temps restent relatifs au média source.

Les secondes sont écrites avec un point et **trois décimales**, contrairement aux deux
décimales du script Tadddam : conserver la milliseconde évite un intervalle ELAN vide
sur un bloc très court. Les espaces multiples, tabulations et retours à la ligne du
texte sont normalisés en espaces pour ne pas créer de colonnes/lignes parasites.
Aucun en-tête, aucune correction linguistique ni nettoyage des hésitations n’est ajouté.

Les étiquettes sont `SPEAKER_00`, `SPEAKER_01`, etc., sans espace interne, comme les
étiquettes de texte de Tadddam. Un locuteur non attribué laisse le champ vide ; aucun
identifiant fictif n’est créé. Les identifiants ne sont pas des identités persistantes.

Exemple à trois colonnes (les séparations sont des tabulations) :

```text
0.700	SPEAKER_01	Bonjour. Comment allez-vous ?
3.000	SPEAKER_00	Très bien.
```

ELAN conserve la colonne vide après la fin utilisée par Tadddam :

```text
0.700	2.300		SPEAKER_01	Bonjour. Comment allez-vous ?
3.000	3.500		SPEAKER_00	Très bien.
```

L’identifiant CLI `nvivo` est conservé pour compatibilité, mais l’interface affiche la
description « Temps · Locuteur · Texte — tabulations ». Ces choix désignent des
conventions d’export tabulé, **pas une certification d’import** dans un logiciel donné.
Les options de colonnes, d’unités et de tiers restent à vérifier dans l’outil cible.
Un TSV est du texte, pas un classeur Excel.

### Sous-titres

Les formats `sonal-srt`, `srt` et `vtt` conservent les mêmes blocs et bornes temporelles,
sans regroupement des paragraphes. Seul `sonal-srt` ajoute les préfixes de locuteur.
Le [contrat SonalPi2](contrat-srt.md) reste inchangé. WebVTT utilise `WEBVTT`, le point
pour les millisecondes et échappe `&`, `<`, `>` dans le texte pour conserver leur sens
littéral plutôt que les traiter comme des balises.

Sans parole exportable, les formats texte/SRT sont vides ; le VTT conserve seulement
son en-tête `WEBVTT`. L’interface annonce zéro segment, pas nécessairement zéro octet.

### Pipeline commun

« Sans locuteur » signifie **sans étiquette dans le fichier**, pas un autre moteur :
conversion, ASR, diarisation et attribution restent exécutés de la même manière.
Contrairement à l’aide historique de Tadddam, le texte brut n’est donc pas présenté
comme un mode de secours pour les médias endommagés ou un contournement de la diarisation.

Le filtrage ciblé des tokens exactement égaux à `<unk>` précède ces exports, avec les
mêmes traces et avertissements. Les JSON natifs et `result.json` ne sont pas remplacés
par un format texte spécifique ; les `cues` sauvegardés restent réexportables.

## Utilisation

Dans la fenêtre, choisir le **Format de sortie** avant de transcrire. L’extension
proposée et le filtre du dialogue d’enregistrement s’adaptent. Changer de format
conserve le dossier et le nom choisis autant que possible et évite les fichiers
existants. Un changement de format seul ne change pas l’identité du travail ; relancer
réutilise les phases audio/ASR/diarisation déjà validées pour cette version.

CLI :

```bash
python -m transcrimoi transcribe entretien.mp3 --output entretien.txt \
  --work-dir travail --format nvivo
```

Pour obtenir d’autres formats **sans modèle, FFmpeg ni nouvelle inférence**, utiliser
le `result.json` d’une transcription achevée :

```bash
python -m transcrimoi export travail/result.json --output entretien.vtt --format vtt
python -m transcrimoi export travail/result.json --output entretien-elan.tsv --format elan
```

`--overwrite` est nécessaire pour remplacer explicitement un document existant.
L’export ne modifie pas le JSON source et ne peut pas l’écraser. Il restitue les blocs
**tels qu’ils ont été sauvegardés**, sans appliquer rétroactivement une nouvelle
politique d’attribution/filtrage aux anciens résultats. Le schéma interne version 1
reste accepté, notamment les résultats de la version 0.2.0.

La mise à jour de l’application vers 0.3.0 conserve les anciens fichiers mais change
l’identité des nouvelles tâches. Pour réexporter sans recalcul depuis une version
précédente, utiliser la commande `export` plutôt que reprendre son dossier avec `transcribe`.

## Vérifications

Les tests couvrent les neuf rendus, les locuteurs inconnus, Unicode, les colonnes,
l’arrondi, la fin ELAN regroupée, les sorties vides, la protection des fichiers et
le réexport sans backend. Les tests de fenêtre parcourent les neuf choix et vérifient
la réutilisation des trois phases natives.

Un essai réel sous Linux/WSL a traité 30 secondes parlées avec Fluid, puis exporté les
neuf formats depuis la fenêtre avec réutilisation des phases pour les huit suivants.
Rapports, exports et captures locaux : `tests/runs/exports-real/`. Cela ne constitue
pas encore un essai d’import humain des formats tabulés dans leurs logiciels cibles,
ni une validation de cette version sur Windows/macOS. Le SRT historique continue de passer ses tests de référence.
