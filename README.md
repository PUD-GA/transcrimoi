# transcrimoi

## Objectif

transcrimoi est conçu pour réaliser la **transcription et la diarisation sur une machine
modeste, uniquement avec son CPU**, sans GPU, compte utilisateur ni envoi du média vers
un service distant. Il transforme un fichier audio ou vidéo en document texte ou en
sous-titres, en distinguant les locuteurs. Neuf formats sont proposés ; le **SRT pour
SonalPi2 reste le choix par défaut**.

Tout le traitement est local et hors ligne une fois l’application installée. La
correction se fait ensuite dans l’outil choisi : transcrimoi n’embarque pas d’éditeur.
Les performances sur les ordinateurs les plus modestes restent à mesurer pendant le
pilote.

## Installation actuelle

Les paquets actuels sont des **préversions autonomes d’environ 1,1 à 1,2 Go**. Ils
contiennent l’application, les modèles, FFmpeg et le moteur CPU : il n’est pas nécessaire
d’installer Python, Torch, CUDA ou FFmpeg séparément. Télécharger le paquet correspondant
à la machine dans les pièces jointes (Assets) d’une
[Release de préversion](https://github.com/PUD-GA/transcrimoi/releases), lorsqu’elle est
publiée, puis suivre la procédure ci-dessous. Ne pas choisir les archives « Source code ».
Les archives de Release s’extraient une seule fois sur chaque plateforme.

### Windows — x86-64

1. Télécharger `transcrimoi-preview-…-windows-x86_64.zip` dans la Release.
2. Extraire ce ZIP une seule fois.
3. Dans le dossier extrait, lancer `Transcrimoi.exe` en conservant `_internal` à côté.

### Linux — x86-64

1. Télécharger `transcrimoi-preview-…-linux-x86_64.tar.gz` dans la Release.
2. Extraire cette archive une seule fois en préservant les permissions des exécutables.
3. Ouvrir le dossier `transcrimoi`, puis lancer `./transcrimoi`.

### macOS — Apple Silicon

1. Télécharger `transcrimoi-preview-…-macos-arm64.app.zip` dans la Release.
2. Extraire ce ZIP une seule fois avec l’Utilitaire d’archive de macOS, puis déplacer
   `transcrimoi.app` dans `Applications` si souhaité.
3. Ouvrir l’application. La préversion n’étant pas encore notariée, macOS peut demander
   de confirmer manuellement son ouverture dans les réglages de sécurité.

Ces préversions ne sont pas encore des installateurs signés. Le paquet macOS actuel ne
prend pas en charge les Mac Intel et la compatibilité des processeurs x86 sans AVX2 reste
à qualifier. Les paquets peuvent être générés depuis **GitHub Actions → Desktop CPU**
avec l’option `release` (brouillon à publier après vérification), ou `package` pour
conserver uniquement les artefacts Actions. Voir les
[instructions détaillées et limites](docs/paquets-autonomes.md).

## Langues

Le modèle Fluid Speech Pro annonce la prise en charge de **25 langues européennes**, avec
détection automatique de la langue : allemand, anglais, bulgare, croate, danois,
espagnol, estonien, finnois, français, grec, hongrois, italien, letton, lituanien,
maltais, néerlandais, polonais, portugais, roumain, russe, slovaque, slovène, suédois,
tchèque et ukrainien.

Cette liste provient de la
[fiche du modèle GGUF figé](https://huggingface.co/FluidVoice-Labs/fluid-speech-pro-gguf/blob/fee970d9ac83f6d236632d39b67cbec12f5a9020/README.md).
La version actuelle de transcrimoi a surtout été évaluée en français : il faut encore
qualifier concrètement les autres langues, accents et conditions d’enregistrement.

## Stack technique

- **Interface et orchestration :** Python 3.11+ et PySide6/Qt.
- **Préparation audio et vidéo :** FFmpeg, avec conversion locale vers le format de travail.
- **Reconnaissance vocale :** Fluid Speech Pro Q8_0 exécuté sur CPU.
- **Détection de parole :** Silero VAD.
- **Diarisation :** NVIDIA Nemotron-3-Diarization.
- **Moteur natif :** parakeet.cpp et GGML, sans serveur d’inférence, Torch ou CUDA.
- **Reprise et traçabilité :** checkpoints et résultats JSON locaux entre les phases.
- **Distribution :** paquets autonomes construits avec PyInstaller pour Windows, Linux
  et macOS.

## État actuel

- Une fenêtre PySide6/Qt, un média à la fois, annulation et reprise par phase.
- Neuf formats de sortie inspirés de Tadddam : texte brut, variantes avec locuteurs/temps, exports tabulés, ELAN tabulé, SRT SonalPi2, SRT simple et WebVTT.
- **Fluid Speech Pro Q8_0**, Silero et Nemotron exécutés avec parakeet.cpp/GGML.
- Aucun Photon, Torch ou SDK Moondream dans les dépendances du produit.
- Tests et pipeline natif Fluid sur silence validés en CI sous **Linux, Windows et macOS Apple Silicon** ; essais d’usage et machines propres restent à qualifier.
- Préversions autonomes avec modèles via un build manuel ; installateurs signés et distribution finale restent à préparer.

Les résultats et limites sont décrits dans la [validation de l’interface](docs/interface-minimale.md),
le [contrat SRT](docs/contrat-srt.md) et le [plan](Plan.md).
Un [essai séparé de Fluid Speech Pro Q8](docs/essai-fluid-speech-pro.md) confirme sa
compatibilité et une mémoire ASR réduite, sans gain de précision établi sur notre
petit corpus français. Fluid Q8 est néanmoins retenu par choix utilisateur, pour son
potentiel multilingue et sa mémoire réduite. Les gains multilingues annoncés en amont
ne constituent pas une validation de notre version GGUF Q8 sur ces langues.

## Organisation du projet

```text
transcrimoi/             Application : contrôleur, backend, exports et interface
scripts/                Préparation du runtime et packaging (pas les outils de test)
backend.lock.json       Runtime et trois modèles du produit, versions et SHA-256
pyproject.toml          Dépendances et points d’entrée de l’application
MANIFEST.in             Contenu de l’archive source, sans données locales
.github/workflows/      Validation automatisée Linux / Windows / macOS
docs/                   Architecture, contrats et rapports de validation
Plan.md                 Plan de construction

tests/                  Tout ce qui relève des tests et expériences
  test_*.py             Tests automatisés du noyau et de la fenêtre
  tools/                Contrôle du corpus, essais réels, comparaison Ultra, audit Git
  fixtures/             Petites références partageables, sans médias ni transcriptions
  experiments/          Configuration figée des expériences
  sources/              Corpus synthétique, réel et WamaTipsIA — LOCAL, ignoré par Git
  models/               Anciens modèles d’expérience — LOCAL, ignoré par Git
  runs/                 Résultats, journaux et checkpoints — LOCAL, ignoré par Git

models/                 Seulement les trois modèles du produit — LOCAL
vendor/                 Code tiers récupéré par le préparateur — LOCAL
build/                  Binaires et manifeste de compilation — LOCAL
dist/                   Futurs paquets à distribuer — LOCAL
.venv*/                 Environnements de développement — LOCAL
```

Le dossier `tests/sources/` désigne les **médias de test**, pas le code de l’application.
Le paquet distribué ne contient que les modules `transcrimoi` ; les outils de test ne
sont jamais importés par le produit. Voir le [guide des tests](tests/README.md).

## Développement depuis les sources

Prérequis développeur : **Python ≥ 3.11**, Git, CMake, compilateur C/C++ et FFmpeg dans le PATH.
Sous Windows : outils C++ de Visual Studio ; sous macOS : outils de compilation Xcode.

Linux/macOS, depuis la racine du projet :

```bash
python3 -m venv .venv-gui
.venv-gui/bin/python -m pip install -e '.[gui]'
.venv-gui/bin/python scripts/prepare_backend.py --download-models --jobs 4
.venv-gui/bin/python -m transcrimoi.gui
```

Windows, PowerShell, dans une copie locale du projet :

```powershell
python -m venv .venv-gui
.\.venv-gui\Scripts\python.exe -m pip install -e ".[gui]"
.\.venv-gui\Scripts\python.exe scripts/prepare_backend.py --download-models --jobs 4
.\.venv-gui\Scripts\pythonw.exe -m transcrimoi.gui
```

L’entrée installée `transcrimoi-gui` lance aussi la fenêtre, sans console sous Windows.
L’interface n’ajoute que **PySide6-Essentials et Shiboken**, pas WebEngine.
Pour comparer les formats, survolez le sélecteur ou les options de sa liste :
une infobulle présente le même échange fictif dans le format correspondant,
avec un délai d’apparition réduit à 150 ms.
Le venv historique `.venv` contient les dépendances de l’essai Photon : ne pas le réutiliser
pour fabriquer un paquet. Employer un environnement propre comme `.venv-gui`.

Le préparateur récupère le runtime et son sous-module figés, applique les correctifs
GGML par Git (sans Bash), compile les deux exécutables utiles et télécharge environ
**1,14 Go** de modèles. Taille et SHA-256 sont vérifiés après téléchargement, puis
la vérification réussie est mémorisée localement. Aucun serveur d’inférence, GPU,
conversion de modèle ou installation de Torch n’est nécessaire.

**Utiliser une copie de travail distincte par OS** : ne pas partager le cache CMake ni
`build/backend.json` entre Windows et Linux/WSL. Makefiles/Ninja et les sorties Release
multi-configuration sont pris en charge. Le build x86 testé utilise notamment AVX2 ;
la compatibilité avec tous les processeurs n’est pas encore qualifiée.

### Mise à jour depuis Ultra

Relancer `scripts/prepare_backend.py --download-models --jobs 4` : cela met à jour
`build/backend.json` et vérifie/télécharge les poids Fluid depuis leur dépôt officiel.
Les dépôts et révisions peuvent être spécifiques à chaque modèle dans `backend.lock.json` ;
Silero et Nemotron conservent leur source figée précédente.
Les anciens poids ne sont jamais supprimés automatiquement. Pour garder Ultra comme
témoin, le déplacer dans `tests/models/ultra-f16.gguf`.

La version 0.2.0 introduit aussi le filtrage ciblé décrit ci-dessous. Les anciens SRT
et checkpoints ne sont pas réécrits ; utiliser un nouveau dossier de travail en CLI.
L’interface choisit automatiquement une nouvelle identité de travail.

## Utilisation

Choisir ou déposer un média, choisir le **Format de sortie**, sa destination et cliquer **Transcrire**.
La destination proposée évite les fichiers existants ; la fenêtre ne permet pas de les écraser.
L’étape en cours et le temps écoulé sont affichés, sans pourcentage fictif.

**Annuler** conserve les phases validées. Relancer le même média réutilise les phases
compatibles ; une phase native interrompue repart du début. Les checkpoints/journaux
restent dans le dossier de données local Qt de l’application, accessible par le bouton
des journaux. Ils peuvent être volumineux et ne sont pas supprimés automatiquement.

À la fin, importer le SRT SonalPi2 ou ouvrir le document dans l’outil correspondant.
Les [neuf formats et leurs conventions](docs/formats-export.md) sont détaillés séparément.
Les identifiants de locuteurs
sont propres à chaque transcription, pas des identités persistantes entre entretiens.
Les mots non attribués directement sont résolus par le contexte temporel, sans distance
maximale ; en cas d’égalité, le locuteur précédent est retenu par choix explicite.
Les blocs restant sans locuteur après cette résolution n’ont pas de préfixe ; leur import
reste à qualifier. Le nombre de mots sans locuteur n’est pas une mesure de confiance.
Voir les [règles d’attribution](docs/contrat-srt.md#règles-de-génération).

### Autres formats et réexport

SRT SonalPi2 reste le défaut. Choisir **SRT simple** ou **WebVTT** supprime les étiquettes
de locuteur du document, pas la diarisation du pipeline. Les formats de texte avec
locuteurs regroupent les blocs consécutifs d’un même locuteur. Les formats à trois
colonnes et ELAN sont des exports tabulés, pas des documents propriétaires ; leur
import reste à qualifier dans les logiciels cibles.

Un changement de format seul permet de réutiliser les phases déjà validées dans la
fenêtre. Pour réexporter un résultat existant sans modèle ni nouvelle inférence :

```bash
python -m transcrimoi export chemin/travail/result.json \
  --output chemin/entretien-elan.tsv --format elan
```

La version 0.3.0 conserve les anciens résultats. Sa commande `export` peut lire les
`result.json` de la version 0.2.0 ; relancer `transcribe` avec une nouvelle version
demande en revanche un nouveau dossier de travail.

### Marqueurs non reconnus

Les tokens exactement égaux à `<unk>` sont omis avant attribution et segmentation,
sans remplacer ni inventer de texte. Les mots contenant ce marqueur et les autres
balises ne sont pas supprimés. Le fichier natif `asr.json` reste intact ; `result.json`
conserve `native_word_count`, `omitted_token_count` et la liste `omitted_tokens` avec
leurs temps, confiance éventuelle et raison. La fenêtre et la CLI signalent le nombre
d’omissions. Ce nettoyage ne récupère pas une parole manquante et n’est pas une preuve
de meilleure reconnaissance. Le même filtrage s’applique à tous les modèles.

### Vérification des modèles

Avant chaque tâche, l’application vérifie la présence et les caractéristiques des modèles
(taille, dates de modification/changement et identité du fichier). Si elles correspondent
à une vérification SHA-256 réussie, le contenu n’est pas relu. Un changement de fichier,
d’empreinte attendue ou un cache absent/invalide déclenche une vérification complète.
En mode développeur, les petits caches `.MODELE.gguf.verified.json` restent à côté des
modèles, hors Git. Dans une application gelée, ils vont dans le cache utilisateur,
jamais dans le bundle. Si le cache n’est pas inscriptible, la vérification fonctionne sans cache.

Ce raccourci détecte les changements ordinaires ; il ne remplace pas une vérification
complète contre une altération dissimulée. Pour forcer cette dernière :

```bash
python -m transcrimoi verify-backend
```

`--project-root chemin/runtime` permet de viser un autre runtime. Cette commande et
une préparation explicite avec `--download-models` relisent intégralement les modèles.
Les binaires restent vérifiés par SHA-256 avant chaque tâche ; les contrôles du média
source sont inchangés.

### CLI développeur

```bash
python -m transcrimoi transcribe chemin/entretien.mp3 \
  --output chemin/resultat.srt --work-dir chemin/travail --threads 4
```

- `--format` : `sonal-srt` (défaut), `txt`, `speaker-txt`, `speaker-tsv`, `timed-txt`, `nvivo`, `elan`, `vtt` ou `srt`.
- `--json-events` : événements par étape, format inclus dans l’événement final d’export.
- `Ctrl+C` : annulation, phases validées conservées.
- Même média, configuration et dossier de travail : reprise des phases compatibles.
- Un changement de modèle, version, source ou paramètres demande un nouveau dossier de travail.
- `--overwrite` est requis pour remplacer un document ; ne pas écraser une copie corrigée.
- Journaux : `ffmpeg.log`, `asr.log`, `diarization.log` dans le dossier de travail.

## Préversions autonomes

Les artefacts `test-report-OS` de la CI sont de petits rapports/captures, **pas des applications**.
Dans Actions → **Desktop CPU** → **Run workflow**, activer `package` pour compiler,
tester et produire un artefact `transcrimoi-preview-OS` avec Python, Qt, FFmpeg, moteur et modèles.
Activer plutôt `release` pour créer également une **Release en brouillon de préversion**
avec les archives finales directement téléchargeables ; cette option implique `package`
et les tests natifs. Après réussite des trois OS, vérifier le brouillon dans **Releases**,
puis le publier manuellement lorsque la diffusion est autorisée.
Les archives sont un `.app.zip` macOS, un ZIP Windows compressé ou un `.tar.gz` Linux,
avec taille, SHA-256 et rapport de diagnostic ; leur poids est de l’ordre du Go.
Les artefacts Actions restent sept jours ; les pièces jointes de Release n’ont pas cette
expiration. Pour les anciens artefacts Actions uniquement, Linux/macOS demandent encore
d’extraire l’enveloppe ZIP GitHub avant l’archive finale.

Ce sont des paquets de validation non signés pour distribution, pas des installateurs
finaux. Consulter les [instructions, limites et notices](docs/paquets-autonomes.md).
La signature/notarisation, l’audit des licences et les essais sur machines propres
restent nécessaires avant distribution publique.

## Tests et préparation de GitHub

```bash
python -m unittest discover -s tests -v
python tests/tools/check_repository.py --list
```

Le second contrôle vérifie les fichiers publiables **sans initialiser Git dans le projet**.
Si un dépôt existe, il détecte aussi les fichiers déjà indexés malgré `.gitignore`.
Les corpus, transcriptions (dont TXT/TSV), résultats, modèles, environnements, certificats et fichiers
`.env` sont exclus. Les petites références JSON et les README des dossiers locaux restent partageables.
Ce contrôle ne remplace pas une relecture des fichiers ni un outil de détection de secrets.

Les tests de fenêtre demandent Qt et FFmpeg, mais pas de modèle. Les essais avec de
vrais modèles, le corpus privé et les expériences sont documentés dans [tests/README.md](tests/README.md).
Le workflow `.github/workflows/desktop.yml` teste les trois OS. La
[validation native Fluid](https://github.com/PUD-GA/transcrimoi/actions/runs/43644971974)
a réussi sur les trois ; son silence synthétique ne remplace pas un essai d’usage sur Mac.

## Limites avant distribution

- Valider macOS, les machines modestes et l’installation sur machines propres.
- Relire/importer les nouveaux SRT dans SonalPi2 et tester un entretien de deux heures.
- La vidéo de 1 h 22 a été traitée, sans qualification humaine globale de la qualité.
- La VAD native charge encore l’audio complet en mémoire.
- Vérifier les décalages audio/vidéo, chevauchements, bruits et fichiers sans parole.
- Qualifier les préversions autonomes, fabriquer les installateurs signés, compléter les notices et choisir la licence du projet.

Aucune dépendance à SonalPi2 ou noScribe. Respecter les licences du runtime, des modèles,
de Qt et de FFmpeg : [composants tiers](docs/composants-tiers.md).
