from __future__ import annotations

from .models import CommandKind, PathFacts, RepoFacts

COMMAND_LABELS: dict[CommandKind, str] = {
    "install": "Install",
    "test": "Test",
    "lint": "Lint",
    "build": "Build",
    "doctor": "Doctor",
    "agents": "Check Agents",
}

COMMAND_ORDER: tuple[CommandKind, ...] = (
    "install",
    "test",
    "lint",
    "build",
    "doctor",
    "agents",
)


def render_agents_md(facts: RepoFacts) -> str:
    lines: list[str] = ["# AGENTS.md", "", "## Project Commands"]

    for kind in COMMAND_ORDER:
        command = facts.command_for(kind)
        if command is not None:
            lines.append(f"- {COMMAND_LABELS[kind]}: `{command.command}`")

    lines.extend(["", "## Project Structure"])
    lines.extend(_render_paths(facts.paths))

    lines.extend(["", "## Agent Rules"])
    lines.extend(_render_rules(facts))

    return "\n".join(lines).rstrip() + "\n"


def _render_paths(paths: PathFacts) -> list[str]:
    lines: list[str] = []

    for path in paths.source:
        lines.append(f"- `{path}`")
    for path in paths.tests:
        lines.append(f"- `{path}`")
    for path in paths.docs:
        lines.append(f"- `{path}`")
    for path in paths.config:
        lines.append(f"- `{path}`")
    for path in paths.generated:
        lines.append(f"- `{path}` generated, do not edit")

    return lines


def _render_rules(facts: RepoFacts) -> list[str]:
    rules: list[str] = []

    if facts.paths.generated:
        rules.append("- Do not modify generated files.")

    rules.append("- Prefer small, safe diffs.")

    if facts.command_for("test") is not None:
        rules.append("- Run the test command before finishing when code changes.")

    rules.append("- Do not invent commands or file paths.")

    return rules
