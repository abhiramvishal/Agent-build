## Project Factory Agent

This is a **production-focused V1 Project Factory Agent** that creates small AI projects inside this repo under `projects/<project_name>/`, using **local Ollama** for generation, then optionally runs verification and makes multiple commits.

Ollama is the only model backend; **no paid APIs** are used.

---

### Requirements

- Python 3.10+
- Git installed and initialized in this repository
- [Ollama](https://ollama.com/) installed and running locally
- Network access to `http://localhost:11434`

Before using the agent:

1. Install Python dependencies (prefer `uv`, fallback to `pip`):

   ```bash
   cd tools/project_factory

   # Using uv (recommended)
   uv venv .venv
   . .venv/bin/activate  # Windows: .venv\Scripts\activate
   uv pip install -e .

   # Or using pip
   python -m venv .venv
   . .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -e .
   ```

2. Ensure Ollama is running and the model is available:

   ```bash
   ollama serve
   ollama pull qwen2.5:7b
   ```

---

### CLI Usage

From this repository root (recommended):

```bash
cd tools/project_factory
python -m project_factory create \
  --repo .. \
  --name my-fastapi-app \
  --goal "Simple FastAPI service with /generate backed by Ollama" \
  --template fastapi_basic \
  --ollama-model qwen2.5:7b \
  --dry-run false
```

Arguments:

- `--repo`: path to the git repository root (e.g. `..` from `tools/project_factory`)
- `--name`: project name; project will be created under `projects/<name>/`
- `--goal`: natural language goal for the project
- `--template`: template key; currently `fastapi_basic`
- `--ollama-model`: Ollama model id, e.g. `qwen2.5:7b`
- `--dry-run`: **string** flag, default `"true"`.
  - `"true"`: plan only (no file writes or commits)
  - `"false"`: execute: build, verify, and commit

Examples:

```bash
# Dry run (default)
python -m project_factory create --repo .. --name demo --goal "Demo FastAPI app" --template fastapi_basic --ollama-model qwen2.5:7b

# Explicit dry run
python -m project_factory create --repo .. --name demo --goal "Demo" --template fastapi_basic --ollama-model qwen2.5:7b --dry-run true

# Actually create, verify, and commit
python -m project_factory create --repo .. --name demo --goal "Demo" --template fastapi_basic --ollama-model qwen2.5:7b --dry-run false
```

---

### What the Agent Does

1. **Planning**
   - Reads the requested `--goal` and `--template`.
   - Produces:
     - high-level steps,
     - a file manifest,
     - a **commit plan** (3–6 commits per project).

2. **Building**
   - Renders template files from `project_factory/templates/<template>/` using **Jinja2**.
   - Uses **Ollama** to:
     - fill AI logic placeholders,
     - customize the project `README.md` based on the goal.
   - Ensures a per-project `.gitignore` with:
     - `.venv/`, `__pycache__/`, `.pytest_cache/`, logs, data, model outputs, etc.

3. **Verification**
   - Creates a virtual environment under `projects/<name>/.venv`:
     - prefers `uv venv` when `uv` is available,
     - falls back to `python -m venv`.
   - Installs the project into that venv (`pip install -e .`).
   - Runs:
     - `python -m py_compile` on all `.py` files,
     - `pytest -q`.
   - If verification **fails**, the agent prints the error and **aborts without committing**.

4. **Committing**
   - Uses `subprocess` to call `git` (no heavy wrappers).
   - Uses `git status --porcelain` to control which files are staged.
   - Follows the planner’s commit plan; each commit only includes files inside `projects/<name>/`.
   - Includes a final docs-oriented commit (e.g. updated README) if applicable.

5. **Safety**
   - Enforces deny patterns (never commits these if detected):
     - `.env`
     - `*.pem`
     - `*.key`
     - `id_rsa`
     - `*.p12`
     - `config*.json` containing secrets
   - Runs a lightweight content scanner on staged files before each commit, looking for:
     - Access tokens (e.g. `AKIA[0-9A-Z]{16}`, common OAuth/Bearer patterns),
     - Private key headers (`-----BEGIN PRIVATE KEY-----`, etc.).
   - If a risk is detected, the commit is **aborted** with details printed.

---

### Generated FastAPI Template (`fastapi_basic`)

The `fastapi_basic` template generates a fully working FastAPI app:

- `app/main.py`
  - `/health` endpoint returning 200.
  - `/generate` endpoint:
    - Accepts JSON: `{ "prompt": "...", "max_tokens": 200 }`.
    - Calls **local Ollama** to generate a response.
- `app/routers/health.py`
  - Isolated health router with `/health` route.
- `tests/test_smoke.py`
  - Uses `fastapi.testclient.TestClient` to hit `/health` and assert HTTP 200.
- `README.md`
  - Customized via Ollama based on your `--goal`.
  - Contains:
    - Setup instructions (venv + install),
    - Run instructions: `uvicorn app.main:app --reload`,
    - Notes about `/health` and `/generate`.

---

### Dry Run Behavior

- `--dry-run` defaults to `"true"`.
- In **dry run** mode, the agent will:
  - Show the **plan**, including:
    - steps,
    - file manifest,
    - commit plan.
  - Show which commands it would run for:
    - building,
    - verification,
    - committing.
  - **NOT** write any files.
  - **NOT** create or run any virtual environments.
  - **NOT** run git commands that mutate state.

To actually create and commit a project, pass `--dry-run false`.

---

### Notes

- The agent is designed to work on **Windows and macOS**:
  - All subprocess calls avoid shell-specific syntax when possible.
  - Virtualenv paths handle both `Scripts` (Windows) and `bin` (POSIX).
- The agent only writes inside:
  - `projects/<project_name>/`
  - `tools/project_factory/` (this tool’s own code)
- Root-level `.pre-commit-config.yaml`, `.gitleaks.toml`, and `.gitignore` are expected to exist and are provided as part of this initial version, but the agent’s per-project commits are limited to the project folder.

