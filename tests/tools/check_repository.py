#!/usr/bin/env python3
"""Contrôle des fichiers publiables, sans initialiser Git dans le projet."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MAX_FILE_BYTES = 5 * 1024 * 1024


def audit(root: Path, *, max_file_bytes: int = MAX_FILE_BYTES) -> dict:
    """Inclut les fichiers déjà indexés : .gitignore ne les protège pas."""
    root = root.resolve()
    probe = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
    with tempfile.TemporaryDirectory(prefix="transcrimoi-git-audit-") as tmp:
        if probe.returncode == 0 and Path(probe.stdout.strip()).resolve() == root:
            git = ["git", "-C", str(root)]
        else:
            # Seul ce dépôt temporaire est créé ; aucun .git dans le projet.
            subprocess.run(["git", "init", "-q", tmp], check=True, capture_output=True)
            git = ["git", f"--git-dir={Path(tmp) / '.git'}", f"--work-tree={root}"]
        files = sorted(set(subprocess.check_output(
            [*git, "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        ).decode("utf-8").strip("\0").split("\0")) - {""})
        ignored = subprocess.run([*git, "check-ignore", "--no-index", "--stdin", "-z"],
                                 input="".join(name + "\0" for name in files).encode("utf-8"),
                                 capture_output=True)
        if ignored.returncode not in (0, 1):
            raise RuntimeError(ignored.stderr.decode("utf-8", errors="replace"))
        errors = [f"Fichier indexé malgré .gitignore : {name}"
                  for name in ignored.stdout.decode("utf-8").strip("\0").split("\0") if name]
        total = 0
        for name in files:
            path = root / name
            if path.is_symlink():
                errors.append(f"Lien symbolique à examiner avant publication : {name}")
            elif path.is_file():
                size = path.stat().st_size
                total += size
                if size > max_file_bytes:
                    errors.append(f"Fichier volumineux ({size} octets) : {name}")
        return {"files": files, "bytes": total, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="Lister les fichiers qui pourraient être publiés")
    args = parser.parse_args()
    result = audit(ROOT)
    if args.list:
        print("\n".join(result["files"]))
    for error in result["errors"]:
        print(error)
    print(f"{len(result['files'])} fichiers publiables, {result['bytes'] / 1024:.1f} Kio ; "
          f"{len(result['errors'])} anomalie(s).")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
