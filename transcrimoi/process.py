"""Sous-processus sans shell, sorties sur disque, annulation de l'arbre."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import threading


class Cancelled(RuntimeError):
    pass


class ProcessError(RuntimeError):
    pass


def stop_tree(process: subprocess.Popen) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        # Un enfant peut survivre au processus parent ; tuer le groupe aussi.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        if process.poll() is None:
            process.kill()
    process.wait()


def run_process(args: list[str], stdout: Path, stderr: Path, cancel: threading.Event | None = None) -> None:
    stdout.parent.mkdir(parents=True, exist_ok=True)
    stderr.parent.mkdir(parents=True, exist_ok=True)
    partial = stdout.with_name(stdout.name + ".part")
    process = None
    try:
        if cancel is not None and cancel.is_set():
            raise Cancelled("Traitement annulé")
        with partial.open("wb") as out, stderr.open("wb") as err:
            process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                       start_new_session=os.name == "posix",
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            while True:
                if cancel is not None and cancel.is_set():
                    raise Cancelled("Traitement annulé")
                try:
                    code = process.wait(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
        if code != 0:
            # Lire seulement la fin du journal, même sur un très long traitement.
            with stderr.open("rb") as stream:
                stream.seek(max(0, stderr.stat().st_size - 4000))
                detail = stream.read().decode("utf-8", errors="replace").strip()
            raise ProcessError(f"{Path(args[0]).name} a échoué (code {code}). Journal : {stderr}\n{detail}")
        os.replace(partial, stdout)
    except BaseException:
        if process is not None:
            stop_tree(process)
        raise
    finally:
        partial.unlink(missing_ok=True)
