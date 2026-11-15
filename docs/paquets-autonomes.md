# Préversions autonomes de transcrimoi

**Paquets de validation, pas des releases qualifiées.** Ils ne sont ni signés avec une
identité éditeur, ni notariés sur macOS. Leur installation sur machines propres reste
à qualifier ; le projet n’a pas encore choisi sa licence. L’inventaire des notices ne
remplace pas l’audit de redistribution des bibliothèques, de Qt et du build FFmpeg.
Ne pas annoncer ces préversions comme des installateurs prêts à distribuer.

## Première validation des paquets

Le [build manuel avec packaging](https://github.com/PUD-GA/transcrimoi/actions/runs/43646231299)
a réussi sur les trois OS. Les rapports du binaire gelé confirment Qt, FFmpeg et Fluid
sur trois secondes de silence (zéro bloc) : macOS arm64, Windows AMD64 et Linux x86-64.
Les artefacts `transcrimoi-preview-*` pèsent environ 1,09 Go (macOS), 1,12 Go
(Windows) et 1,19 Go (Linux), modèles inclus. La suite de tests atteint 136 cas sous Linux local.

Le paquet Linux local a également été extrait hors du dépôt et testé avec un `PATH`
vide et sans environnement Python actif. Aucun cache n’est écrit dans ses ressources.
Ces vérifications ne sont **pas** des essais sur machines propres, une qualification de
la parole réelle dans les paquets, ni une autorisation de redistribution publique.

## Deux types d’artefacts GitHub

- `test-report-OS` : captures, rapports JSON et journaux ; quelques dizaines de Ko.
  Ce n’est **pas une application**.
- `transcrimoi-preview-OS` : application autonome avec Python, Qt, FFmpeg, les deux
  exécutables natifs et les trois modèles du produit (environ 1,14 Go de poids seuls).
  Sous Windows, le contenu de l’application est envoyé directement dans l’artefact :
  le ZIP téléchargé ne contient donc plus un second ZIP. Linux conserve un `.tar.gz`
  pour les permissions et macOS un `.app.zip` pour la structure du bundle. Aucune
  dépendance Torch/Photon ni besoin de Python, compilateur, réseau ou FFmpeg
  préinstallés pour l’utiliser. Les bibliothèques système de l’OS restent nécessaires.

Les artefacts restent sept jours pour les préversions volumineuses ; aucune release
GitHub n’est créée. Ne pas confondre un artefact de tests avec le paquet de l’application.

## Lancer les validations

GitHub → Actions → **Desktop CPU** → **Run workflow**, branche `main` :

1. `native=true`, `package=false` : compiler et tester les vrais modèles sur les trois OS.
2. `package=true` : implique la validation native, puis construit, teste et archive
   l’application autonome sur chaque OS. Les poids sont téléchargés une fois par job.

Un push ou une pull request ne lance que les tests simulés et la capture, sans modèles
ni packaging. Un paquet n’est archivé qu’après réussite du diagnostic du binaire gelé.

## Ouvrir une préversion

Ouvrir le paquet correspondant à la plateforme :

- **Windows x86-64** : extraire une seule fois le ZIP téléchargé, puis lancer
  `Transcrimoi.exe`. Conserver `_internal/` à côté du programme.
- **macOS Apple Silicon** : extraire l’artefact GitHub, puis le `.app.zip` en préservant les liens symboliques,
  puis ouvrir `transcrimoi.app`. Finder peut refuser cette application non notariée ;
  pour un essai de confiance, utiliser la procédure d’autorisation manuelle de macOS.
  Aucune désactivation globale de Gatekeeper n’est nécessaire ni recommandée.
  Cette matrice ne produit pas de paquet Mac Intel.
- **Linux x86-64** : extraire l’artefact GitHub, puis le `.tar.gz` en conservant les permissions et les liens,
  lancer `transcrimoi/transcrimoi`. Le paquet CI est construit sur Ubuntu 22.04 ; la
  compatibilité avec d’autres distributions, glibc, affichages et CPU reste à tester.

Ne pas déplacer un exécutable seul hors de son dossier. Les paquets utilisent le
runtime embarqué, pas le dépôt source. Leurs checkpoints et journaux vont dans les
données locales de l’utilisateur. Les caches de vérification des modèles vont dans
le cache utilisateur, **jamais dans le bundle**, pour préserver ses ressources/signatures
et permettre l’exécution depuis un dossier non inscriptible.

Pour rejouer le diagnostic embarqué, fournir un dossier de sortie **nouveau** :

```text
transcrimoi --self-test chemin/nouveau-diagnostic
```

Sur macOS, l’exécutable est `transcrimoi.app/Contents/MacOS/transcrimoi`.
Le diagnostic ouvre/capture Qt, traite trois secondes de silence avec FFmpeg et les
vrais modèles, et exige zéro bloc. Les rapports et captures n’utilisent aucun média
utilisateur. Il ne prouve pas la qualité d’une transcription parlée, ni l’ensemble des
interactions de la fenêtre ou le fonctionnement sur une machine propre.

## Construire localement

Préparer d’abord le moteur et les modèles, puis utiliser un environnement propre :

```bash
python -m pip install -e '.[gui,package]'
python scripts/prepare_backend.py --download-models --jobs 3
python scripts/build_desktop.py
```

Sous Windows, employer `".[gui,package]"`. Le build demande les outils habituels
Git/CMake/C++ et FFmpeg. `--ffmpeg` permet de désigner le vrai exécutable, pas un shim.
`--work-dir` et `--output-dir` permettent de choisir de nouveaux dossiers pour rejouer
sans écraser un paquet précédent. Résultats par défaut : `dist/desktop/` ; travail et
rapport de diagnostic : `build/desktop/`.

PyInstaller collecte uniquement l’application, le runtime et les notices sélectionnés.
Ni corpus, ni résultats privés, ni modèles expérimentaux, ni environnements de
développement ne sont ajoutés. Les empreintes des exécutables natifs sont recalculées
après les éventuelles modifications de chargement/signatures de PyInstaller.
L’archive est construite après le diagnostic ; sa taille et son SHA-256 sont enregistrés.

## Notices et distribution restante

Les préversions contiennent un dossier `notices/` : attributions des modèles,
licences figées des modèles et du runtime, licences disponibles de Qt/Python,
configuration et licence annoncées par FFmpeg. Les licences de dépendances système
collectées automatiquement ne sont pas garanties exhaustives. Les versions du build
et les références des poids sont conservées avec le runtime.

Avant distribution publique : choisir la licence du projet, compléter les notices et
les obligations de source/reconstruction/remplacement des composants, auditer FFmpeg
et ses codecs/bibliothèques, signer les paquets et notarier macOS, qualifier les CPU et
les machines propres, puis fabriquer les vrais installateurs Windows/macOS/Linux.
Voir aussi [les composants tiers](composants-tiers.md).
