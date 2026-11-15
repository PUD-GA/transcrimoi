# Plan de construction — transcrimoi, transcription locale vers SonalPi2

**Version 2.5 — Fluid Q8 CPU et neuf formats de restitution**
**Produit :** une application de bureau locale de transcription, SRT SonalPi2 par défaut et huit autres restitutions inspirées de Tadddam.
**Principe :** transcrimoi transcrit et distingue les locuteurs ; SonalPi2 assure la relecture, la correction et le travail d’analyse.  
**Statut :** Fluid Speech Pro Q8_0 est le modèle ASR par défaut par choix utilisateur ; les tokens exactement égaux à `<unk>` sont désormais omis du SRT avec traçabilité. Les gains multilingues de notre version GGUF restent à qualifier. Une fenêtre PySide6/Qt a été ajoutée ; le parcours complet avec Ultra réel a été essayé sous Linux/WSL et Windows 11 sur silence et sur un extrait parlé. La CI native Fluid a depuis réussi sous Linux, Windows et macOS Apple Silicon sur silence ; les essais d’usage macOS restent à qualifier. Les essais antérieurs incluent WamaTipsIA (1 h 22 min 48 s). L’import des nouveaux résultats dans SonalPi2, la qualité globale, les entretiens de deux heures et les installateurs autonomes restent à qualifier. Voir aussi la [validation de l’interface](docs/interface-minimale.md). Voir les rapports [M0–M2](docs/validation-m1-m2.md), [Ultra GGUF](docs/essai-ultra-gguf.md), [Photon CPU](docs/essai-photon-cpu.md) et le [guide développeur](README.md).

## Organisation du dépôt

Le produit reste dans `transcrimoi/` ; `scripts/` prépare son runtime et ses préversions autonomes. Les tests, leurs
outils, configurations d’expérience et petites fixtures sont regroupés dans `tests/`.
Les corpus (synthétique, réel et WamaTipsIA), les modèles expérimentaux et les résultats
sont respectivement dans `tests/sources/`, `tests/models/` et `tests/runs/`, ignorés par Git.
Les rapports rédigés restent dans `docs/`. Voir le [guide des tests](tests/README.md).

## 1. Décision centrale

Le parcours cible est :

**Choisir un audio ou une vidéo → choisir le format → lancer le traitement → enregistrer le document → l’ouvrir dans l’outil cible.**

Le parcours SRT SonalPi2 reste le défaut et conserve son contrat. À la demande de
l’utilisateur, la version 0.3.0 ajoute les [neuf formats proposés par Tadddam](docs/formats-export.md),
sans reprendre son code ni son moteur. Le JSON interne peut être réexporté en CLI sans
nouvelle inférence ; le choix d’export ne change pas l’identité des phases natives.

Il n’y a pas d’éditeur dans transcrimoi : ni lecteur audio synchronisé, ni correction de texte, ni renommage ou réattribution manuelle des locuteurs. Ces fonctions appartiennent à SonalPi2.

noScribe reste une référence éventuelle de qualité, pas une base applicative à reprendre. Aucune dépendance à noScribe ou noScribeEditor n’est nécessaire. Aucun audit détaillé de ces codebases ni de celle de SonalPi2 n’est un préalable : le raccord se valide par un fichier témoin et un essai d’import.

La simplification porte sur le produit et son intégration, pas sur la qualité du traitement des entretiens longs.

### Historique — adoption initiale d’Ultra GGUF

**Orientation initiale, remplacée par Fluid ci-dessous : `moondream/parakeet-ultra` en GGUF avec `parakeet.cpp` / GGML, sur CPU, sans Photon ni Torch dans le produit distribué.**

