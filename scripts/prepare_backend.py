#!/usr/bin/env python3
"""Préparation développeur : runtime figé, modèles vérifiés. Pas un installateur."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from transcrimoi.model_verification import remember_verified_model, verify_model
from transcrimoi.storage import sha256_file, write_json


def run(*args: str) -> None:
    subprocess.run(args, check=True, cwd=ROOT)


def download(model: dict, repository: str, revision: str, *, directory: Path | None = None) -> None:
    target = (directory if directory is not None else ROOT / "models") / model["file"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        try:
            verify_model(target, size=model["size"], sha256=model["sha256"], force=True)
        except ValueError as error:
            raise ValueError(f"Modèle existant non conforme : {target}. Le déplacer avant de réessayer.") from error
        print(f"Vérifié : {target.name}", flush=True)
        return
    url = f"https://huggingface.co/{repository}/resolve/{revision}/{model['file']}"
    tmp = target.with_suffix(".gguf.part")
    print(f"Téléchargement : {target.name} ({model['size'] / 1e6:.1f} Mo)", flush=True)
    try:
        with urllib.request.urlopen(url, timeout=120) as source, tmp.open("wb") as dest:
            while block := source.read(1024 * 1024):
                dest.write(block)
        if tmp.stat().st_size != model["size"] or sha256_file(tmp) != model["sha256"]:
            raise ValueError(f"Taille ou SHA-256 incorrect : {target.name}")
        os.replace(tmp, target)
        remember_verified_model(target, size=model["size"], sha256=model["sha256"])
    finally:
        tmp.unlink(missing_ok=True)


def download_locked_models(lock: dict) -> None:
    """Chaque modèle peut remplacer le dépôt/révision communs du verrou."""
    for model in lock["models"].values():
        download(model, model.get("repository", lock["model_repository"]),
                 model.get("revision", lock["model_revision"]))


def apply_ggml_patches(source: Path) -> None:
    """Même série amont, appliquée sans Bash (notamment sans le Bash WSL)."""
    ggml = source / "third_party/ggml"
    patches = sorted((source / "third_party/ggml-patches").glob("*.patch"))
    if not patches:
        raise FileNotFoundError("Série de correctifs GGML absente du runtime figé")
    for patch in patches:
        command = ["git", "-C", str(ggml), "apply"]
        reverse = subprocess.run([*command, "--check", "--reverse", str(patch.resolve())],
                                 capture_output=True)
        if reverse.returncode == 0:
            print(f"Correctif déjà appliqué : {patch.name}", flush=True)
            continue
        forward = subprocess.run([*command, "--check", str(patch.resolve())], capture_output=True)
        if forward.returncode:
            raise RuntimeError(f"Correctif GGML incompatible : {patch.name}\n"
                               + forward.stderr.decode("utf-8", errors="replace"))
        subprocess.run([*command, str(patch.resolve())], check=True)
        print(f"Correctif appliqué : {patch.name}", flush=True)


def find_binary(build: Path, name: str, *, windows: bool | None = None) -> Path:
    """Générateurs CMake mono-configuration et Visual Studio/Xcode Release."""
    suffix = ".exe" if (os.name == "nt" if windows is None else windows) else ""
    for directory in (build / "examples/cli/Release", build / "examples/cli",
                      build / "bin/Release", build / "bin", build / "Release", build):
        candidate = directory / (name + suffix)
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Exécutable {name}{suffix} absent dans {build}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-models", action="store_true", help="Télécharger les trois GGUF (environ 1,14 Go)")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    lock = json.loads((ROOT / "backend.lock.json").read_text())
    if not args.skip_build:
        source = ROOT / "vendor/parakeet.cpp"
        if not source.exists():
            source.parent.mkdir(parents=True, exist_ok=True)
            run("git", "clone", lock["native"]["repository"], str(source))
        head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        if head != lock["native"]["commit"]:
            run("git", "-C", str(source), "checkout", "--detach", lock["native"]["commit"])
        run("git", "-C", str(source), "submodule", "update", "--init", "third_party/ggml")
        ggml_head = subprocess.check_output(["git", "-C", str(source / "third_party/ggml"), "rev-parse", "HEAD"], text=True).strip()
        if ggml_head != lock["native"]["ggml_commit"]:
            raise ValueError("Référence GGML inattendue")
        # Ne pas laisser CMake choisir accidentellement le Bash de WSL sous Windows.
        apply_ggml_patches(source)
        options = [f"-D{k}={v}" for k, v in lock["native"]["cmake_options"].items()]
        run("cmake", "-S", str(source), "-B", str(ROOT / "build/native"), *options)
        targets = ["parakeet-cli", "diarize", "test_sas_merge", "test_vad_segmenter"]
        run("cmake", "--build", str(ROOT / "build/native"), "--config", "Release",
            "--parallel", str(args.jobs), "--target", *targets)
        binaries = {name: find_binary(ROOT / "build/native", name)
                    for name in ("parakeet-cli", "diarize")}
        write_json(ROOT / "build/backend.json", {
            "schema_version": 1,
            "native_commit": lock["native"]["commit"],
            "ggml_commit": ggml_head,
            "ggml_patch_diff_sha256": hashlib.sha256(subprocess.check_output(
                ["git", "-C", str(source / "third_party/ggml"), "diff", "--binary"])).hexdigest(),
            "cmake_options": lock["native"]["cmake_options"],
            "backend": "cpu",
            "lock_sha256": sha256_file(ROOT / "backend.lock.json"),
            "binaries": {name: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}
                         for name, path in binaries.items()},
        })
    if args.download_models:
        download_locked_models(lock)


if __name__ == "__main__":
    main()
