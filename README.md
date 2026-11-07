# transcrimoi

Transcription et diarisation **locales sur CPU** d’un média vers un **SRT pour SonalPi2**.
La correction se fait dans SonalPi2 : transcrimoi n’embarque pas d’éditeur.

## État actuel

- Une fenêtre PySide6/Qt, un média à la fois, annulation et reprise par phase.
- **Parakeet Ultra F16**, Silero et Nemotron exécutés avec parakeet.cpp/GGML.
- Aucun Photon, Torch ou SDK Moondream dans les dépendances du produit.
- Traitement et interface essayés sous **Linux/WSL et Windows 11** ; macOS reste à valider.
- Prototype développeur : les applications autonomes et installateurs restent à fabriquer.

Les résultats et limites sont décrits dans la [validation de l’interface](docs/interface-minimale.md),
le [contrat SRT](docs/contrat-srt.md) et le [plan](Plan.md).

## Organisation du projet

```text
transcrimoi/             Application : contrôleur, backend, SRT et interface
scripts/                Préparation du runtime (pas les outils de test)
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
**1,64 Go** de modèles. Taille et SHA-256 sont vérifiés. Aucun serveur d’inférence,
GPU, conversion de modèle ou installation de Torch n’est nécessaire.

**Utiliser une copie de travail distincte par OS** : ne pas partager le cache CMake ni
`build/backend.json` entre Windows et Linux/WSL. Makefiles/Ninja et les sorties Release
multi-configuration sont pris en charge. Le build x86 testé utilise notamment AVX2 ;
la compatibilité avec tous les processeurs n’est pas encore qualifiée.

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
Les blocs sans attribution certaine n’ont pas de préfixe ; leur import reste à qualifier.

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
Le workflow `.github/workflows/desktop.yml` prévoit les trois OS ; il n’a pas été exécuté
ici sur GitHub et ne constitue pas encore une validation macOS.

## Limites avant distribution

- Valider macOS, les machines modestes et l’installation sur machines propres.
- Relire/importer les nouveaux SRT dans SonalPi2 et tester un entretien de deux heures.
- La vidéo de 1 h 22 a été traitée, sans qualification humaine globale de la qualité.
- La VAD native charge encore l’audio complet en mémoire.
- Vérifier les décalages audio/vidéo, chevauchements, bruits et fichiers sans parole.
- Fabriquer les paquets autonomes, assembler les notices et choisir la licence du projet.

Aucune dépendance à SonalPi2 ou noScribe. Respecter les licences du runtime, des modèles,
de Qt et de FFmpeg : [composants tiers](docs/composants-tiers.md).
