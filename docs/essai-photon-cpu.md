# Premier essai Photon sur CPU — résultat

> Décision ultérieure : Ultra F16 GGUF est désormais le modèle par défaut du
> produit, **sans Photon ni Torch**. L’environnement Photon reste expérimental,
> distinct de l’environnement de l’[interface Qt](interface-minimale.md).

## Installation et périmètre

Installation standard de `moondream==2.6.1` dans `.venv`, après installation de
Torch CPU depuis l'index officiel PyTorch. Les dépendances de transcrimoi dans
`pyproject.toml` n'ont pas été modifiées.

Versions effectivement utilisées :

- Python 3.12.3 ; Torch **2.15.0+cpu**, `torch.version.cuda is None`.
- Moondream 2.6.1, moteur Kestrel 0.9.1, kernels 0.7.4.
- Appel `md.photon("moondream/parakeet-ultra", device="cpu", cpu_threads=4)`.
- Aucun compte, clé API, service distant d'inférence ni GPU requis pour cet essai.
  Les avertissements relatifs aux clés concernent des fonctions non utilisées.

Le SDK a chargé les poids originaux **safetensors**, pas notre GGUF. Révision HF
`73175eb7aeb0d82f1e2a6b53b3aabc10a90bcd0b`, modèle de 1 255 353 386 octets,
SHA-256 vérifié :
`c9608f36d0ab956c14bfcc525479b0746b3b42a56f6949ec85c14eb7466717dc`.

Les paquets et kernels du SDK rendent le venv expérimental volumineux (environ
1,7 Gio hors modèles). Ils ne sont pas destinés au paquet utilisateur de transcrimoi.
Le pipeline GGUF continue de fonctionner sans import Torch/Photon.

## Test réel

Premier extrait de WamaTipsIA : 2,132–29,504 s, soit **27,372 s d'audio**.
Exactement le WAV utilisé pour l'essai GGUF, sans ajout de silence. API standard :

```python
with md.photon("moondream/parakeet-ultra", device="cpu", cpu_threads=4) as speech:
    result = speech.transcribe(audio="first-cut-exact.wav", timestamps="word")
```

Le texte retourné est **strictement identique** au texte plat d'Ultra F16 GGUF
sur cet extrait, comparaison de chaînes complète effectuée. Il commence par :

> Ok, normalement c'est enregistré. Donc pour être très rapide, cette présentation
> a lieu dans le cadre de Tip Cia.

Le mélange anglais/français de v3 sans padding n'y apparaît pas. Les mêmes erreurs
potentielles de noms propres, telles que « Tip Cia » / « Tip CA », subsistent.
Les horodatages par mot et par segment ont été retournés, mais leur parité entre
les deux moteurs n'a pas été qualifiée.

## Temps : ne pas confondre téléchargement et inférence

- 2 243,899 s avant disponibilité du modèle : **inclut le téléchargement réseau**,
  pas seulement un chargement local. Ce n'est pas un temps d'inférence.
- 1,032 s pour l'appel de transcription après chargement.
- L'essai GGUF indiquait 3,807 s, mais incluait le chargement du processus et du
  modèle. Ces deux temps ne sont donc pas directement comparables.

Une seule exécution, sur une station Xeon puissante, sans protocole de benchmark.
Aucune promesse de vitesse sur ordinateur modeste n'en est déduite.

## Artefacts et conclusion

- Réponse et métadonnées : `tests/runs/wamatipsia/diagnostic-photon/first-cut-cpu.json`.
- Journaux : `tests/runs/wamatipsia/diagnostic-photon/install.log` et `test.log`.
- Ces chemins reflètent le rangement actuel ; les résultats et journaux restent inchangés.
- Vidéo complète traitée avec Ultra GGUF : [compte rendu](essai-ultra-gguf.md).

Photon fonctionne bien sur CPU dans cet environnement. Sur le premier extrait,
il n'apporte pas de différence textuelle visible par rapport à Ultra GGUF ; cela
conforte la poursuite du moteur léger GGML. Ce test unique ne prouve pas une parité
générale des deux implémentations. Photon reste une référence expérimentale, sans
intégration au produit ni changement automatique du modèle par défaut.
