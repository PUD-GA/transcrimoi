# transcrimoi

Transcription et diarisation **locales sur CPU** d’un média vers un **SRT pour SonalPi2**.
La correction se fait dans SonalPi2 : transcrimoi n’embarque pas d’éditeur.

## État actuel

- Une fenêtre PySide6/Qt, un média à la fois, annulation et reprise par phase.
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
transcrimoi/             Application : contrôleur, backend, SRT et interface
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

## Préparer et lancer le prototype

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

Choisir ou déposer un média, choisir le SRT de destination et cliquer **Transcrire**.
La destination proposée évite les fichiers existants ; la fenêtre ne permet pas de les écraser.
L’étape en cours et le temps écoulé sont affichés, sans pourcentage fictif.

**Annuler** conserve les phases validées. Relancer le même média réutilise les phases
compatibles ; une phase native interrompue repart du début. Les checkpoints/journaux
restent dans le dossier de données local Qt de l’application, accessible par le bouton
des journaux. Ils peuvent être volumineux et ne sont pas supprimés automatiquement.

À la fin, importer manuellement le SRT dans SonalPi2. Les identifiants de locuteurs
sont propres à chaque transcription, pas des identités persistantes entre entretiens.
Les mots non attribués directement sont résolus par le contexte temporel, sans distance
maximale ; en cas d’égalité, le locuteur précédent est retenu par choix explicite.
Les blocs restant sans locuteur après cette résolution n’ont pas de préfixe ; leur import
reste à qualifier. Le nombre de mots sans locuteur n’est pas une mesure de confiance.
Voir les [règles d’attribution](docs/contrat-srt.md#règles-de-génération).

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

- `--json-events` : événements par étape.
- `Ctrl+C` : annulation, phases validées conservées.
- Même média, configuration et dossier de travail : reprise des phases compatibles.
- Un changement de modèle, version, source ou paramètres demande un nouveau dossier de travail.
- `--overwrite` est requis pour remplacer un SRT ; ne pas écraser une copie corrigée.
- Journaux : `ffmpeg.log`, `asr.log`, `diarization.log` dans le dossier de travail.

## Préversions autonomes

Les artefacts `test-report-OS` de la CI sont de petits rapports/captures, **pas des applications**.
Dans Actions → **Desktop CPU** → **Run workflow**, activer `package` pour compiler,
tester et produire un artefact `app-preview-OS` avec Python, Qt, FFmpeg, moteur et modèles.
L’option implique les tests natifs. Les archives sont un `.app.zip` macOS, un ZIP Windows
ou un `.tar.gz` Linux, avec taille et empreinte SHA-256 ; leur poids est de l’ordre du Go,
pas de quelques Ko. Elles restent sept jours et aucune release n’est publiée.

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
Les corpus, transcriptions, résultats, modèles, environnements, certificats et fichiers
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
