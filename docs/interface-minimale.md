# Interface minimale — CPU, sans Photon

> **Version actuelle :** Fluid Speech Pro Q8_0 remplace Ultra par choix utilisateur.
> Les tokens exactement égaux à `<unk>` sont omis avant attribution/segmentation,
> tracés dans `result.json` et signalés à la fin, sans toucher aux sorties natives.
> Les résultats Linux/Windows du tableau historique ci-dessous concernent Ultra ;
> ils ne constituent pas une validation de Fluid sur Windows ou macOS.

> Les résultats ci-dessous précèdent le rangement des tests. Les chemins de consultation
> ont été actualisés ; les journaux et résultats historiques n’ont pas été réécrits.
> Voir l’[organisation actuelle et les commandes de test](../tests/README.md).

## Périmètre livré

Une seule fenêtre Qt (`transcrimoi/gui.py`) :

- choix ou dépôt d’un seul média audio/vidéo ;
- destination SRT proposée à côté du média, avec un nom libre si un SRT existe ;
- bouton Transcrire, étape en cours, indicateur indéterminé et temps écoulé ;
- Annuler, puis reprise des phases compatibles en relançant le même média ;
- accès au dossier du SRT, aux journaux et aux détails d’une erreur ;
- message explicite si aucune parole n’a été détectée.

Aucun éditeur, lecteur, sélecteur de langue, de nombre de locuteurs ou de modèle.
La fenêtre n’expose aucune option d’écrasement. Le noyau protège aussi la publication
contre la création concurrente d’un SRT par une autre application.
Pendant le traitement, les champs sont désactivés. La fermeture demande confirmation,
annule les processus puis attend leur arrêt sans bloquer la boucle graphique.