- **Mélange français/anglais :** Ultra semble résoudre le défaut observé avec Parakeet v3 sur WamaTipsIA. Les quatre extraits comparés restent en français, avec ou sans ajout de silence. Le SRT complet produit avec Ultra, sans padding, ne présente plus ce mélange dans les passages contrôlés ; la recherche de marqueurs anglais courants sur ses 994 blocs n’en a pas retrouvé. Ce contrôle textuel ne remplace pas une écoute intégrale et ne garantit pas l’absence de toute erreur.
- **Photon non nécessaire au produit :** sur le premier extrait de 27,372 s, Photon CPU et Ultra F16 GGUF produisent exactement le même texte. Ce résultat conforte le choix GGML, sans démontrer une parité générale des moteurs ni permettre de comparer directement leurs temps mesurés différemment.
- **Périmètre technique maintenu :** conserver le contrôleur Python léger, les processus natifs, Silero, Nemotron F16 et la sortie SRT vers SonalPi2. Photon et ses dépendances ne servent que de référence expérimentale de développement ; aucune dépendance à Photon, au SDK Moondream ou à Torch n’est ajoutée au paquet utilisateur.
- **Validation restante :** relire le SRT complet, vérifier son import et les attributions indéterminées dans SonalPi2, puis évaluer d’autres entretiens français et des CPU modestes avant de qualifier le choix. Le test de 1 h 22 ne valide pas encore la cible de deux heures.

Les constats et les artefacts sont détaillés dans les rapports [Ultra GGUF](docs/essai-ultra-gguf.md) et [Photon CPU](docs/essai-photon-cpu.md). **Adoption initiale :** Ultra F16 avait été figé avec l’empreinte vérifiée lors de l’expérience ; il est maintenant conservé dans `tests/models/`. Le témoin v3 est figé séparément dans `tests/experiments/ultra-f16.lock.json`, pour que l’expérience historique reste une véritable comparaison. Les anciens résultats et checkpoints ne sont pas réécrits.

### Décision actuelle — Fluid Speech Pro Q8_0

Le [premier essai Fluid Q8 / Ultra F16](docs/essai-fluid-speech-pro.md) utilise le même
runtime CPU sans changer le produit. Fluid fonctionne et réduit le pic mémoire ASR,
mais ne montre pas de gain de précision sur les quatre médias synthétiques français.
Fluid Q8_0 est néanmoins adopté par choix utilisateur pour son potentiel multilingue
et sa mémoire réduite, sans prétendre que ses benchmarks amont prouvent un gain dans
notre runtime. Ultra reste le témoin expérimental. L’effet propre de la quantification
n’est pas isolé ; Fluid F32 n’a pas été testé. Les poids Fluid viennent de leur dépôt
GGUF officiel figé, tandis que Silero et Nemotron conservent leurs sources précédentes.

### Décisions retenues

| Décision | Conséquence |
|---|---|
| Projet autonome nommé transcrimoi | Dépôt, noyau et petite interface propres ; pas de fork noScribe. |
| SRT SonalPi2 par défaut, neuf restitutions | Conserver le contrat SRT ; ajouter texte, tabulations, NVivo, ELAN tabulé, SRT simple et WebVTT. |
| Correction dans SonalPi2 | Aucun éditeur, contrat HTML ou aller-retour de corrections à construire. |
| Fluid Speech Pro GGUF Q8_0, modèle par défaut | Un seul modèle ASR cible ; Ultra F16 et v3 restent des témoins d’expérience, pas des moteurs supplémentaires dans l’interface. |
| Nemotron-3-Diarization F16 | Référence initiale pour distinguer les locuteurs. |
| Runtime natif `mudler/parakeet.cpp`, GGML/GGUF | Pas de pile Python d’inférence dans le paquet utilisateur. Capacités à vérifier sur un commit figé. |
| Contrôleur Python et processus natifs séparés | Noyau testable sans interface, isolation des plantages et libération mémoire entre phases. |
| Traitement local d’enregistrements sur CPU | Parcours complet sans GPU et hors ligne après installation ; accélération facultative, pas d’objectif de transcription en direct. |

## 2. Périmètre du premier produit

### Obligatoire

- Installer et utiliser sans terminal, sans Python préinstallé et sans compte externe.
- Importer WAV, MP3, M4A, FLAC et MP4, avec décodage local par FFmpeg.
- Transcrire des entretiens en français de 1 à 2 heures, sans perdre la chronologie originale.
- Distinguer les locuteurs, en priorité deux personnes ; qualifier aussi une voix et trois à quatre personnes.
- Produire un SRT UTF-8 directement importable dans SonalPi2, avec une convention de locuteurs validée.
- Afficher l’étape en cours, la progression lorsqu’elle est disponible et les erreurs utiles.
- Annuler proprement ; récupérer les phases déjà achevées après interruption.
- Ne jamais écraser silencieusement un document existant, quel que soit le format.
- Fonctionner réseau coupé une fois les composants installés.

