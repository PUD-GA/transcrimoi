"""Adaptation des deux CLI natifs figés ; aucune inférence dans Python."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .storage import read_json, sha256_file


@dataclass(frozen=True)
class Backend:
    cli: Path
    diarize: Path
    asr_model: Path
    diar_model: Path
    vad_model: Path
    provenance: dict

    @classmethod
    def verified(cls, root: Path) -> Backend:
        lock_path = root / "backend.lock.json"
        lock = read_json(lock_path)
        manifest = read_json(root / "build/backend.json")
        if manifest.get("lock_sha256") != sha256_file(lock_path):
            raise ValueError("Build incompatible avec backend.lock.json ; relancer scripts/prepare_backend.py")
        if manifest.get("native_commit") != lock["native"]["commit"] or manifest.get("backend") != "cpu":
            raise ValueError("Build CPU de référence attendu")
        binaries = {}
        for name, item in manifest["binaries"].items():
            path = Path(item["path"])
            if not path.is_absolute():
                path = root / path
            if sha256_file(path) != item["sha256"]:
                raise ValueError(f"Binaire modifié : {path}")
            binaries[name] = path
        models = {}
        for role, item in lock["models"].items():
            path = root / "models" / item["file"]
            if path.stat().st_size != item["size"] or sha256_file(path) != item["sha256"]:
                raise ValueError(f"Modèle corrompu ou incompatible : {path}")
            models[role] = path
        return cls(binaries["parakeet-cli"], binaries["diarize"], models["asr"],
                   models["diarization"], models["vad"], {"lock": lock, "build": manifest})

    def asr_command(self, audio: Path, threads: int) -> list[str]:
        return [str(self.cli), "transcribe", "--model", str(self.asr_model), "--input", str(audio),
                "--decoder", "tdt", "--json", "--threads", str(threads), "--vad",
                "--vad-model", str(self.vad_model), "--vad-max-seg", "30"]

    def diarization_command(self, audio: Path) -> list[str]:
        # Le mode model = 21,12 s avec cache continu, pas de faible latence.
        # Ce CLI ne propose pas --threads ; son défaut natif est conservé.
        return [str(self.diarize), str(self.diar_model), str(audio), "--stream", "model"]