La fenêtre lance le contrôleur existant dans un thread Qt. FFmpeg, l’ASR et la
diarisation restent des processus natifs séparés ; le noyau n’importe pas Qt.
Les événements remontent par signaux, sans accès aux widgets depuis le thread de travail.
Les binaires sont vérifiés par SHA-256 avant chaque tâche. Pour les modèles, une
vérification SHA-256 réussie est mémorisée à côté du fichier : les tâches suivantes
contrôlent sa présence, sa taille, ses dates et son identité sans relire son contenu.
Un changement ou un cache absent/invalide déclenche une nouvelle vérification complète.
Après téléchargement, le contenu est toujours vérifié avant publication et mise en cache.
`python -m transcrimoi verify-backend` force la relecture complète des modèles.
Ce cache local est une optimisation, pas une protection contre une altération hostile ;
s'il ne peut pas être écrit, l'application revérifie intégralement les modèles.
Voir les [règles de vérification](../README.md#vérification-des-modèles).

## Modèle et environnement

`backend.lock.json` référence désormais **Fluid Speech Pro GGUF Q8_0**, depuis le dépôt
officiel FluidVoice-Labs figé et vérifié par SHA-256. Silero, Nemotron et les règles
actuelles d’attribution/segmentation restent utilisés, avec filtrage ciblé de `<unk>`
avant attribution. Aucun padding supplémentaire. Voir le [compte rendu Fluid](essai-fluid-speech-pro.md).
Les anciens SRT et checkpoints ne sont pas réécrits ; la version et la politique de
filtrage changent l’identité de reprise.

Les expériences conservent leurs témoins v3 et Ultra dans `tests/models/`, indépendants
du modèle par défaut. Seuls Fluid, Silero et Nemotron sont nécessaires au produit.

L’interface dépend uniquement de **PySide6-Essentials et Shiboken6**, sans WebEngine.
L’environnement Linux propre `.venv-gui` contient ces deux paquets et transcrimoi,
sans Torch, Moondream ni Kestrel. Ne pas distribuer le venv Photon expérimental.
Les versions utilisées ici sont Qt/PySide6-Essentials 6.12.0, Python 3.12.3 sous
Linux/WSL et Python 3.13.5 sous Windows.

## Préparation et lancement

C’est encore un **prototype développeur**, pas un installateur autonome. Il faut
Python ≥ 3.11, Git, CMake, un compilateur C++ et FFmpeg. Sous Windows, les outils
C++ de Visual Studio conviennent ; sous macOS, les outils Xcode sont à installer.

Utiliser **une copie de travail par OS** : un cache CMake ou un manifeste de binaires
Windows n’est pas réutilisable sous Linux/WSL, ni inversement. Les chemins des binaires
sont maintenant relatifs à la racine du runtime dans `build/backend.json`.

Linux/macOS, depuis la racine du projet :

```bash
python3 -m venv .venv-gui
.venv-gui/bin/python -m pip install -e '.[gui]'
.venv-gui/bin/python scripts/prepare_backend.py --download-models --jobs 4
.venv-gui/bin/python -m transcrimoi.gui
```

Windows, PowerShell, depuis une copie du projet sur un disque Windows :

```powershell
python -m venv .venv-gui
.venv-gui\Scripts\python.exe -m pip install -e ".[gui]"
.venv-gui\Scripts\python.exe scripts/prepare_backend.py --download-models --jobs 4
.venv-gui\Scripts\pythonw.exe -m transcrimoi.gui
```

FFmpeg doit être dans le PATH. La fenêtre accepte aussi `bin/ffmpeg[.exe]` dans le
runtime. L’entrée installée `transcrimoi-gui` lance la fenêtre sans console sous Windows.
`--project-root` permet de désigner un runtime préparé ailleurs.

Sur la machine de développement actuelle, `tests/runs/transcrimoi-Windows.lnk` relance
le prototype Windows sans console. Le moteur compilé et son environnement Qt se
trouvent dans `%TEMP%/transcrimoi-native-windows` et `%TEMP%/transcrimoi-gui-tests`.
Ce raccourci de test n’est pas un installateur et cesse de fonctionner si ces dossiers
sont nettoyés. Une fenêtre native Windows a été laissée ouverte pour l’essai manuel.

La préparation applique les correctifs GGML figés par `git apply`, de façon idempotente,
avant CMake. Son application Bash automatique est désactivée : Windows peut sinon
sélectionner par erreur le Bash de WSL, qui ne comprend pas ses chemins `C:/…`.
Les générateurs CMake à configuration unique et les sorties Release multi-configuration
sont pris en charge.

Les checkpoints et journaux sont conservés sous le dossier de données **local** Qt de
l’application (`AppLocalDataLocation/work`). L’identité dépend du contenu du média,
du moteur, des modèles et des paramètres, pas du nom du SRT. Les phases interrompues
repartent du début ; celles qui sont achevées et compatibles sont réutilisées.
Ce dossier peut devenir volumineux et n’est pas nettoyé automatiquement.

## Tests effectués

| Vérification | Linux/WSL x86-64 | Windows 11 x86-64 | macOS |
|---|---|---|---|
| Suite Python + fenêtre | 84 tests, succès | 84 tests, succès, 3 ignorés | Non exécutée ici |
| Compilation native figée | Succès, GCC | Succès, MSVC 2022 Release | Non exécutée ici |
| CTest natifs ciblés | 3/3 succès | 3/3 succès | Non exécutés ici |
| Fenêtre → vrai Ultra → SRT, silence 3 s | Zéro bloc, message explicite | Zéro bloc, message explicite | Non exécutée ici |
| Fenêtre → vrai Ultra → SRT, parole 30 s | 8 blocs, aucun mot sans locuteur | 8 blocs, aucun mot sans locuteur | Non exécutée ici |

Les trois tests ignorés dans la dernière copie Windows sont les deux tests du corpus
privé (non copié dans ce workspace) et le test de groupe de processus POSIX. Un passage
Windows précédent avait aussi vérifié le corpus privé depuis le partage WSL.

La suite de fenêtre utilise de vrais threads/processus et FFmpeg, mais un **double
d’inférence explicitement nommé**. Elle couvre succès, silence, Unicode, destination
personnalisée, protection contre l’écrasement, annulation/reprise, erreur du moteur,
erreur longue, fermeture en cours de tâche et dépôt d’un fichier unique. Les tests
du backend contrôlent aussi l’adoption d’Ultra et l’application idempotente des correctifs.

Les essais bout-en-bout utilisent, eux, les **vrais modèles**. L’extrait parlé correspond
aux 30 premières secondes de `tests/sources/synth/audio/1Coordinatrice.mp3`.
Le SRT Linux et le SRT Windows ont la même empreinte sur cet extrait :

```text
dc92c0d9f3111fcf23a71c3dd28ec4f99676ada95a25c2bbcc8fa06560d5d79f
```

Ce résultat court ne démontre ni une parité générale des OS, ni la qualité globale de
l’ASR/diarisation. Les durées sont celles d’une station de développement puissante,
pas un benchmark ni une promesse de vitesse sur ordinateur modeste.

Artefacts locaux (exclus du suivi de code) :

- `tests/runs/gui-linux-tests-final.log`, `tests/runs/gui-windows-tests-final.log` ;
- `tests/runs/gui-native-speech-final/` et `tests/runs/gui-native-silence-final/` : Linux ;
- `tests/runs/gui-native-windows-speech/` et `tests/runs/gui-native-windows-silence-v2/` : Windows ;
- chaque dossier d’essai contient rapport JSON, captures et SRT.

Un premier essai Windows avait échoué parce que son cache était placé sur le partage
UNC WSL, dont le verrouillage `msvcrt` n’était pas disponible. Les essais suivants ont
utilisé un cache sur le disque Windows, comme le fait la fenêtre par défaut. Les chemins
réseau et systèmes de fichiers sans liens physiques/verrouillage restent à qualifier.
Les captures Windows sont faites avec le plugin natif : le plugin `offscreen` pouvait
produire des carrés à la place des caractères, sans que le rendu du bureau soit défectueux.

## Rejouer et tester les trois OS

```bash
python -m unittest discover -s tests -v
python tests/tools/smoke_gui.py --output-dir tests/runs/gui-silence-nouveau
python tests/tools/smoke_gui.py --source chemin/entretien.wav --output-dir tests/runs/gui-parole-nouveau
```

Chaque dossier de sortie doit être nouveau. Sans `--source`, le test génère trois secondes
de silence. Avec un média parlé, il exige au moins un bloc. `--preview-only` capture la
fenêtre sans modèle. Sous Linux sans affichage, utiliser `QT_QPA_PLATFORM=offscreen`.
Pour la suite de fenêtre, Qt et FFmpeg sont requis ; les tests privés du corpus sont
explicitement ignorés lorsqu’il est absent.

`.github/workflows/desktop.yml` prévoit une matrice Ubuntu, Windows et macOS :

1. installation de Qt/FFmpeg et tests du noyau/de la fenêtre sans modèles ;
2. capture de la fenêtre ;
3. sur déclenchement manuel avec `native=true`, compilation du moteur, téléchargement
   des modèles vérifiés et essai bout-en-bout du silence avec le modèle réel du produit.

Ce workflow est fourni mais **n’a pas été exécuté ici sur GitHub**. Il ne remplace pas
un essai d’usage sur un Mac. L’architecture réelle est enregistrée dans chaque rapport ;
Apple Silicon et Mac Intel ne doivent pas être présumés qualifiés tous les deux.

## Validation native Fluid et préversions

Après les essais historiques ci-dessus, la
[CI native Fluid](https://github.com/PUD-GA/transcrimoi/actions/runs/43644971974) a réussi
sous Ubuntu, Windows et macOS Apple Silicon : compilation, tests CTest ciblés et
fenêtre → Fluid réel → SRT vide sur silence. Ce n’est pas un essai d’usage complet sur Mac.

Le workflow peut désormais fabriquer des préversions PyInstaller avec modèles inclus,
et exécute leur diagnostic gelé avant archivage. Les caches des modèles vont dans le
cache utilisateur, pas dans le bundle. Voir les [paquets autonomes](paquets-autonomes.md).
Signature, notarisation, notices complètes et qualification sur machines propres restent ouvertes.

## Restant avant distribution

- validation macOS, essais manuels sur les trois OS et sur ordinateurs modestes ;
- essai d’un entretien long depuis la fenêtre, annulation réelle et import SonalPi2 ;
- qualification des processeurs : le build x86 actuel utilise notamment AVX2 ;
- paquet autonome propre à chaque OS, Python/Qt/FFmpeg et bibliothèques natives inclus ;
- contrôle des licences/notices, signature Windows, signature/notarisation macOS ;
- tests sur machines propres sans Python ni outils de compilation.

L’interface portable est livrée ; les installateurs et la validation complète des trois
plateformes ne sont pas présentés comme terminés.