### Après le pilote

File de plusieurs fichiers, reprise au milieu d’une phase et réglages avancés de performance. Le besoin d’autres formats a été exprimé : les neuf conventions Tadddam font désormais partie du périmètre, sans DOCX/XLSX ni export EAF (XML).

### Hors périmètre

Éditeur, lecteur audio synchronisé, corrections dans transcrimoi, HTML noScribe, distribution de noScribeEditor, synchronisation des corrections avec SonalPi2, modification de SonalPi2, intégration directe entre applications, transcription en direct, résumé/correction par LLM, traduction, identification d’une personne entre entretiens et service web.

L’import manuel du SRT suffit pour le pilote. Aucun lancement automatique de SonalPi2 n’est nécessaire.

## 3. Premier verrou : le contrat SRT avec SonalPi2

Le SRT est un format de sous-titres, pas un format standardisé de diarisation. Les temps et le texte ne suffisent donc pas à garantir la récupération des locuteurs par l’importeur. C’est le seul raccord à fixer avant d’assembler le produit.

### M0 — Un fichier témoin, pas un audit de code

1. Partir d’un SRT déjà accepté par SonalPi2, s’il en existe un, ou fabriquer un petit SRT synthétique avec un audio connu.
2. Inclure deux locuteurs, des accents, une réponse très courte, une pause et un changement de locuteur. Tester séparément un chevauchement et une attribution indéterminée.
3. Fixer la représentation des locuteurs que SonalPi2 reconnaît effectivement. Ne pas présumer qu’un préfixe textuel est interprété comme une identité de locuteur.
4. Importer le fichier et vérifier le texte, les débuts/fins, l’absence de décalage et la récupération des locuteurs attendue.
5. Conserver ce fichier comme fixture de référence, avec les résultats attendus et les règles d’export.

**Condition de sortie :** une convention SRT acceptée par SonalPi2 est documentée et vérifiée. L’essai peut être réalisé manuellement avec l’utilisateur, sans lire la codebase de SonalPi2.

Si les locuteurs ne sont pas récupérés, ne pas présenter ce point comme résolu : choisir explicitement une convention déjà prise en charge ou accepter une limitation. Une modification de SonalPi2 serait une décision séparée, pas un chantier implicite de transcrimoi.

### Règles de l’exporteur

- UTF-8, blocs numérotés à partir de 1 et séparés par une ligne vide.
- Horodatages `HH:MM:SS,mmm --> HH:MM:SS,mmm`, dans le repère du média original.
- Débuts positifs ou nuls, fins strictement postérieures aux débuts, bornes cohérentes avec la durée du média.
- Ordre déterministe, trié par temps de début ; arrondi en millisecondes testé, sans bloc de durée nulle après arrondi.
- Texte brut ; pas de balisage propriétaire non validé par l’importeur.
- Convention des locuteurs et politique de chevauchement conformes à la fixture M0.
- Segmentation par tours de parole et unités de texte raisonnables ; éviter un bloc de plusieurs minutes. Les limites de durée et de longueur sont fixées par les essais d’import et d’usage, pas par une norme de sous-titrage arbitraire.
- Aucun décalage artificiel des temps pour masquer des paroles simultanées. Le SRT ne permet pas de restituer les mots que l’ASR n’a pas reconnus.
- Écriture dans un temporaire puis publication atomique du fichier final après validation.

Le SRT SonalPi2 reste le livrable par défaut ; les autres formats de restitution utilisent les mêmes blocs internes. Le JSON conserve les résultats détaillés pour la reprise et le réexport, sans devenir un éditeur ni un protocole de synchronisation.

## 4. Architecture minimale

**Interface minimale → contrôleur Python → FFmpeg et processus natifs → mots et plages de locuteurs → attribution → export choisi.**

| Composant | Responsabilité |
|---|---|
| Interface | Choix du média, format et destination, démarrage, progression, annulation et accès au fichier produit. |
| Contrôleur autonome | État de la tâche, orchestration, sauvegardes par phase et erreurs. |
| FFmpeg embarqué | Conversion locale de l’audio de travail. |
| Adaptateur natif | Lancement de Parakeet/VAD et de Nemotron ; normalisation des sorties. |
| Attribution et segmentation | Associer les mots aux locuteurs puis construire les blocs à exporter. |
| Exports | Appliquer le contrat SonalPi2 ou une autre des neuf restitutions, sans changer l’inférence. |

