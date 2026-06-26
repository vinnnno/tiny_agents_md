# tiny-agents-md

A no-LLM `AGENTS.md` generator and doctor that refuses to invent commands or
paths.

Status: early MVP. Supports JS/TS, Python, Rust, Go, and Makefile-based command
signals.

## Why

`AGENTS.md` should help coding agents do the right thing quickly:

- run real commands
- inspect real paths
- avoid generated files
- avoid stale or generic project prose

`tiny-agents-md` keeps the file small by default and checks that generated or
hand-written guidance stays factual.

## Usage

```bash
python -m tiny_agents_md init . --dry-run
python -m tiny_agents_md init . --write
python -m tiny_agents_md doctor .
python -m tiny_agents_md loop .
```

After installation, the console script is also available:

```bash
tiny-agents-md init . --dry-run
tiny-agents-md init . --write
tiny-agents-md doctor .
tiny-agents-md loop .
```

The first version uses static repository facts only. It does not call LLM APIs.

## No-LLM core

The CLI is deterministic and local-only:

- `init` scans repository files and renders `AGENTS.md`
- `doctor` checks an existing `AGENTS.md` for factual issues
- `loop` regenerates, checks, and stops when the file is stable

No command calls an LLM, embedding API, MCP server, or remote model. Commands,
paths, and package-manager choices come from files already present in the
repository.

`doctor` checks whether an existing `AGENTS.md` is factual and useful enough for
coding agents: commands must be traceable, paths must exist, package managers
must match, and generic boilerplate is flagged.

`loop` keeps the no-LLM workflow self-checking: regenerate `AGENTS.md`, run
`doctor`, and stop only when the file is stable and the score meets the
threshold.

The `skills/` directory contains optional Codex companion skills. They should
orchestrate `tiny-agents-md` commands rather than hand-writing generated
content.

## Optional skill workflow

The repository also includes two optional Codex skills:

- `skills/agents-md-generate`: runs the deterministic CLI loop and reports
  whether it converged.
- `skills/agents-md-review`: reviews an agent instruction file using
  `doctor --json` as hard evidence, then comments on usefulness and minimality.

The skills are not a second generator. They should not manually compose
`AGENTS.md` content unless a user explicitly asks for a manual edit. The safe
path is:

```text
agents-md-generate -> tiny-agents-md loop -> agents-md-review
```

Example output:

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

## Development

```bash
python -m unittest discover -v
python -m compileall tiny_agents_md tests
```
