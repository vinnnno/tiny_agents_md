# tiny-agents-md

A no-LLM `AGENTS.md` doctor and generator that refuses to invent commands or
paths.

```bash
$ tiny-agents-md doctor . --explain

AGENTS.md Health Report

File: AGENTS.md
Score: 100/100
Rating: excellent

Issues: none

Valid Commands:
- `python -m unittest discover -v` from Makefile:test
- `python -m compileall tiny_agents_md tests` from Makefile:lint

Valid Paths:
- `tiny_agents_md/` (source)
- `tests/` (tests)
```

Generate a minimal file when you need one:

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

## Install

Requires Python 3.11+.

From GitHub:

```bash
pipx install git+https://github.com/vinnnno/tiny_agents_md.git
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
tiny-agents-md init . --dry-run
tiny-agents-md init . --write
```

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