Les phases lourdes sont exécutées successivement pour ne pas garder les modèles simultanément en mémoire : conversion, transcription, diarisation, attribution et export. Le noyau n’importe aucun module d’interface.

### Intégration du moteur

Commencer par les exécutables CLI de parakeet.cpp si leurs sorties donnent les mots horodatés et les plages de diarisation nécessaires. Vérifier ces capacités sur le commit retenu.

Si le CLI est insuffisant, construire un petit exécutable lié à l’API C, exposant uniquement les opérations utiles. Ne pas développer ce wrapper par anticipation. L’API/CLI amont reste derrière un adaptateur ; aucun serveur HTTP n’est nécessaire.

Lancer les processus sans shell, avec des arguments séparés. Une phase n’est validée qu’après un code de sortie réussi et la validation de ses résultats. Les diagnostics sont distincts des données structurées.

## 5. Modèles et dépendances

| Élément | Choix retenu provisoirement |
|---|---|
| ASR | `FluidVoice-Labs/fluid-speech-pro`, GGUF officiel Q8_0 ; choix multilingue à qualifier sur nos propres corpus. |
| Diarisation | `nvidia/Nemotron-3-Diarization`, GGUF F16. |
| VAD | Silero dans le runtime natif, modèle distinct à versionner. |
| Audio | FFmpeg avec les capacités nécessaires aux formats d’import. |
| Application | Contrôleur Python et fenêtre PySide6/Qt (Essentials uniquement). Python embarqué et installateurs à préparer. |

La même interface cible Windows, Linux et macOS. Les premiers essais de fenêtre et de moteur réel passent sous Linux/WSL et Windows 11 ; macOS, les machines propres, la signature et la distribution ne sont pas encore qualifiés.

Ne pas distribuer Photon, le SDK Moondream, Torch, Torchaudio, NeMo, Pyannote, Whisper, faster-whisper, CTranslate2 ou ONNX Runtime. Séparer les outils de conversion des modèles de l’environnement utilisateur. Ne pas reprendre les dépendances ou spécifications de packaging de noScribe.

Figer le runtime, ses sous-modules, les modèles, leurs licences et leurs sommes de contrôle. Ne pas inclure de modèles supplémentaires sans usage.

Vérifier intégralement les modèles par SHA-256 après téléchargement. Mémoriser la
vérification réussie dans un cache local lié à l’empreinte attendue et aux caractéristiques
du fichier ; avant chaque tâche, ne relire le contenu que si elles ont changé ou si le
cache est absent/invalide. Sans cache inscriptible, conserver la vérification complète.
La commande `python -m transcrimoi verify-backend` force le contrôle intégral.
Les binaires restent vérifiés intégralement à chaque tâche. Ce compromis de performance
n’est pas une protection contre une altération hostile du modèle et de son cache.

## 6. Traitement des entretiens longs

### Audio et chronologie

Convertir vers un WAV mono 16 kHz sur disque, sans suppression définitive des silences. Tous les résultats restent exprimés dans le repère temporel du média source. Vérifier les offsets, les durées et les éventuels décalages introduits par le décodage, notamment pour les vidéos.

Éviter les copies intégrales de l’audio en Python. Vérifier aussi les allocations du runtime natif : une inférence par fenêtres ne garantit pas à elle seule une mémoire totale bornée.

### Transcription

Utiliser la VAD et des marges pour découper près des pauses, avec une durée maximale par morceau déterminée par les essais. Conserver l’offset de chaque morceau et tester la fusion sans perte ni duplication aux jonctions.

Inclure « oui », « non », « hum » et les interruptions brèves dans les tests. Ne pas inventer des hésitations ou des mots non émis par l’ASR. Afficher « Reconnaissance multilingue automatique », sans prétendre qu’une langue est verrouillée ni proposer de faux sélecteur de français.

