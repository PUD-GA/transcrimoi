# Résultats locaux — ne pas publier

Les SRT, JSON natifs, journaux, captures, WAV de travail et checkpoints sont regroupés
ici. Ils peuvent contenir le texte intégral des entretiens : tout est ignoré par Git,
excepté ce README. Les rapports partageables rédigés se trouvent dans `docs/`.

- `synth/` : anciens résultats du corpus synthétique (`runs/corpus/`).
- `reel/` : essais sur le corpus réel.
- `wamatipsia/` : diagnostic Murmure, essais Ultra/Photon, SRT complets et anciens caches.
- `gui-*` : captures, journaux et résultats des essais de fenêtre.

Les fichiers historiques n’ont pas été réécrits : leurs chemins absolus/relatifs
peuvent donc désigner les anciens emplacements. Les scripts ponctuels archivés ici
sont propres à la machine de développement et ne sont pas des outils maintenus.
Utiliser les outils portables dans `tests/tools/` et un nouveau dossier de sortie.
Ne pas forcer une reprise avec un état dont les sources ou la configuration ont changé.

Les WAV dérivés des anciens caches sont conservés pour la traçabilité, même lorsqu’un
WAV identique existe dans `tests/sources/`. Aucune suppression de résultat n’a été faite
pendant le rangement.

Le raccourci de développement Windows, lorsqu’il existe, est maintenant
`tests/runs/transcrimoi-Windows.lnk`. Il repose sur les runtimes temporaires Windows
préparés précédemment ; ce n’est pas un installateur autonome.
