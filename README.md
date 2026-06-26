# tiny-agents-md

Keep `AGENTS.md` small, factual, and safe.

Generate and audit minimal agent instruction files without an LLM.

```bash
$ python -m tiny_agents_md doctor . --explain

AGENTS.md Health Report

File: AGENTS.md
Score: 100/100
Rating: excellent

Issues: none

Valid Commands:
- `make agents` from Makefile:agents
- `make doctor` from Makefile:doctor
- `make install` from Makefile:install
- `make lint` from Makefile:lint
- `make test` from Makefile:test
- `python -m compileall tiny_agents_md tests` from Makefile:lint
- `python -m pip install -e .` from Makefile:install
- `python -m tiny_agents_md doctor . --explain` from Makefile:doctor
- `python -m tiny_agents_md loop .` from Makefile:agents
- `python -m unittest discover -v` from Makefile:test

Valid Paths:
- `skills/` (config)
- `tiny_agents_md/` (source)
- `tests/` (tests)
```

Preview a generated file when you need one:

```bash
$ python -m tiny_agents_md init .
```

Write only when you are ready:

```bash
$ tiny-agents-md init . --write
```

## Why

Agent instruction files usually fail in boring ways:

- they mention commands that do not exist
- they reference stale paths
- they copy generic project prose
- they grow too long for coding agents to use well

`tiny-agents-md` keeps `AGENTS.md` small, factual, and checkable. It scans the
repository, writes only facts it can verify, and gives existing instruction files
a score with concrete issues.

## What It Checks

- commands from `package.json`, `pyproject.toml`, `Makefile`, `Cargo.toml`, and
  `go.mod`
- real project paths such as source, test, docs, config, and generated dirs
- package-manager conflicts such as npm vs pnpm vs yarn
- missing test commands
- generic boilerplate and README duplication
- generated directories without a do-not-edit rule

The first version is deterministic and local-only. It does not call an LLM,
embedding API, MCP server, or remote model.

Python command detection is intentionally conservative: it only emits commands
that are backed by recognized project files or Makefile targets.

## Install

Requires Python 3.11+.

From GitHub:

```bash
pipx install git+https://github.com/vinnnno/tiny-agents-md.git
```

From a local checkout:

```bash
python -m pip install -e .
```

You can also run it without installing:

```bash
python -m tiny_agents_md doctor . --explain
```

## Usage

Generate `AGENTS.md`:

```bash
tiny-agents-md init .
tiny-agents-md init . --dry-run
tiny-agents-md init . --write
```

`init` previews a diff by default. `--write` creates `AGENTS.md` when it does
not exist. If `AGENTS.md` already exists, use `--write --force` to overwrite it.

Check an existing file:

```bash
tiny-agents-md doctor .
tiny-agents-md doctor . --explain
tiny-agents-md doctor . --json --explain
```

Check another instruction file against the same repo facts:

```bash
tiny-agents-md doctor . --file CLAUDE.md
```

Use a stricter exit-code threshold:

```bash
tiny-agents-md doctor . --min-score 90
```

Regenerate and check until the file is stable:

```bash
tiny-agents-md loop .
```

## Example Output

```md
# AGENTS.md

## Project Commands
- Test: `pnpm test`
- Lint: `pnpm lint`

## Project Structure
- `src/`
- `tests/`
- `dist/` generated, do not edit

## Agent Rules
- Do not modify generated files.
- Prefer small, safe diffs.
- Run the test command before finishing when code changes.
- Do not invent commands or file paths.
```

## CLI

- `init`: scan repository files and render a minimal `AGENTS.md`
- `init --write --force`: overwrite an existing generated file intentionally
- `doctor`: check an existing agent instruction file for factual issues
- `loop`: regenerate, run `doctor`, and stop when the file is stable

Supported signals in the MVP:

- JS/TS: `package.json` scripts and npm/pnpm/yarn lockfiles
- Python: `pyproject.toml`, pytest config, ruff config, uv/poetry lockfiles
- Rust: `Cargo.toml`
- Go: `go.mod`
- Makefile targets: `install`, `test`, `lint`, `build`, `doctor`, `agents`

## Optional Skill Workflow

The repository includes two optional Codex companion skills:

- `skills/agents-md-generate`: runs the deterministic CLI loop and reports
  whether it converged.
- `skills/agents-md-review`: reviews an agent instruction file using
  `doctor --json --explain` as hard evidence, then comments on usefulness and
  minimality.

The skills are not a second generator. The safe path is:

```text
agents-md-generate -> tiny-agents-md loop -> agents-md-review
```

## Development

```bash
python -m unittest discover -v
python -m compileall tiny_agents_md tests
python -m tiny_agents_md doctor . --explain
```
