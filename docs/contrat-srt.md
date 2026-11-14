# Contrat SRT SonalPi2 — référence M0

## Source d’autorité

L’utilisateur a fourni le corpus synthétique, désormais dans `tests/sources/synth/`,
en précisant que les SRT sont des entrées
valides de SonalPi2. Leur acceptation est prise comme référence, sans audit de son code.
Les fichiers originaux ne sont pas modifiés.

Inventaire figé avec SHA-256 des médias et des SRT :
[`tests/fixtures/corpus_manifest.json`](../tests/fixtures/corpus_manifest.json).

| Fichier | Durée MP3 (s, conteneur) | Blocs | Locuteurs dans le SRT |
|---|---:|---:|---|
| 1Coordinatrice | 223,53 | 100 | 0, 1 |
| 2RetraiteAnticipee | 296,78 | 96 | 0, 1 |
| 3Cuisinier | 234,61 | 80 | 0, 1 |
| 4Etudiants | 214,52 | 62 | 0, 1, 2 |

## Convention reproduite

```srt
1
00:00:00,700 --> 00:00:02,460
Speaker 1: Alors déjà, merci beaucoup de me recevoir.
```

- Encodage UTF-8 ; les références ont un BOM, accepté à la lecture. L’export est UTF-8
  sans BOM, à vérifier également lors du premier import du résultat généré.
- Blocs numérotés continûment, ligne vide de séparation.
- Horodatages à la milliseconde, virgule décimale, début/fin dans le repère du média source.
- `Speaker N: ` en début du texte, où `N` est un entier positif ou nul. Ni balise HTML
  ni métadonnée propriétaire supplémentaire.
- Un seul locuteur par bloc ; les indices ne sont pas nécessairement dans l’ordre
  de première apparition. Les références démarrent souvent par `Speaker 1`.
- Les identifiants ne sont pas des identités de personnes et ne sont pas comparables
  automatiquement entre le SRT de référence et la sortie d’une nouvelle diarisation.

Le lecteur/exporteur conserve texte, temps et locuteurs lors d’un aller-retour sur
les 338 blocs. Cela ne constitue pas encore un essai d’import de la nouvelle sortie.

## Règles de génération

L’exporteur refuse les temps non finis, négatifs, désordonnés et les blocs vides après
arrondi. Arrondi décimal à la milliseconde, demi-milliseconde vers le haut.

La segmentation initiale conserve les changements de locuteur et coupe aux fins de
phrases, aux pauses de plus de 0,8 s ou près des limites de 15 s / 240 caractères.
Ces limites sont des heuristiques de travail, pas des normes SonalPi2. Un mot individuel
n’est jamais tronqué. Les horodatages des mots d’origine restent dans le JSON interne.

Avant l’attribution, les tokens **exactement égaux à `<unk>`** (après retrait des
espaces externes par le parseur) sont omis de la représentation destinée au SRT.
Aucun filtrage générique de texte entre chevrons : `pré<unk>fixe`, `<UNK>`, `<unk>.`
et les autres balises restent inchangés. Aucun mot de remplacement n’est inventé.
Les sorties natives `asr.json` restent intactes. Dans `result.json`, `native_word_count`
compte tous les tokens natifs ; `words` ne contient que les mots conservés après
attribution ; `omitted_token_count` et `omitted_tokens` retracent les omissions avec
leurs bornes, confiance éventuelle et raison `native_unknown_token`.
Le compteur est affiché dans la fenêtre, la CLI et les événements JSON d’export.
Un résultat ne contenant que des marqueurs omis produit un SRT vide avec un message
« Aucun texte exportable après filtrage », pas une affirmation d’absence de parole.
La politique de filtrage fait partie de la provenance et de l’identité de reprise.

L’attribution des mots conservés se fait en deux passes :

1. **Attribution temporelle directe** : choisir le plus grand recouvrement mot/parole.
   En l’absence de recouvrement, un rapprochement de 150 ms maximum est admis s’il
   désigne un seul locuteur. À cette étape, une égalité ou l’absence de candidat laisse
   le mot indéterminé.
2. **Résolution par contexte** : pour chaque groupe de mots encore indéterminés,
   chercher les mots attribués précédent et suivant, hors ponctuation fermante. Si leurs
   locuteurs sont identiques, retenir ce locuteur ; sinon, retenir le côté temporellement
   le plus proche. **En cas d’égalité, retenir le locuteur précédent : c’est un choix
   explicite du produit.** Si un seul côté est disponible, utiliser son locuteur.
   Cette passe n’impose pas de distance maximale, contrairement au rapprochement
   direct de 150 ms. Sans contexte attribué, les mots restent indéterminés.

La ponctuation fermante encore indéterminée hérite du token lexical précédent lorsqu’il
est attribué. La raison de l’attribution finale est conservée dans le JSON interne,
notamment pour distinguer attribution directe et résolution par contexte. Le compteur
« mots sans locuteur » porte sur le résultat après ces deux passes : zéro mot sans
locuteur ne constitue pas une mesure de fiabilité des attributions.

Les chevauchements temporels ne sont pas artificiellement décalés. Un mot de ponctuation
isolé de durée nulle peut nécessiter un bloc minimal de 1 ms ; il n’est pas supprimé.
Les fichiers existants sont protégés par défaut, y compris contre une création concurrente.

## Cas non couverts par ce corpus

Les quatre SRT fournis n’ont ni bloc sans locuteur ni blocs adjacents en chevauchement.
Leur import ne prouve donc pas ces variantes. Le prototype exporte le texte sans préfixe
pour les attributions indéterminées ; **l’interprétation par SonalPi2 reste à confirmer**.
Un résultat sans parole produit un fichier vide et zéro bloc, sans inventer de contenu ;
il ne doit pas être présenté comme un SRT non vide à importer.

Le premier essai utilisateur doit vérifier sur un nouveau SRT : lecture UTF-8 sans BOM,
locuteurs, temps début/milieu/fin et association au média original. Les variantes inconnues
ou chevauchées nécessitent des essais distincts. Aucun changement de SonalPi2 n’est inclus.