Avant attribution et segmentation, omettre uniquement les tokens exactement égaux à
`<unk>`. Conserver les JSON natifs, les temps et la raison des omissions dans le résultat ;
signaler leur nombre dans la fenêtre et la CLI. Aucun remplacement inventé, aucun
filtrage générique des balises ou des fragments de mots. La politique appartient à la
provenance de reprise ; les anciens résultats ne sont pas réécrits.

### Diarisation et attribution

Employer le chemin progressif avec cache continu de locuteurs exposé par la version retenue. Ne pas réinitialiser le cache à chaque fenêtre et ne pas supposer qu’un traitement intégral de deux heures tient en mémoire. Vérifier les fonctions et paramètres réellement utilisés.

Attribuer d’abord les mots par recouvrement temporel avec les plages de parole, puis par proximité à 150 ms maximum si un seul locuteur convient. Résoudre ensuite les mots encore indéterminés par le contexte attribué précédent/suivant, sans distance maximale : même locuteur des deux côtés, sinon côté temporellement le plus proche, ou seul côté disponible. **En cas d’égalité, retenir le locuteur précédent : choix explicite du produit.** Sans contexte attribué, conserver l’indétermination. Enregistrer la raison de l’attribution finale ; une attribution par contexte n’est pas une certitude mesurée. Tester les frontières, les égalités, l’absence de plage et les voix simultanées. Préserver les changements de locuteur et les réponses courtes dans les blocs SRT. Les règles détaillées figurent dans le [contrat SRT](docs/contrat-srt.md#règles-de-génération).

La cible de deux personnes n’est pas un réglage « exactement deux » tant que le moteur ne permet pas de l’imposer effectivement.

### Sauvegardes et annulation

Sauvegarder après chaque phase validée : conversion, transcription, diarisation, attribution. Une reprise réutilise uniquement des résultats compatibles avec la source, les versions et les paramètres enregistrés.

Après interruption au milieu de la diarisation, relancer cette phase depuis le début : restaurer un numéro de fenêtre sans son cache serait incorrect. La reprise interne à une phase attendra une gestion complète de l’état.

L’annulation arrête FFmpeg, le moteur et leurs enfants. Libérer les ressources entre les phases. Une sortie partielle ne remplace jamais un SRT existant. Un SRT déjà importé ou corrigé dans SonalPi2 n’est pas synchronisé avec transcrimoi ; une nouvelle génération produit un fichier distinct ou exige une confirmation explicite.

## 7. Découpage actuel du dépôt

Le prototype conserve des modules simples plutôt qu’un ensemble de sous-paquets anticipés.

| Module | Contenu |
|---|---|
| `transcrimoi/backend.py` | Vérification des manifests/modèles/binaires et commandes ASR/diarisation. |
| `transcrimoi/model_verification.py` | Vérification SHA-256 des modèles et cache local des contrôles réussis. |
| `transcrimoi/process.py` | Sous-processus natifs, arrêt de leur arbre et erreurs. |
| `transcrimoi/job.py` | Conversion FFmpeg, orchestration, événements et reprise par phase. |
| `transcrimoi/assignment.py` | Attribution des mots et segmentation. |
| `transcrimoi/schema.py` | Contrat interne versionné et validation. |
| `transcrimoi/srt.py` | Lecture/export selon la fixture SonalPi2. |
| `transcrimoi/exports.py` | Neuf restitutions, regroupement texte par locuteur et chargement des résultats réexportables. |
| `transcrimoi/storage.py` | Empreintes et écritures atomiques. |
| `transcrimoi/gui.py` | Fenêtre Qt, sans inférence dans Python. |
| `transcrimoi/runtime.py` | Emplacements source/gelés et cache utilisateur des modèles. |
| `transcrimoi/desktop_check.py` | Diagnostic embarqué Qt → vrais modèles → silence. |
| `transcrimoi/__main__.py` | CLI indépendante de Qt. |
| `scripts/prepare_backend.py` | Préparation développeur du runtime figé. |
| `scripts/build_desktop.py`, `scripts/transcrimoi.spec` | Préversions PyInstaller avec modèles, diagnostic et archives par OS. |
| `tests/` | Tests, outils, petites références et configurations d’expérience ; données locales ignorées. |

Le contrat interne conserve : provenance de la source et du moteur, paramètres, mots horodatés, plages de locuteurs avec chevauchements, attributions ambiguës, blocs calculés et phases achevées. Il ne devient pas un format d’édition ou un protocole de synchronisation avec SonalPi2.

Les [préversions autonomes](docs/paquets-autonomes.md) sont construites manuellement
via l’entrée `package` du workflow Desktop CPU. Les artefacts `app-preview-OS`
contiennent l’application et ses modèles ; `test-report-OS` ne contient que les rapports.
Le diagnostic du binaire gelé doit réussir avant archivage. Aucun installateur final,
signature éditeur, notarisation ou validation exhaustive des licences n’est revendiqué.

## 8. Interface utilisateur

Une seule fenêtre suffit :

1. **Fichier audio ou vidéo**.
2. **Format de sortie et destination**, proposés à côté de la source si possible.
3. **Transcrire**.
4. Étape en cours, progression disponible et bouton **Annuler**.
5. À la fin : **Ouvrir le dossier du résultat**, avec indication d’import SonalPi2 pour le format par défaut.

Pas de lecteur, de liste de segments ou de panneau de correction. La distinction des locuteurs est active dans le parcours cible ; un mode sans diarisation n’est ajouté que s’il répond à un besoin concret.

Si le moteur ne fournit pas de progression mesurable, afficher une étape indéterminée plutôt qu’un pourcentage inventé. L’absence d’événements réguliers ne prouve pas un blocage.

Le prototype actuel utilise exclusivement le CPU et Fluid Speech Pro Q8_0. Pas de sélecteur de langue, de modèle ou de nombre de locuteurs sans effet réel. Une seule tâche à la fois ; les champs sont désactivés pendant le traitement. Les erreurs détaillées et les journaux restent accessibles, sans panneau d’édition. Les messages d’erreur distinguent média illisible, modèle absent/corrompu, espace disque insuffisant et panne du moteur.

## 9. Séquence de développement

| Étape | Travail | Condition de sortie |
|---|---|---|
| **M0 — Contrat SRT** | Fichier témoin, convention de locuteurs et essai d’import dans SonalPi2. | Texte, temps et locuteurs attendus récupérés ; fixture conservée. |
| **M1 — Moteur minimal** | Figer parakeet.cpp ; construire le runtime ; acquérir et vérifier les modèles ; tester ASR et diarisation séparément. | Mots horodatés et plages de locuteurs exploitables sur petits fichiers. |
| **M2 — Premier SRT réel** | Contrôleur, normalisation, attribution et export ; wrapper natif seulement si nécessaire. | Un enregistrement court devient un SRT réellement importé dans SonalPi2. |
| **M3 — Entretiens longs et robustesse** | VAD, offsets, cache continu, sauvegardes, annulation et mesures mémoire. | Entretien de 2 h traité sans corruption ; reprise des phases achevées vérifiée. |
| **M4 — Petite application** | Interface, erreurs compréhensibles et premier paquet autonome. | Parcours sans terminal sur une machine sans environnement de développement. |
| **M5 — Qualification et distribution** | Qualité, F16/Q8 ASR, allègement, installateur et tests hors ligne. | Paquet pilote mesuré et import SonalPi2 validé de bout en bout. |

M0 et M1 peuvent avancer en parallèle. M2 exige les deux. Un petit prototype de packaging peut être fait tôt pour lever les risques de dépendances, sans construire les installateurs complets avant M3.

Pas de calendrier ferme avant les essais du moteur. Le chemin critique est désormais **moteur → SRT réel → entretien long → application distribuable**, et non l’intégration d’un éditeur.

## 10. Validation et critères du pilote

### Tests sans modèle

Validation du schéma interne, conversion et arrondi des temps, accents, longues durées, attribution synthétique, segmentation, export SRT, transitions d’état et protection des fichiers existants. La fixture M0 devient un test de non-régression de l’exporteur.

### Tests réels

Silence seul, une voix, dialogue, réponses brèves, changements rapides, chevauchements, longs silences, média de deux heures, chemins Unicode, modèle corrompu, média illisible, disque plein, processus tué et annulation. Un fichier sans parole doit se terminer proprement sans texte inventé ; préciser dans l’interface qu’aucun bloc n’a été produit.

Importer dans SonalPi2 un SRT court puis un SRT d’entretien complet. Vérifier la chronologie au début, au milieu et à la fin, ainsi que les locuteurs. Cet essai fonctionnel ne demande pas d’audit de son code.

### Qualité et performance

Corpus proposé : cinq entretiens autorisés de 1 à 2 heures, principalement à deux personnes, et dix extraits annotés couvrant bruit, accents et interruptions. Mesurer séparément qualité ASR, diarisation, attribution des mots et erreurs de segmentation/export.

noScribe peut servir de référence sur ce corpus ; il n’est ni une dépendance de test obligatoire ni une exigence de parité d’interface. Publier les conventions des mesures WER/DER, les versions et le matériel. Mesurer temps total, temps par phase, mémoire maximale de tous les processus et taille installée, modèles compris.

| Domaine | Objectif proposé, à confirmer après prototype |
|---|---|
| Parcours | 4 débutants sur 5 produisent puis importent le SRT sans aide technique. |
| Compatibilité | Import vérifié des temps, du texte et des locuteurs selon le contrat M0. |
| Durée | Entretien de 2 h complet ; essai de résistance à 4 h avec limites documentées. |
| Mémoire | Cible ≤ 4 Go pour les processus de l’application sur une machine 8 Go, hors SonalPi2 et système. |
| Vitesse | Cible totale ≤ durée audio sur CPU de référence ; objectif ≤ 30 min pour 2 h sur Apple Silicon de référence, à qualifier. |
| Volume | Cible ≤ 2 Go installés, modèles compris ; mesurer le paquet réel plutôt que promettre une réduction relative à noScribe. |
| Qualité | Si comparée à noScribe : WER moyen au plus 2 points absolus au-dessus et DER moyen au plus 3 points au-dessus, à protocole identique ; examiner les cas critiques séparément. |
| Utilité | Relecture possible dans SonalPi2 sans réparation structurelle préalable du SRT ; effort de correction évalué sur un sous-ensemble. |
| Annulation | Réaction visible ≤ 5 s ; processus arrêtés et ressources libérées ≤ 15 s. |
| Intégrité | Pas d’écrasement silencieux, pas de sortie partielle publiée, pas de perte/duplication aux jonctions sur les cas annotés. |
| Confidentialité | Traitement hors ligne, aucun envoi d’audio ou de texte, aucun compte requis. |

Ces valeurs sont des objectifs, pas des résultats acquis. Si elles échouent, corriger ou faire accepter une limite explicite avant diffusion.

## 11. Distribution et maintenance

Conserver l’ordre de qualification prévu : macOS Apple Silicon d’abord, Windows x64 CPU ensuite, Linux dans un second temps. Une seule plateforme qualifiée suffit au premier pilote ; ne pas laisser les trois installateurs bloquer le premier SRT utile.

- **macOS :** build arm64/Metal, composants natifs embarqués, signature et notarisation pour la diffusion ; essai hors ligne sans outils de développement.
- **Windows :** binaire CPU portable, bibliothèques requises incluses, essai sans Python, Visual Studio ou CUDA ; vérifier chemins et arrêt des enfants.
- **Linux :** préciser les distributions et bibliothèques minimales, puis tester un paquet autonome adapté.

Le paquet contient uniquement transcrimoi, son environnement nécessaire, FFmpeg, le runtime et les modèles. Il n’embarque ni SonalPi2 ni noScribeEditor.

Privilégier d’abord un paquet complet prêt hors ligne. Un téléchargement initial guidé pourra suivre, avec taille, progression et contrôle d’intégrité. Les modèles ne changent pas pendant un traitement. Chaque version qualifie ensemble application, runtime, modèles et convention d’export.

Examiner séparément les licences du runtime, de FFmpeg, des poids et des bibliothèques d’interface. Si du code tiers est finalement repris, conserver les notices et respecter ses obligations ; aucune reprise noScribe n’est nécessaire par défaut.

## 12. Risques restants

| Risque | Réponse |
|---|---|
| Locuteurs non interprétés à l’import SRT | Fixture et essai M0 avant l’assemblage ; aucune convention inventée présentée comme compatible. |
| API/CLI native insuffisante | Vérifier en M1 ; ajouter seulement le wrapper nécessaire. |
| Dérive des identités sur deux heures | Contrôler le cache et mesurer début/milieu/fin d’un entretien complet. |
| Mémoire excessive malgré le fenêtrage | Profiler lecture audio, copies PCM et contextes ; exécuter les phases successivement. |
| Temps faux après découpage ou décodage | Tests d’offset et import vérifié face au média original. |
| SRT trop fragmenté ou trop massif | Régler la segmentation sur les usages de SonalPi2, sans modifier arbitrairement les temps. |
| Mauvaise reconnaissance des hésitations ou chevauchements | Mesurer et documenter ; ne pas inventer de contenu absent de l’ASR. |
| Runtime évolutif | Commit et sous-modules figés, adaptateur isolé, tests avant mise à jour. |
| Paquet encore lourd | Auditer les dépendances transitives et modèles ; aucun éditeur à distribuer. |

## 13. Livrables et définition de terminé

1. Noyau autonome avec traitement par phase et exporteur SRT.
2. Fixture SRT SonalPi2 et contrat d’import vérifié.
3. Petite interface sans fonctions d’édition.
4. Manifeste des modèles, versions, checksums et licences.
5. Tests ciblés, rapport qualité/performance et limites connues.
6. Paquet de la plateforme pilote et guide court : choisir le média, transcrire, importer le SRT dans SonalPi2.

**Le pilote est terminé lorsqu’un utilisateur peut installer transcrimoi sur une machine propre, traiter hors ligne un entretien de deux heures et importer le SRT dans SonalPi2 avec le texte, les temps et les locuteurs attendus.** La correction se déroule ensuite entièrement dans SonalPi2.

## 14. Références et limites de preuve

Le prototype fige parakeet.cpp au commit `2eac2e77d9c7ef8899f7a86a46e693ac5ac1a5cd`. Les trois modèles du produit et leurs SHA-256 sont dans `backend.lock.json` ; les références de l’expérience v3/Ultra sont dans `tests/experiments/ultra-f16.lock.json`. Les CLI ont fourni les mots horodatés et la diarisation nécessaires sans wrapper C supplémentaire. Les rapports [initiaux](docs/validation-m1-m2.md), [Ultra GGUF](docs/essai-ultra-gguf.md) et [Photon CPU](docs/essai-photon-cpu.md) distinguent les résultats effectivement obtenus des objectifs restant à qualifier. Les performances publiées en amont ne sont pas des garanties produit.

- [parakeet.cpp](https://github.com/mudler/parakeet.cpp), [CLI](https://github.com/mudler/parakeet.cpp/blob/master/docs/cli.md), [API C](https://github.com/mudler/parakeet.cpp/blob/master/docs/capi.md) et [diarisation](https://github.com/mudler/parakeet.cpp/blob/master/docs/diarization.md).
- [Parakeet TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3), modèle des premiers essais et base d’Ultra.
- [Parakeet Ultra](https://huggingface.co/moondream/parakeet-ultra), ancien modèle du produit et témoin expérimental.
- [Fluid Speech Pro GGUF](https://huggingface.co/FluidVoice-Labs/fluid-speech-pro-gguf), modèle actuel ; ses benchmarks amont ne qualifient pas nos usages multilingues sur CPU.
- [Nemotron-3-Diarization](https://huggingface.co/nvidia/Nemotron-3-Diarization).
- [Modèles GGUF mudler](https://huggingface.co/mudler/parakeet-cpp-gguf/tree/main).

Aucun nouvel audit de noScribe ou de SonalPi2 n’est revendiqué dans cette version. La compatibilité SRT sera établie par les essais M0/M2, pas déduite de la seule présence d’un importeur SRT.

## 15. Ce qui disparaît du plan précédent

- Réutilisation, adaptation, lancement et distribution de noScribeEditor.
- Variante de reprise de l’interface de transcription noScribe.
- Contrat HTML, ancres spécifiques et tests d’aller-retour éditeur.
- Gestion des corrections, renommage manuel et réattribution dans transcrimoi.
- Exports HTML, TXT et WebVTT du périmètre initial.
- Packaging commun lanceur/éditeur et maintenance des correctifs de l’éditeur.

Le SRT passe au cœur du produit. Les exigences de traitement local, de qualité, de diarisation et de robustesse sur les entretiens longs restent conservées.
