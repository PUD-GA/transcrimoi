#!/usr/bin/env python3
"""Préversion autonome PyInstaller, modèles inclus. Pas une release signée/notariée."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import threading
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from transcrimoi import __version__
from transcrimoi.backend import Backend
from transcrimoi.process import run_process
from transcrimoi.storage import read_json, sha256_file, write_json


def artifact_name() -> str:
    system = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}[platform.system()]
    machine = {"AMD64": "x86_64", "aarch64": "arm64"}.get(platform.machine(), platform.machine())
    return f"transcrimoi-preview-{__version__}-{system}-{machine}"


def find_ffmpeg() -> Path:
    found = shutil.which("ffmpeg")
    if not found:
        raise FileNotFoundError("FFmpeg introuvable")
    path = Path(found).resolve()
    if os.name == "nt" and "chocolatey" in str(path).lower():
        # Ne pas embarquer le shim Chocolatey, qui dépend de son installation hôte.
        install = Path(os.environ.get("ChocolateyInstall", r"C:\ProgramData\chocolatey"))
        candidates = list((install / "lib/ffmpeg/tools").rglob("ffmpeg.exe"))
        if len(candidates) != 1:
            raise ValueError("FFmpeg Chocolatey ambigu ; fournir --ffmpeg avec le vrai exécutable")
        path = candidates[0].resolve()
    return path


def stage_runtime(root: Path, stage: Path, ffmpeg: Path) -> None:
    backend = Backend.verified(root)
    stage.mkdir(parents=True, exist_ok=False)
    (stage / "bin").mkdir()
    (stage / "models").mkdir()
    (stage / "build").mkdir()
    shutil.copy2(root / "backend.lock.json", stage / "backend.lock.json")
    manifest = read_json(root / "build/backend.json")
    for name, source in (("parakeet-cli", backend.cli), ("diarize", backend.diarize)):
        target = stage / "bin" / (name + (".exe" if os.name == "nt" else ""))
        shutil.copy2(source, target)
        manifest["binaries"][name] = {"path": target.relative_to(stage).as_posix(), "sha256": sha256_file(target)}
    shutil.copy2(ffmpeg, stage / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg"))
    for model in backend.provenance["lock"]["models"].values():
        shutil.copy2(root / "models" / model["file"], stage / "models" / model["file"])
    write_json(stage / "build/backend.json", manifest)


def collect_notices(root: Path, stage: Path, ffmpeg: Path) -> None:
    notices = stage / "notices"
    notices.mkdir()
    for source, name in ((root / "docs/paquets-autonomes.md", "LISEZ-MOI.md"),
                         (root / "docs/composants-tiers.md", "composants-tiers.md"),
                         (root / "docs/formats-export.md", "FORMATS.md"),
                         (root / "vendor/parakeet.cpp/LICENSE", "parakeet.cpp-LICENSE"),
                         (root / "vendor/parakeet.cpp/third_party/ggml/LICENSE", "ggml-LICENSE")):
        shutil.copy2(source, notices / name)
    lock = read_json(stage / "backend.lock.json")
    base = f"https://huggingface.co/{lock['model_repository']}/resolve/{lock['model_revision']}/licenses"
    sources = {name: f"{base}/{name}.txt" for name in ("CC-BY-4.0", "MIT", "OpenMDW-1.1")}
    asr = lock["models"]["asr"]
    sources["FluidSpeechPro-LICENSE"] = f"https://huggingface.co/{asr['repository']}/resolve/{asr['revision']}/LICENSE"
    for name, url in sources.items():
        with urllib.request.urlopen(url, timeout=60) as response:
            (notices / f"{name}.txt").write_bytes(response.read())
    (notices / "attributions.txt").write_text(
        "Fluid Speech Pro by FluidVoice — CC BY 4.0\n"
        "Dérivé de NVIDIA Parakeet v3 et Moondream Parakeet Ultra.\n"
        "Nemotron-3-Diarization (NVIDIA), Silero VAD (Silero Team).\n"
        "Les poids sont inchangés ; runtime GGUF avec parakeet.cpp/GGML.\n"
        "Notices collectées pour validation, audit de redistribution encore requis.\n", encoding="utf-8")
    for name in ("PySide6-Essentials", "shiboken6", "pyinstaller"):
        dist = importlib.metadata.distribution(name)
        for entry in dist.files or []:
            if any(word in str(entry).lower() for word in ("license", "copying", "copyright")):
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    # Garder la hiérarchie, mais jamais sortir du dossier de notices.
                    relative = Path(*[part for part in entry.parts if part not in ("..", ".")])
                    target = notices / name / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    candidates = [Path(sys.base_prefix) / "LICENSE.txt", Path("/usr/share/doc/ffmpeg/copyright")]
    candidates += [Path("/usr/share/common-licenses") / name for name in ("GPL-2", "GPL-3", "LGPL-2.1", "LGPL-3")]
    for index, source in enumerate(candidates):
        if source.is_file():
            shutil.copy2(source, notices / f"system-{index}-{source.name}")
    for option, name in (("-version", "ffmpeg-build.txt"), ("-L", "ffmpeg-license.txt")):
        result = subprocess.run([str(ffmpeg), option], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (notices / name).write_bytes(result.stdout)
    write_json(notices / "sources.json", sources)


def stamp_manifest(runtime: Path) -> None:
    """PyInstaller peut modifier RPATH/signatures : empreintes des fichiers finaux."""
    manifest = read_json(runtime / "build/backend.json")
    for item in manifest["binaries"].values():
        item["sha256"] = sha256_file(runtime / item["path"])
    manifest["package"] = {"application": __version__, "platform": platform.platform(),
                           "machine": platform.machine(), "python": platform.python_version(),
                           "pyinstaller": importlib.metadata.version("pyinstaller"),
                           "preview": True, "signed_for_distribution": False}
    write_json(runtime / "build/backend.json", manifest)


def archive_bundle(bundle: Path, destination: Path) -> Path:
    if sys.platform == "darwin":
        archive = Path(str(destination) + ".app.zip")
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(bundle), str(archive)], check=True)
    elif os.name == "nt":
        archive = Path(shutil.make_archive(str(destination), "zip", bundle.parent, bundle.name))
    else:
        archive = Path(str(destination) + ".tar.gz")
        with tarfile.open(archive, "w:gz") as stream:
            stream.add(bundle, arcname="transcrimoi")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist/desktop")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build/desktop")
    parser.add_argument("--ffmpeg", type=Path, help="Vrai exécutable, pas un shim")
    args = parser.parse_args()
    output, work = args.output_dir.resolve(), args.work_dir.resolve()
    if work.exists():
        parser.error("Le dossier de build existe ; choisir un nouveau --work-dir")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.glob(artifact_name() + "*")):
        parser.error("Le paquet existe déjà ; choisir un nouveau --output-dir")
    ffmpeg = args.ffmpeg.resolve() if args.ffmpeg else find_ffmpeg()
    stage_runtime(ROOT, work / "runtime", ffmpeg)
    collect_notices(ROOT, work / "runtime", ffmpeg)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--distpath", str(work / "dist"), "--workpath", str(work / "pyinstaller"),
                    str(ROOT / "scripts/transcrimoi.spec")], check=True,
                   env={**os.environ, "TRANSCRIMOI_PACKAGE_STAGE": str(work / "runtime")})
    if sys.platform == "darwin":
        bundle = work / "dist/transcrimoi.app"
        runtime = bundle / "Contents/Frameworks"
        executable = bundle / "Contents/MacOS/transcrimoi"
    else:
        bundle = work / "dist/transcrimoi"
        runtime = bundle / "_internal"
        executable = bundle / ("Transcrimoi.exe" if os.name == "nt" else "transcrimoi")
    stamp_manifest(runtime)
    if sys.platform == "darwin":
        # Ressources modifiées après la signature PyInstaller : resignature de
        # l'enveloppe seulement, sans retoucher les binaires déjà empreintés.
        subprocess.run(["codesign", "--force", "--sign", "-", str(bundle)], check=True)
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(bundle)], check=True)
    cancel = threading.Event()
    timer = threading.Timer(300, cancel.set)
    timer.start()
    previous = Path.cwd()
    try:
        # Lancer hors du dépôt, avec le Python et le FFmpeg embarqués uniquement.
        os.chdir(work)
        run_process([str(executable), "--self-test", str(work / "self-test")],
                    work / "self-test.stdout", work / "self-test.log", cancel)
    finally:
        os.chdir(previous)
        timer.cancel()
    report = read_json(work / "self-test/report.json")
    if report.get("status") != "completed" or not report.get("frozen"):
        raise RuntimeError("Le diagnostic du paquet autonome n'a pas abouti")
    archive = archive_bundle(bundle, output / artifact_name())
    write_json(output / f"{archive.name}.sha256.json", {"file": archive.name, "bytes": archive.stat().st_size,
                                                      "sha256": sha256_file(archive)})
    shutil.copy2(work / "self-test/report.json", output / f"{artifact_name()}-self-test.json")
    print(f"Préversion créée : {archive}", flush=True)


if __name__ == "__main__":
    main()
