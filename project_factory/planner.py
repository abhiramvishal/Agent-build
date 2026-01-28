from __future__ import annotations

from pathlib import Path
from typing import List

from .config import CreateCommandConfig, Plan, PlanFile, CommitStep


class Planner:
    """
    Simple but explicit planner: produces
    - steps
    - file manifest
    - commit plan
    """

    TEMPLATE_FASTAPI_BASIC = "fastapi_basic"

    def plan(self, cfg: CreateCommandConfig) -> Plan:
        if cfg.template != self.TEMPLATE_FASTAPI_BASIC:
            raise ValueError(f"Unsupported template: {cfg.template!r}")

        project_root = cfg.project_root

        steps: List[str] = [
            "Create project directory under projects/<name>/",
            "Render FastAPI template files using Jinja2.",
            "Fill AI-specific logic and README using Ollama.",
            "Create per-project .gitignore with safe defaults.",
            "Create virtualenv and install project dependencies.",
            "Run python -m py_compile and pytest -q inside the project venv.",
            "If verification succeeds, create multiple git commits for the project only.",
        ]

        files: List[PlanFile] = [
            PlanFile(project_root / "pyproject.toml", "Project metadata and dependencies for the FastAPI app"),
            PlanFile(project_root / "README.md", "Project README customized based on the goal"),
            PlanFile(project_root / "app" / "__init__.py", "Package marker"),
            PlanFile(project_root / "app" / "main.py", "FastAPI application entrypoint with /health and /generate"),
            PlanFile(project_root / "app" / "routers" / "__init__.py", "Package marker"),
            PlanFile(project_root / "app" / "routers" / "health.py", "Health check router for /health"),
            PlanFile(project_root / "tests" / "test_smoke.py", "Smoke test hitting /health endpoint"),
            PlanFile(project_root / ".gitignore", "Per-project ignore rules (.venv, caches, data, model dumps)"),
        ]

        # Commit plan: 3–4 commits
        commits: List[CommitStep] = [
            CommitStep(
                name="scaffold",
                message=f"Scaffold FastAPI project {cfg.project_name}",
                include_paths=[
                    project_root / "pyproject.toml",
                    project_root / "app",
                    project_root / "tests",
                    project_root / ".gitignore",
                ],
            ),
            CommitStep(
                name="ai_customization",
                message=f"Customize {cfg.project_name} AI behavior and endpoints",
                include_paths=[
                    project_root / "app" / "main.py",
                    project_root / "README.md",
                ],
            ),
            CommitStep(
                name="tests_and_docs",
                message=f"Add tests and docs for {cfg.project_name}",
                include_paths=[
                    project_root / "tests",
                    project_root / "README.md",
                ],
            ),
        ]

        return Plan(steps=steps, files=files, commits=commits, meta={"template": cfg.template, "goal": cfg.goal})

