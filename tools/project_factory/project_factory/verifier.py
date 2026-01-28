from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List

from .config import CreateCommandConfig


class VerifierError(RuntimeError):
    pass


class Verifier:
    def __init__(self) -> None:
        ...

    def verify(self, cfg: CreateCommandConfig, dry_run: bool) -> None:
        """
        Create venv, install deps, run py_compile and pytest.

        Raises VerifierError on failure.
        """
        project_root = cfg.project_root
        venv_path = project_root / ".venv"

        commands: List[str] = []

        # venv creation (prefer uv)
        if self._have_command("uv"):
            commands.append(f"uv venv {venv_path}")
        else:
            commands.append(f"{sys.executable} -m venv {venv_path}")

        venv_python = self._venv_python_executable(venv_path)

        # installation
        commands.append(f"{venv_python} -m pip install -e {project_root}")

        # py_compile and pytest
        commands.append(f"{venv_python} -m compileall {project_root}")
        commands.append(f"{venv_python} -m pytest -q {project_root}")

        if dry_run:
            print("[Verifier/DRY_RUN] Would run verification commands:")
            for cmd in commands:
                print(" -", cmd)
            return

        print("[Verifier] Creating virtualenv and running tests...")
        if self._have_command("uv"):
            self._run(["uv", "venv", str(venv_path)], cwd=project_root)
        else:
            self._run([sys.executable, "-m", "venv", str(venv_path)], cwd=project_root)

        venv_python = self._venv_python_executable(venv_path)
        self._run([venv_python, "-m", "pip", "install", "-e", "."], cwd=project_root)
        self._run([venv_python, "-m", "compileall", "."], cwd=project_root)
        self._run([venv_python, "-m", "pytest", "-q"], cwd=project_root)
        print("[Verifier] Verification succeeded.")

    @staticmethod
    def _have_command(name: str) -> bool:
        from shutil import which

        return which(name) is not None

    @staticmethod
    def _venv_python_executable(venv: Path) -> str:
        if os.name == "nt":
            return str(venv / "Scripts" / "python.exe")
        return str(venv / "bin" / "python")

    @staticmethod
    def _run(cmd: List[str], cwd: Path) -> None:
        print(f"[Verifier] Running: {' '.join(cmd)} (cwd={cwd})")
        proc = subprocess.run(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if proc.returncode != 0:
            print(proc.stdout)
            raise VerifierError(f"Command failed with exit code {proc.returncode}: {' '.join(cmd)}")
        if proc.stdout:
            print(proc.stdout)

