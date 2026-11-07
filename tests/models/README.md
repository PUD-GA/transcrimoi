# Modèles d’expérience locaux — ne pas distribuer

Ce dossier est ignoré par Git, sauf ce README. Il contient les modèles **hors produit** :

- `tdt-0.6b-v3-f16.gguf` : témoin historique de la comparaison v3/Ultra ;
- `photon-ultra-f16/` : anciens fichiers de téléchargement/configuration Photon.
  Le fichier `model.safetensors.part` est incomplet et n’est pas exploitable comme modèle.

Les modèles du produit sont seulement les trois GGUF désignés par `backend.lock.json`,
dans le dossier racine `models/`. Ne jamais embarquer tous les modèles expérimentaux
ou le venv Photon dans un paquet utilisateur.

L’outil `tests/tools/compare_ultra.py --download-model` place le témoin v3 ici et réutilise
Ultra depuis le dossier du produit. Voir [le guide des tests](../README.md).
