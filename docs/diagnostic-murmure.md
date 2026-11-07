# Comparaison ciblée avec Murmure — mélange français/anglais

## Périmètre et références

Lecture statique de Murmure au commit `b6f44c283d00ac108124b7d30db1cd39be9b98e2`,
complétée par des essais locaux sur des extraits de WamaTipsIA avec notre backend.
Murmure lui-même et son export ONNX n’ont pas été exécutés. La version installée
chez l’utilisateur reste à confirmer. Aucun changement du pipeline de production,
des modèles ou du SRT déjà livré n’a été effectué pour cette investigation.

## Différences vérifiées

### Silence ajouté avant et après la transcription finale

Dans `src-tauri/src/audio/pipeline.rs`, `INFERENCE_SILENCE_PAD_SECS = 0.25` et
`pad_with_silence()` entourent chaque morceau de 250 ms de zéros avant l’appel
à `engine.transcribe_samples()`. La remise à zéro du décodeur est explicite dans
`engine.rs` : un nouvel état est créé pour chaque séquence.

Cet ajout est une modification acoustique des bords du morceau, pas un sélecteur
de français. Son effet exact sur les résultats doit être mesuré ; il ne prouve
pas à lui seul la cause du défaut dans notre runtime.

### Streaming : aperçu recalculé, pas mémoire de langue persistante

`audio/streaming.rs` retranscrit le tampon courant quand sa révision change. Le
tampon s’allonge entre les coupes ; le texte provisoire peut être révisé. Le
chemin d’aperçu ne passe pas par `pad_with_silence()` et ne doit pas être confondu
avec la transcription finale des morceaux. Aucun verrou de langue n’est passé
à l’inférence. Le réglage `settings.language` est la langue de l’interface.

### Découpage différent

Dans `audio/chunking.rs`, recherche d’une pause de 500 ms après 15 s de morceau ;
coupe forcée à 60 s, avec une seconde de recouvrement puis déduplication. Notre
pipeline utilise Silero et une limite de 30 s. Murmure ne fait donc pas simplement
la même segmentation avec un autre affichage.

### Runtime et poids

Murmure utilise ONNX Runtime via Rust (`ort`), un préprocesseur ONNX `nemo128`,
un encodeur et un décodeur/joint ONNX int8. Nous utilisons GGML/GGUF F16.

La branche examinée distribue **Parakeet Ultra**, fine-tuning Moondream de Parakeet
v3, export int8 Olicorne. Le changelog l’annonce à partir de la version 2.0.3.
Le nom du dossier de ressources reste `parakeet-tdt-0.6b-v3-int8`, ce qui peut masquer
cette différence. Il faut connaître la version installée pour comparer les poids.

### Garde contre une dérive induite par le dictionnaire

`engine.rs` compare le décodage avec boosting lexical à un second décodage sans
boosting. Si la séquence boostée a au moins 24 tokens et que la divergence normalisée
dépasse 0,35, elle est remplacée par le décodage non boosté. Le commentaire mentionne
explicitement les bascules de langue.

Ce n’est pas un détecteur de langue général : la garde ne s’active que si un arbre
de boosting est présent. Notre pipeline n’utilise aucun boosting ; copier cette
garde telle quelle ne corrigerait donc pas notre cas.

## Essai contrôlé avec notre modèle inchangé

Artefacts : `tests/runs/wamatipsia/diagnostic-murmure/` (emplacement après rangement,
contenu historique inchangé). Le WAV source est dans `tests/sources/wamatipsia/WamaTipsIA.wav`.

Les coupes Silero ont été calculées sur le WAV de travail, mode `segments`, limite
30 s. Pour chaque coupe testée : extraction des mêmes échantillons PCM 16 kHz ;
transcription native isolée sans VAD supplémentaire, avec et sans exactement 4 000
échantillons nuls de chaque côté (250 ms). Même modèle v3 F16, même décodeur TDT,
même CLI, quatre threads. Ni forçage de langue, ni dictionnaire, ni LLM.

| Coupe (index à partir de zéro) | Intervalle source | Sans ajout | Avec ajout de 250 ms de chaque côté |
|---|---|---|---|
| 0 | 2,132–29,504 s | « Okay, normally it's enregistré. This presentation has deep CIA. » | « Ok, normalement c'est enregistré. Donc pour être très rapide, cette présentation a lieu dans le cadre de TIPSIA. » |
| 20 | 536,756–562,764 s | Mélange anglais/français, très tronqué | Davantage de texte, mais mélange persistant : amélioration insuffisante |
| 100 | 2634,880–2660,972 s | Français déjà cohérent | Français similaire, pas de changement spectaculaire |
| 180 | 4732,000–4756,652 s | « Merci for the presentation. I laid a chance… » | « Merci pour la présentation. Je laisse une dernière chance à une dernière question… » |

Le premier morceau sans padding, transcrit isolément, reproduit le mélange observé
dans le traitement complet : le décodage groupé n’est pas nécessaire pour reproduire
ce cas. Le premier morceau avec padding conserve le « OK » initial : il n’a pas fallu
supprimer ce mot pour obtenir une sortie en français.

Ces quatre comparaisons qualitatives ne remplacent pas une référence humaine ni une
comparaison avec le vrai moteur Murmure. L’ajout de silence aide nettement sur deux
cas, laisse un cas déjà français similaire et ne résout pas le quatrième.

## Conséquences proposées

1. Tester le padding aux frontières comme paramètre explicite et versionné, sans
   l’assimiler à une solution universelle ni modifier silencieusement les exports.
2. En cas d’intégration, retrancher le padding initial des horodatages locaux puis
   appliquer l’offset source, borner les temps, tester les jonctions et les silences.
3. Vérifier la version de Murmure utilisée et distinguer checkpoint, export et runtime.
4. Comparer les mêmes extraits au moteur ONNX de référence, puis le découpage, avant
   d’abandonner GGML ou d’introduire une correction/traduction artificielle du texte.

## Sources

- [Silence ajouté et transcription finale](https://github.com/Kieirra/murmure/blob/b6f44c283d00ac108124b7d30db1cd39be9b98e2/src-tauri/src/audio/pipeline.rs#L29-L72).
- [Aperçu streaming](https://github.com/Kieirra/murmure/blob/b6f44c283d00ac108124b7d30db1cd39be9b98e2/src-tauri/src/audio/streaming.rs).
- [Découpage](https://github.com/Kieirra/murmure/blob/b6f44c283d00ac108124b7d30db1cd39be9b98e2/src-tauri/src/audio/chunking.rs#L63-L70).
- [Décodeur et garde de boosting](https://github.com/Kieirra/murmure/blob/b6f44c283d00ac108124b7d30db1cd39be9b98e2/src-tauri/src/engine/engine.rs#L547-L578).
- [Modèle distribué](https://github.com/Kieirra/murmure/blob/b6f44c283d00ac108124b7d30db1cd39be9b98e2/README.md#L159-L160) et [changelog](https://github.com/Kieirra/murmure/blob/b6f44c283d00ac108124b7d30db1cd39be9b98e2/CHANGELOG.md).
