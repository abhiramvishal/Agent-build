from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any


@dataclass
class CreateCommandConfig:
    repo_root: Path
    project_name: str
    goal: str
    template: str
    ollama_model: str
    dry_run: bool

    @property
    def projects_root(self) -> Path:
        return self.repo_root / "projects"

    @property
    def project_root(self) -> Path:
        return self.projects_root / self.project_name

    @property
    def project_gitignore(self) -> Path:
        return self.project_root / ".gitignore"


@dataclass
class PlanFile:
    path: Path
    description: str


@dataclass
class CommitStep:
    name: str
    message: str
    include_paths: List[Path]


@dataclass
class Plan:
    steps: List[str]
    files: List[PlanFile]
    commits: List[CommitStep]
    meta: Dict[str, Any] = dataclasses.field(default_factory=dict)

