from __future__ import annotations

import argparse
from pathlib import Path

from .builder import Builder
from .committer import Committer
from .config import CreateCommandConfig
from .ollama_client import OllamaClient
from .planner import Planner
from .safety import SafetyScanner
from .verifier import Verifier


def _parse_bool(value: str) -> bool:
    v = value.strip().lower()
    if v in {"true", "1", "yes", "y"}:
        return True
    if v in {"false", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="project_factory", description="Project Factory Agent using local Ollama.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a new project inside this repo.")
    create.add_argument("--repo", required=True, help="Path to git repo root.")
    create.add_argument("--name", required=True, help="Project name (directory under projects/).")
    create.add_argument("--goal", required=True, help="What to build (natural language).")
    create.add_argument("--template", required=True, help="Template to use (e.g. fastapi_basic).")
    create.add_argument("--ollama-model", required=True, help="Ollama model id (e.g. qwen2.5:7b).")
    create.add_argument(
        "--dry-run",
        type=_parse_bool,
        default=True,
        help="If true (default), only print planned changes and commands without modifying anything.",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "create":
        run_create(
            repo_root=Path(args.repo).resolve(),
            project_name=args.name,
            goal=args.goal,
            template=args.template,
            ollama_model=args.ollama_model,
            dry_run=args.dry_run,
        )
    else:
        parser.error(f"Unknown command {args.command!r}")


def run_create(
    repo_root: Path,
    project_name: str,
    goal: str,
    template: str,
    ollama_model: str,
    dry_run: bool,
) -> None:
    cfg = CreateCommandConfig(
        repo_root=repo_root,
        project_name=project_name,
        goal=goal,
        template=template,
        ollama_model=ollama_model,
        dry_run=dry_run,
    )

    print(f"[CLI] repo_root={cfg.repo_root}")
    print(f"[CLI] project_root={cfg.project_root}")
    print(f"[CLI] template={cfg.template}")
    print(f"[CLI] goal={cfg.goal}")
    print(f"[CLI] ollama_model={cfg.ollama_model}")
    print(f"[CLI] dry_run={cfg.dry_run}")

    planner = Planner()
    ollama = OllamaClient()
    builder = Builder(templates_root=Path(__file__).resolve().parent / "templates", ollama=ollama)
    verifier = Verifier()
    safety = SafetyScanner()
    committer = Committer(safety=safety)

    # Plan
    plan = planner.plan(cfg)
    print("\n[Plan] Steps:")
    for step in plan.steps:
        print(" -", step)
    print("\n[Plan] Files:")
    for f in plan.files:
        print(f" - {f.path}: {f.description}")
    print("\n[Plan] Commits:")
    for c in plan.commits:
        incl = ", ".join(str(p) for p in c.include_paths)
        print(f" - {c.message}: {incl}")

    if dry_run:
        print("\n[CLI] DRY RUN: stopping after planning. No files will be written.")
        # Show verification & commit commands that would be run
        verifier.verify(cfg, dry_run=True)
        committer.commit(cfg, plan, dry_run=True)
        return

    # Ensure base projects directory exists
    cfg.projects_root.mkdir(parents=True, exist_ok=True)

    # Build
    builder.build(cfg, plan, dry_run=False)

    # Verify
    verifier.verify(cfg, dry_run=False)

    # Commit
    committer.commit(cfg, plan, dry_run=False)


if __name__ == "__main__":
    main()

