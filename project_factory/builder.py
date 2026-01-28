from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .config import CreateCommandConfig, Plan
from .ollama_client import OllamaClient


class Builder:
    def __init__(self, templates_root: Path, ollama: OllamaClient) -> None:
        self.templates_root = templates_root
        self.ollama = ollama

    def _make_jinja_env(self, template_dir: Path) -> Environment:
        return Environment(
            loader=FileSystemLoader(str(template_dir)),
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
        )

    def build(self, cfg: CreateCommandConfig, plan: Plan, dry_run: bool) -> None:
        """
        Render the selected template into the target project directory.

        If dry_run is True, only prints what would be rendered.
        """
        template_dir = self.templates_root / cfg.template
        template_json = template_dir / "template.json"
        if not template_json.is_file():
            raise FileNotFoundError(f"Missing template metadata: {template_json}")

        with template_json.open("r", encoding="utf8") as f:
            template_meta: Dict[str, Any] = json.load(f)

        context: Dict[str, Any] = {
            "project_name": cfg.project_name,
            "goal": cfg.goal,
            "ollama_model": cfg.ollama_model,
        }
        context.update(template_meta.get("defaults", {}))

        env = self._make_jinja_env(template_dir)
        project_root = cfg.project_root

        # Jinja-based files
        jinja_files = [
            "README.md.j2",
            "pyproject.toml.j2",
            "app/main.py.j2",
            "app/routers/health.py.j2",
            "tests/test_smoke.py.j2",
        ]

        print(f"[Builder] Target project root: {project_root}")
        for rel in jinja_files:
            src = template_dir / rel
            if not src.is_file():
                raise FileNotFoundError(f"Template file not found: {src}")

            rel_out = rel[:-3] if rel.endswith(".j2") else rel
            dest = project_root / rel_out
            if dry_run:
                print(f"[Builder/DRY_RUN] Would render {src} -> {dest}")
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            template = env.get_template(rel)
            rendered = template.render(**context)
            dest.write_text(rendered, encoding="utf8")
            print(f"[Builder] Rendered {dest}")

        # Ensure per-project gitignore and repo-level safety configs
        self._ensure_project_gitignore(cfg, dry_run)
        self._ensure_project_repo_configs(cfg, dry_run)

        # Use Ollama to further customize README if desired
        readme_path = project_root / "README.md"
        if not dry_run and readme_path.is_file():
            self._post_process_readme(cfg, readme_path)

    def _ensure_project_gitignore(self, cfg: CreateCommandConfig, dry_run: bool) -> None:
        content = (
            "# Project-local ignores\n"
            ".venv/\n"
            "__pycache__/\n"
            ".pytest_cache/\n"
            "*.log\n"
            "data/\n"
            "models/\n"
            "model_dumps/\n"
            ".env\n"
            ".DS_Store\n"
        )
        if dry_run:
            print(f"[Builder/DRY_RUN] Would ensure project .gitignore at {cfg.project_gitignore}")
            return
        cfg.project_gitignore.parent.mkdir(parents=True, exist_ok=True)
        if cfg.project_gitignore.exists():
            existing = cfg.project_gitignore.read_text(encoding="utf8")
            if content.strip() not in existing:
                cfg.project_gitignore.write_text(existing.rstrip() + "\n\n" + content, encoding="utf8")
        else:
            cfg.project_gitignore.write_text(content, encoding="utf8")
        print(f"[Builder] Ensured .gitignore at {cfg.project_gitignore}")

    def _ensure_project_repo_configs(self, cfg: CreateCommandConfig, dry_run: bool) -> None:
        """
        Ensure each generated project has its own pre-commit + gitleaks config
        so that commits inside the project repo are protected.
        """
        project_root = cfg.project_root
        pre_commit_path = project_root / ".pre-commit-config.yaml"
        gitleaks_path = project_root / ".gitleaks.toml"

        pre_commit_content = (
            "repos:\n"
            "  - repo: https://github.com/psf/black\n"
            "    rev: 24.4.2\n"
            "    hooks:\n"
            "      - id: black\n"
            "        language_version: python3\n"
            "\n"
            "  - repo: https://github.com/pycqa/isort\n"
            "    rev: 5.13.2\n"
            "    hooks:\n"
            "      - id: isort\n"
            "        args: [\"--profile\", \"black\"]\n"
            "\n"
            "  - repo: https://github.com/pre-commit/pre-commit-hooks\n"
            "    rev: v4.6.0\n"
            "    hooks:\n"
            "      - id: check-yaml\n"
            "      - id: end-of-file-fixer\n"
            "      - id: trailing-whitespace\n"
            "\n"
            "  - repo: https://github.com/gitleaks/gitleaks\n"
            "    rev: v8.18.2\n"
            "    hooks:\n"
            "      - id: gitleaks\n"
            "        args: [\"protect\", \"--staged\", \"--config=.gitleaks.toml\"]\n"
        )

        gitleaks_content = (
            "title = \"Project Factory gitleaks config\"\n"
            "\n"
            "[allowlist]\n"
            "description = \"Allow some common test secrets\"\n"
            "regexes = [\n"
            "  '''dummysecret''',\n"
            "  '''example_key''',\n"
            "]\n"
            "\n"
            "[[rules]]\n"
            "id = \"generic-api-key\"\n"
            "description = \"Generic API Key\"\n"
            "regex = '''(?i)(api[_-]?key|token)[^a-zA-Z0-9]?[\\'\\\"]?[0-9a-zA-Z\\-_=]{16,}'''\n"
            "tags = [\"key\", \"api\", \"generic\"]\n"
            "\n"
            "[[rules]]\n"
            "id = \"private-key\"\n"
            "description = \"Private key block\"\n"
            "regex = '''-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----'''\n"
            "tags = [\"key\", \"private\", \"pem\"]\n"
        )

        if dry_run:
            print(f"[Builder/DRY_RUN] Would ensure .pre-commit-config.yaml and .gitleaks.toml in {project_root}")
            return

        if not pre_commit_path.exists():
            pre_commit_path.write_text(pre_commit_content, encoding="utf8")
            print(f"[Builder] Created {pre_commit_path}")
        if not gitleaks_path.exists():
            gitleaks_path.write_text(gitleaks_content, encoding="utf8")
            print(f"[Builder] Created {gitleaks_path}")

    def _post_process_readme(self, cfg: CreateCommandConfig, readme_path: Path) -> None:
        """
        Ask Ollama to enrich the README a bit using the goal.
        """
        base = readme_path.read_text(encoding="utf8")
        prompt = (
            "You are improving a README for a small FastAPI project.\n"
            f"Project goal: {cfg.goal}\n\n"
            "Existing README content:\n"
            "-----\n"
            f"{base}\n"
            "-----\n\n"
            "Produce an improved README.md that keeps setup and run instructions but explains "
            "the purpose and endpoints clearly in concise, production-friendly language."
        )
        try:
            updated = self.ollama.generate(model=cfg.ollama_model, prompt=prompt)
        except Exception as exc:  # noqa: BLE001
            print(f"[Builder] Ollama README customization failed ({exc}), keeping original README.")
            return
        readme_path.write_text(updated, encoding="utf8")
        print(f"[Builder] Updated README.md via Ollama at {readme_path}")

