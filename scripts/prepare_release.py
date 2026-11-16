#!/usr/bin/env python3
"""Vérifier les trois paquets autonomes avant création d'une Release en brouillon."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from transcrimoi import __version__
from transcrimoi.storage import read_json, sha256_file


PLATFORMS = {
    "windows-x86_64": ".zip",
    "macos-arm64": ".app.zip",
    "linux-x86_64": ".tar.gz",
}


def validate_assets(directory: Path) -> list[Path]:
    expected = set()
    archives = []
    for platform, suffix in PLATFORMS.items():
        base = f"transcrimoi-preview-{__version__}-{platform}"
        archive = directory / f"{base}{suffix}"
        checksum = directory / f"{archive.name}.sha256.json"
        report = directory / f"{base}-self-test.json"
        expected.update((archive.name, checksum.name, report.name))
        for path in (archive, checksum, report):
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Fichier de Release absent ou invalide : {path.name}")
        manifest = read_json(checksum)
        size = archive.stat().st_size
        if not 0 < size < 2 ** 31:
            raise ValueError(f"Archive vide ou dépassant la limite GitHub de 2 Gio : {archive.name}")
        if (not isinstance(manifest, dict)
                or manifest.get("file") != archive.name or manifest.get("bytes") != size
                or manifest.get("sha256") != sha256_file(archive)):
            raise ValueError(f"Taille ou empreinte incorrecte : {archive.name}")
        diagnostic = read_json(report)
        if (not isinstance(diagnostic, dict)
                or diagnostic.get("status") != "completed" or diagnostic.get("frozen") is not True):
            raise ValueError(f"Diagnostic du paquet non validé : {report.name}")
        archives.append(archive)
    if {path.name for path in directory.iterdir()} != expected:
        raise ValueError("Fichiers inattendus parmi les pièces jointes de la Release")
    return archives


def release_notes() -> str:
    return f"""# transcrimoi {__version__} — préversion autonome

Paquets de validation avec modèles inclus, non signés pour distribution et non notariés
sur macOS. Ce ne sont pas des installateurs qualifiés. L'audit des licences et les
essais sur machines propres restent à terminer. Vérifier ces points avant publication.

## Télécharger et ouvrir

Choisir l'archive de votre plateforme dans les pièces jointes (Assets), **pas** les
archives « Source code » ni les artefacts de rapports Actions. Une seule extraction :

- **Windows x86-64** : extraire le `.zip`, ouvrir le dossier `transcrimoi` et lancer
  `Transcrimoi.exe`, en conservant `_internal` à côté.
- **macOS Apple Silicon** : extraire le `.app.zip` avec l'Utilitaire d'archive de macOS,
  puis déplacer `transcrimoi.app` dans Applications si souhaité. Application non notariée ;
  une autorisation manuelle peut être nécessaire. Mac Intel non pris en charge.
- **Linux x86-64** : extraire le `.tar.gz` en conservant les permissions et les liens,
  puis lancer `transcrimoi/transcrimoi`.

Python, FFmpeg et les modèles sont embarqués. Aucun compte ni téléchargement de modèle
supplémentaire n'est nécessaire pour transcrire. Les bibliothèques système restent requises.
Chaque archive est accompagnée de sa taille et de son SHA-256 (`.sha256.json`) et du
rapport de diagnostic embarqué (`-self-test.json`).
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--notes", type=Path, required=True)
    args = parser.parse_args()
    try:
        archives = validate_assets(args.directory)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    args.notes.write_text(release_notes(), encoding="utf-8")
    print(f"{len(archives)} archives vérifiées ; notes : {args.notes}")


if __name__ == "__main__":
    main()
