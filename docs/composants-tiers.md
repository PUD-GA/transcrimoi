# Composants tiers — inventaire développeur

Ce document n’est pas une autorisation de redistribution ni un avis juridique.
Les notices complètes devront être assemblées dans le paquet final.

| Composant | Référence | Licence indiquée en amont |
|---|---|---|
| parakeet.cpp | Commit dans `backend.lock.json` | MIT |
| GGML | Sous-module figé ; correctifs fournis par parakeet.cpp appliqués par son CMake | MIT |
| Fluid Speech Pro Q8_0 | GGUF officiel FluidVoice-Labs, dérivé de Parakeet v3 et Ultra | CC-BY-4.0 ; attribution « Fluid Speech Pro by FluidVoice », références NVIDIA/Moondream et licence à conserver |
| Nemotron-3-Diarization | Poids NVIDIA convertis en GGUF par mudler | OpenMDW 1.1 |
| Silero VAD | Conversion GGUF mudler | MIT, copyright Silero Team |
| FFmpeg | Exécutable système dans le prototype | Dépend de la configuration du build ; vérifier LGPL/GPL et codecs avant embarquement |
| Python | Interpréteur système dans le prototype | PSF ; embarquement à préparer ultérieurement |
| PySide6-Essentials / Shiboken6 / Qt | Interface optionnelle, versions dans les rapports de test | LGPLv3/GPLv3 ou licence commerciale selon les composants ; notices et obligations de redistribution à vérifier avant empaquetage |

Les références exactes des trois GGUF, leur révision Hugging Face et leurs SHA-256
sont dans [`backend.lock.json`](../backend.lock.json).

Le modèle ASR du produit vient du dépôt officiel
[Fluid Speech Pro GGUF](https://huggingface.co/FluidVoice-Labs/fluid-speech-pro-gguf) :
son dépôt et sa révision remplacent, pour ce rôle seulement, les valeurs communes du
verrou. Silero et Nemotron restent issus du dépôt mudler figé.
Ultra F16 et Parakeet v3 restent des témoins expérimentaux **hors produit** dans
`tests/models/`, sous CC-BY-4.0, avec leurs références figées dans `tests/experiments/`.

Sources à conserver/contrôler pour l’assemblage :

- `vendor/parakeet.cpp/LICENSE`, `vendor/parakeet.cpp/third_party/ggml/LICENSE`.
- [Licences documentées par le convertisseur](https://github.com/mudler/parakeet.cpp/blob/2eac2e77d9c7ef8899f7a86a46e693ac5ac1a5cd/docs/licenses.md).
- [Licences du dépôt de poids figé](https://huggingface.co/mudler/parakeet-cpp-gguf/tree/07a08a3a405d20c5434b9a1442f6e6cf571f57ad/licenses).
- [Fluid Speech Pro GGUF figé](https://huggingface.co/FluidVoice-Labs/fluid-speech-pro-gguf/tree/fee970d9ac83f6d236632d39b67cbec12f5a9020), dérivé d’[Ultra](https://huggingface.co/moondream/parakeet-ultra) et de [Parakeet v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3).
- [Licences Qt for Python](https://doc.qt.io/qtforpython-6/licenses.html).
- [Modèle de diarisation d’origine](https://huggingface.co/nvidia/Nemotron-3-Diarization).
- [Silero VAD](https://github.com/snakers4/silero-vad).

Les composants CED et voice-detect ne sont pas liés au runtime de ce prototype ;
leurs sous-modules peuvent être présents dans un clone de travail mais ne sont pas
nécessaires au build retenu. Aucun code de noScribe/noScribeEditor n’est repris.
La licence propre du nouveau projet reste à choisir avant publication.
