# Tests et expériences

Tout le matériel de validation est regroupé ici, **séparé de l’application**.
Les rapports synthétiques et contrats sont conservés dans `docs/`.

```text
tests/
  test_*.py       Tests automatisés ; doubles d’inférence explicitement nommés
  paths.py        Emplacements communs, indépendants du répertoire courant
  tools/          Outils de validation et d’expérimentation
  fixtures/       Petites références JSON partageables (pas les transcriptions)
  experiments/    Paramètres et modèles figés des expériences
  sources/        Corpus locaux confidentiels ; seul README.md est versionné
  models/         Modèles expérimentaux locaux ; seul README.md est versionné
  runs/           Résultats et checkpoints locaux ; seul README.md est versionné
```

Exécuter les commandes depuis la racine du projet, avec le Python de l’environnement
choisi. Par exemple `.venv-gui/bin/python` sous Linux/macOS, ou
`.\.venv-gui\Scripts\python.exe` sous Windows.

## Tests automatisés, sans modèles

```bash
python -m unittest discover -s tests -v
```

Les tests du noyau ne nécessitent pas Qt. Les tests de fenêtre nécessitent l’extra
`.[gui]` et FFmpeg ; ils simulent l’inférence, mais utilisent de vrais threads,
processus et FFmpeg. Les cas du corpus privé sont ignorés s’il n’est pas présent.
Sous Linux sans affichage, définir `QT_QPA_PLATFORM=offscreen`.

La suite vérifie aussi les frontières de l’architecture, les règles `.gitignore`,
la non-publication de fichiers privés déjà indexés et les chemins des expériences.
Un corpus vide ne peut pas être figé comme une nouvelle référence par erreur.
Les tests de vérification des modèles utilisent de petits fichiers factices : cache
persistant, invalidation après changement, corruption, vérification forcée, cache
inaccessible et téléchargement vérifié avant mise en cache.

Les outils peuvent être lancés directement comme ci-dessus ou comme modules,
par exemple `python -m tests.tools.check_repository`.

## Vérifier les fichiers avant GitHub

```bash
python tests/tools/check_repository.py --list
```

Sans `.git`, un dépôt temporaire est utilisé **sans modifier le projet**. Avec un dépôt,
les fichiers indexés et les fichiers non ignorés sont examinés. Un fichier indexé malgré
`.gitignore`, un lien symbolique ou un fichier de plus de 5 Mio fait échouer le contrôle.
Un `.gitignore` n’efface pas un secret déjà commité : il faut alors traiter l’historique
et révoquer les identifiants concernés. Cet outil n’analyse pas le contenu à la recherche
de tous les secrets possibles ; relire les fichiers avant publication.

Les sources et résultats ne doivent jamais être ajoutés avec `git add -f`.
Le `MANIFEST.in` exclut également ces données des archives source Python ; les roues
Python ne contiennent que l’application.

## Corpus de référence SonalPi2

Emplacements locaux :

- `tests/sources/synth/audio/` : quatre MP3 fournis ;
- `tests/sources/synth/srt/` : leurs quatre SRT de référence ;
- `tests/sources/reel/` : entretien réel fourni, sans référence humaine figée ;
- `tests/sources/wamatipsia/` : WAV WamaTipsIA et coupes du diagnostic.

Les médias et les transcriptions ne sont pas dans Git. Seul l’inventaire avec
empreintes et caractéristiques est partageable : `tests/fixtures/corpus_manifest.json`.

```bash
python tests/tools/check_corpus.py
```

FFprobe est nécessaire. `--write-manifest` remplace explicitement l’inventaire : ne
l’utiliser qu’après avoir décidé de changer la référence, jamais automatiquement en CI.
Les chemins de l’inventaire sont relatifs à la racine du projet et utilisent `/`, y
compris sous Windows.

## Essai réel du corpus synthétique

Après préparation du backend et de ses trois modèles :

```bash
python tests/tools/run_corpus.py --threads 4 --output-dir tests/runs/synth-fluid-nouveau
```

