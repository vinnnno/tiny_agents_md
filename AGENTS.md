# AGENTS.md

## Project Commands
- Install: `python -m pip install -e .`
- Test: `python -m unittest discover -v`
- Lint: `python -m compileall tiny_agents_md tests`
- Doctor: `python -m tiny_agents_md doctor . --explain`
- Check Agents: `python -m tiny_agents_md loop .`

## Project Structure
- `tiny_agents_md/`
- `tests/`
- `skills/`

## Agent Rules
- Prefer small, safe diffs.
- Run the test command before finishing when code changes.
- Do not invent commands or file paths.
