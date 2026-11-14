"""Cache local d'intégrité des modèles ; pas une protection contre une altération hostile."""
from __future__ import annotations

from pathlib import Path

from .runtime import model_cache_directory
from .storage import fingerprint, read_json, sha256_file, write_json


def _signature(path: Path, size: int, sha256: str) -> dict:
    stat = path.stat()
    if stat.st_size != size:
        raise ValueError(f"Modèle corrompu ou incompatible : {path}")
    return {
        "schema_version": 1, "path": str(path.resolve()), "sha256": sha256,
        "size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "ctime_ns": stat.st_ctime_ns,
        "device": stat.st_dev, "inode": stat.st_ino,
    }


def _cache_path(path: Path) -> Path:
    directory = model_cache_directory()
    if directory is not None:
        return directory / f"{fingerprint(str(path.resolve()))}.json"
    return path.with_name(f".{path.name}.verified.json")


def _save(path: Path, signature: dict) -> None:
    try:
        write_json(_cache_path(path), signature)
    except OSError:
        # Runtime en lecture seule : l'intégrité reste vérifiée, mais sans cache.
        pass


def remember_verified_model(path: Path, *, size: int, sha256: str) -> None:
    """Mémoriser un modèle dont l'appelant vient de vérifier le contenu par SHA-256."""
    _save(path, _signature(path, size, sha256))


def verify_model(path: Path, *, size: int, sha256: str, force: bool = False) -> None:
    """Vérifier le contenu si le cache est absent, invalide, périmé ou forcé."""
    signature = _signature(path, size, sha256)
    if not force:
        try:
            if read_json(_cache_path(path)) == signature:
                return
        except (OSError, ValueError):
            pass
    actual = sha256_file(path)
    if _signature(path, size, sha256) != signature:
        raise ValueError(f"Le modèle a changé pendant sa vérification : {path}")
    if actual != sha256:
        raise ValueError(f"Modèle corrompu ou incompatible : {path}")
    _save(path, signature)