`--case 4Etudiants` limite l’essai à un fichier. Les sorties sont dans `srt/`, les
checkpoints dans `work/`, et le rapport dans `report.json` du dossier choisi.
Les destinations existantes ne sont pas écrasées sans `--overwrite` explicite.
Les WER indicatifs comparent aux SRT synthétiques fournis, **pas à des annotations
humaines de validation**. Ils ne qualifient pas la précision sur entretiens réels.

Tests natifs ciblés, après compilation :

```bash
ctest --test-dir build/native -C Release -R '^(test_sas_merge|test_vad_segmenter|cli_version_long)$' --output-on-failure
```

## Essai bout-en-bout de la fenêtre avec le modèle réel du produit

```bash
python tests/tools/smoke_gui.py --output-dir tests/runs/gui-silence-nouveau
python tests/tools/smoke_gui.py --source chemin/entretien.wav --output-dir tests/runs/gui-parole-nouveau
```

Chaque dossier doit être **nouveau**. Sans source : trois secondes de silence, avec
zéro bloc attendu. Avec une source parlée : au moins un bloc attendu. Le test produit
un SRT, des captures et un rapport JSON. `--preview-only` capture la fenêtre sans modèle.
Sous Windows, utiliser le plugin Qt natif pour contrôler le rendu des polices.
Voir les [résultats de l’interface](../docs/interface-minimale.md).

## Expérience historique v3 / Ultra

Configuration : `tests/experiments/ultra-f16.lock.json`. Elle fige le runtime, le modèle
Ultra et son témoin v3, les quatre coupes et les facteurs de padding.

```bash
python tests/tools/compare_ultra.py --download-model --output-dir tests/runs/wamatipsia/comparaison-nouvelle
```

Le téléchargement place **v3 et Ultra dans `tests/models/`**, indépendamment du modèle
Fluid du produit. Il ne change pas `backend.lock.json` ni les anciens SRT.
Les coupes utilisent le même PCM et zéro ou 250 ms de silence de chaque côté, sans
seconde VAD, dictionnaire, forçage de langue ou LLM. Les temps incluent le chargement
natif ; ce ne sont pas des benchmarks isolés ni une mesure de qualité humaine.

Les anciens rapports et extraits restent sous `tests/runs/wamatipsia/`. Le WAV source
est dans `tests/sources/wamatipsia/WamaTipsIA.wav`, avec l’empreinte d’origine conservée.
Voir le [rapport Ultra](../docs/essai-ultra-gguf.md) et le [diagnostic Murmure](../docs/diagnostic-murmure.md).

## Expérience Ultra F16 / Fluid Speech Pro Q8

Configuration figée : `tests/experiments/fluid-q8.lock.json` (révisions, tailles,
SHA-256 des modèles, inventaire du corpus et coupes WamaTipsIA).
Depuis l’adoption de Fluid, Ultra est conservé dans `tests/models/` ; Fluid est partagé
avec le produit dans `models/` lorsqu’il est présent, sinon téléchargé dans `tests/models/`.
L’expérience ne change pas le backend du produit, les anciens checkpoints ou les anciens SRT.
Le [compte rendu du premier essai](../docs/essai-fluid-speech-pro.md) conserve ses résultats
historiques et distingue la recommandation initiale de la décision utilisateur ultérieure.

```bash
python tests/tools/compare_fluid.py --download-model --suite smoke --output-dir tests/runs/fluid-smoke-nouveau
python tests/tools/compare_fluid.py --suite all --output-dir tests/runs/fluid-comparison-nouvelle
```

`smoke` vérifie les 30 premières secondes du premier média synthétique avec les deux
modèles. `all` compare les quatre médias synthétiques complets et les quatre extraits
WamaTipsIA, sans padding. `corpus` et `wamatipsia` permettent de les exécuter séparément.
Chaque dossier de sortie doit être nouveau ; les corpus locaux sont nécessaires.

Les deux modèles utilisent le même pipeline CPU, quatre threads ASR, Silero, Nemotron
et les mêmes règles d’attribution/segmentation. Les rapports locaux conservent les
empreintes, les résultats JSON/SRT, les journaux, le texte des extraits et les temps.
Sous Linux, GNU time mesure aussi le pic RSS du processus ASR seul ; ailleurs cette
mesure reste `null`. Aucun mode « clean » n’est activé.

