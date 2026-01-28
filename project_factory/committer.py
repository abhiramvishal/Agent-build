from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, List

from .config import CreateCommandConfig, Plan
from .safety import SafetyScanner


class CommitterError(RuntimeError):
    pass


class Committer:
    def __init__(self, safety: SafetyScanner) -> None:
        self.safety = safety

    def commit(self, cfg: CreateCommandConfig, plan: Plan, dry_run: bool) -> None:
        """
        Perform staged commits according to plan.commits.

        Each commit is restricted to files under the specific project folder.
        """
        repo_root = cfg.repo_root
        project_root = cfg.project_root

        print(f"[Committer] Repo root: {repo_root}")
        print(f"[Committer] Project root: {project_root}")

        if dry_run:
            print("[Committer/DRY_RUN] Would execute the following commits:")
            for step in plan.commits:
                rel_paths = [str(p.relative_to(repo_root)) for p in self._resolve_paths(step.include_paths)]
                print(f" - {step.message}: {rel_paths}")
            return

        for step in plan.commits:
            include_paths = self._resolve_paths(step.include_paths)
            include_paths = [p for p in include_paths if project_root in p.parents or p == project_root]
            if not include_paths:
                print(f"[Committer] No files to include for commit step {step.name}, skipping.")
                continue

            print(f"[Committer] Preparing commit '{step.message}'")
            self._git_add(repo_root, include_paths)

            # Safety check staged files (limited to project)
            staged = self._get_staged_paths(repo_root)
            staged_in_project = [p for p in staged if project_root in p.parents or p == project_root]
            issues = self.safety.scan_paths(staged_in_project)
            if issues:
                self.safety.print_issues(issues)
                # Reset staged changes for safety
                self._git_reset(repo_root, staged_in_project)
                raise CommitterError("Aborting commit due to potential secrets in staged files.")

            self._git_commit(repo_root, step.message)
        print("[Committer] All planned commits completed.")

    @staticmethod
    def _resolve_paths(paths: Iterable[Path]) -> List[Path]:
        result: List[Path] = []
        for p in paths:
            if p.is_dir():
                result.extend([q for q in p.rglob("*") if q.is_file()])
            elif p.exists():
                result.append(p)
        return result

    @staticmethod
    def _git_add(repo_root: Path, paths: Iterable[Path]) -> None:
        rels = [str(p.relative_to(repo_root)) for p in paths]
        if not rels:
            return
        cmd = ["git", "add"] + rels
        print(f"[Committer] git add {rels}")
        subprocess.check_call(cmd, cwd=str(repo_root))

    @staticmethod
    def _git_reset(repo_root: Path, paths: Iterable[Path]) -> None:
        rels = [str(p.relative_to(repo_root)) for p in paths]
        if not rels:
            return
        cmd = ["git", "reset", "HEAD"] + rels
        print(f"[Committer] git reset HEAD {' '.join(rels)}")
        subprocess.check_call(cmd, cwd=str(repo_root))

    @staticmethod
    def _git_commit(repo_root: Path, message: str) -> None:
        cmd = ["git", "commit", "-m", message]
        print(f"[Committer] git commit -m {message!r}")
        proc = subprocess.run(cmd, cwd=str(repo_root), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            print(proc.stdout)
            raise CommitterError(f"git commit failed with exit {proc.returncode}")
        print(proc.stdout)

    @staticmethod
    def _get_staged_paths(repo_root: Path) -> List[Path]:
        cmd = ["git", "status", "--porcelain"]
        proc = subprocess.run(cmd, cwd=str(repo_root), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            raise CommitterError(f"git status failed with exit {proc.returncode}")
        paths: List[Path] = []
        for line in proc.stdout.splitlines():
            if not line:
                continue
            status = line[:2]
            if status.strip() == "":
                continue
            # staged files have status in first column
            if status[0] != " ":
                rel = line[3:]
                paths.append(repo_root / rel)
        return paths

