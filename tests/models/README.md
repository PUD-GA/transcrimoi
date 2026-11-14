# Modèles d’expérience locaux — ne pas distribuer

Ce dossier est ignoré par Git, sauf ce README. Il contient les modèles **hors produit** :

- `tdt-0.6b-v3-f16.gguf` : témoin historique de la comparaison v3/Ultra ;
- `ultra-f16.gguf` : témoin des expériences v3/Ultra et Ultra/Fluid, ancien modèle du produit ;
- `photon-ultra-f16/` : anciens fichiers de téléchargement/configuration Photon.
  Le fichier `model.safetensors.part` est incomplet et n’est pas exploitable comme modèle.

Les modèles du produit sont seulement les trois GGUF désignés par `backend.lock.json`,
dans le dossier racine `models/`. Ne jamais embarquer tous les modèles expérimentaux
ou le venv Photon dans un paquet utilisateur.

L’outil `tests/tools/compare_ultra.py --download-model` place v3 et Ultra ici.
`compare_fluid.py` utilise Ultra ici et Fluid depuis `models/` quand il est présent,
sinon depuis ce dossier pour une expérience indépendante. Voir [le guide des tests](../README.md).