Le WER porte sur les SRT synthétiques fournis, pas une référence humaine indépendante.
Les extraits WamaTipsIA n’ont pas de WER faute de référence. La validation des
horodatages est structurelle, pas une mesure de leur justesse. Une exécution par
condition, Ultra toujours en premier : pas un benchmark statistique. La comparaison
change à la fois le modèle et sa précision (Ultra F16 / Fluid Q8_0).
Depuis la version 0.2.0, les deux modèles passent par le même filtrage ciblé de `<unk>`.
Les nouveaux rapports enregistrent version, politique de filtrage, nombre de mots natifs
et nombre d’omissions ; leurs scores SRT ne sont pas directement ceux du premier essai,
antérieur à ce filtrage. Les JSON natifs restent intacts.

## Photon : archive expérimentale, pas dépendance produit

Le test Photon CPU est documenté dans [son compte rendu](../docs/essai-photon-cpu.md).
Le venv historique `.venv` et les caches SDK existants ne sont ni supprimés ni distribués.
Les fichiers de téléchargement expérimentaux locaux sont dans `tests/models/photon-ultra-f16/` ;
le fichier `.part` qu’ils contiennent n’est pas un modèle complet exploitable.

Si l’expérience doit être répétée, utiliser un environnement **distinct et propre**,
installer Torch CPU puis `moondream==2.6.1` uniquement dans cet environnement. Ne pas
figer ses dépendances dans celles de l’application. L’extrait de référence est conservé
sous `tests/runs/wamatipsia/diagnostic-murmure/first-cut-exact.wav`.

## Migration de l’arborescence

Ancien emplacement → nouvel emplacement :

- `CorpusSynth/` → `tests/sources/synth/` ;
- `CorpusReel/` → `tests/sources/reel/` ;
- `runs/WamaTipsIA/WamaTipsIA.wav` → `tests/sources/wamatipsia/WamaTipsIA.wav` ;
- `runs/` → `tests/runs/` (sous-dossiers `synth`, `reel`, `wamatipsia`) ;
- `scripts/{check_corpus,run_corpus,compare_ultra,smoke_gui}.py` → `tests/tools/` ;
- `experiments/` → `tests/experiments/` ;
- ancien modèle v3 et téléchargement Photon de `models/` → `tests/models/`.

Les fichiers source et résultats ont été déplacés sans changer leur contenu ; leurs
SHA-256 ont été contrôlés. Les anciens journaux, JSON de provenance et scripts ponctuels
archivés conservent leurs chemins historiques. **Ne pas les réécrire pour simuler une
reprise compatible** : un média déplacé a une nouvelle provenance. Pour un nouvel essai,
utiliser un nouveau dossier de sortie/travail. Les outils partageables ont, eux, été adaptés.

### Vérifications après rangement

- 93 tests réussis sous Linux/WSL avec les corpus locaux.
- 93 tests réussis depuis l’archive source sans corpus (2 ignorés explicitement).
- 93 tests réussis sous Windows depuis une copie sans données privées (3 ignorés).
- Trois CTest natifs ciblés réussis sous Linux.
- Contrôle du corpus : quatre paires et empreintes d’origine conservées.
- Essai réel Ultra du cas `4Etudiants`, test de silence via la fenêtre et comparaison
  v3/Ultra du premier extrait WamaTipsIA rejoués depuis les nouveaux emplacements.
- Roue et archive source Python construites et inspectées : ni médias, ni transcriptions,
  ni poids de modèles, ni journaux privés embarqués.

Les logs de ce contrôle sont sous `tests/runs/layout-*`, donc ignorés par Git.
Les 310 fichiers de corpus/résultats et les quatre fichiers de modèles expérimentaux
ont été contrôlés avant/après déplacement. Aucun fichier n’a été supprimé.

Le workflow CI est dans `.github/workflows/desktop.yml`. Il utilise seulement des données
synthétiques créées à l’exécution, sauf déclenchement explicite des essais natifs avec modèles.
Aucun entretien utilisateur ne doit être publié comme artefact CI.
