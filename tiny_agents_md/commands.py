from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from .models import CommandFact, CommandKind

COMMAND_ORDER: tuple[CommandKind, ...] = (
    "install",
    "test",
    "lint",
    "build",
    "doctor",
    "agents",
)


def extract_commands(root: Path) -> tuple[tuple[CommandFact, ...], tuple[str, ...]]:
    """Extract commands that can be traced to repository files."""
    commands: dict[CommandKind, CommandFact] = {}
    warnings: list[str] = []

    for command in _extract_js_commands(root, warnings):
        _add_command(commands, command, warnings)

    for command in _extract_python_commands(root, warnings):
        _add_command(commands, command, warnings)

    for command in _extract_rust_commands(root):
        _add_command(commands, command, warnings)

    for command in _extract_go_commands(root):
        _add_command(commands, command, warnings)

    for command in _extract_makefile_commands(root):
        _add_command(commands, command, warnings)

    ordered = tuple(commands[kind] for kind in COMMAND_ORDER if kind in commands)
    return ordered, tuple(warnings)


def _add_command(
    commands: dict[CommandKind, CommandFact],
    command: CommandFact,
    warnings: list[str],
) -> None:
    if command.kind in commands:
        existing = commands[command.kind]
        warnings.append(
            f"skipped {command.source} for {command.kind}; "
            f"already using {existing.source}"
        )
        return
    commands[command.kind] = command


def _extract_js_commands(root: Path, warnings: list[str]) -> list[CommandFact]:
    package_json = root / "package.json"
    if not package_json.exists():
        return []

    try:
        data = json.loads(package_json.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"could not read package.json: {exc}")
        return []

    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        scripts = {}

    package_manager = _detect_js_package_manager(root, data, warnings)
    if package_manager is None:
        warnings.append("skipped JS commands because package manager is ambiguous")
        return []

    commands = [
        CommandFact("install", _install_command(package_manager), "package.json"),
    ]

    if "test" in scripts:
        commands.append(
            CommandFact(
                "test",
                _script_command(package_manager, "test"),
                "package.json:scripts.test",
            )
        )

    lint_script = _first_existing_script(scripts, ("lint", "check", "typecheck"))
    if lint_script:
        commands.append(
            CommandFact(
                "lint",
                _script_command(package_manager, lint_script),
                f"package.json:scripts.{lint_script}",
            )
        )

    if "build" in scripts:
        commands.append(
            CommandFact(
                "build",
                _script_command(package_manager, "build"),
                "package.json:scripts.build",
            )
        )

    return commands


def _detect_js_package_manager(
    root: Path,
    package_json: dict,
    warnings: list[str],
) -> str | None:
    declared = _declared_package_manager(package_json)
    lockfiles = {
        "pnpm": root / "pnpm-lock.yaml",
        "yarn": root / "yarn.lock",
        "npm": root / "package-lock.json",
    }
    present = [name for name, path in lockfiles.items() if path.exists()]
    if len(present) > 1:
        warnings.append(
            "package manager conflict: "
            + ", ".join(lockfiles[name].name for name in present)
        )
        return None

    if declared and present and declared != present[0]:
        warnings.append(
            "package manager conflict: "
            f"packageManager declares {declared} but {lockfiles[present[0]].name} is present"
        )
        return None

    if declared:
        return declared

    if len(present) == 1:
        return present[0]

    return "npm"


def _declared_package_manager(package_json: dict) -> str | None:
    package_manager = package_json.get("packageManager")
    if isinstance(package_manager, str):
        name = package_manager.split("@", 1)[0]
        if name in {"npm", "pnpm", "yarn"}:
            return name
    return None


def _install_command(package_manager: str) -> str:
    if package_manager == "npm":
        return "npm install"
    if package_manager == "pnpm":
        return "pnpm install"
    return "yarn install"


def _script_command(package_manager: str, script: str) -> str:
    if package_manager == "npm":
        if script in {"test", "start"}:
            return f"npm {script}"
        return f"npm run {script}"
    return f"{package_manager} {script}"


def _first_existing_script(scripts: dict, candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in scripts:
            return candidate
    return None


def _extract_python_commands(root: Path, warnings: list[str]) -> list[CommandFact]:
    pyproject_path = root / "pyproject.toml"
    pyproject = _read_toml(pyproject_path, warnings) if pyproject_path.exists() else {}
    tool = pyproject.get("tool", {}) if isinstance(pyproject, dict) else {}
    tool = tool if isinstance(tool, dict) else {}

    prefix = _python_prefix(root)
    commands: list[CommandFact] = []

    pytest_source = _pytest_source(root, tool)
    if pytest_source:
        commands.append(CommandFact("test", f"{prefix}pytest", pytest_source))

    ruff_source = _ruff_source(root, tool)
    if ruff_source:
        commands.append(CommandFact("lint", f"{prefix}ruff check .", ruff_source))

    return commands


def _read_toml(path: Path, warnings: list[str]) -> dict:
    try:
        content = path.read_bytes()
        if content.startswith(b"\xef\xbb\xbf"):
            content = content[3:]
        return tomllib.loads(content.decode("utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        warnings.append(f"could not read {path.name}: {exc}")
        return {}


def _python_prefix(root: Path) -> str:
    if (root / "uv.lock").exists():
        return "uv run "
    if (root / "poetry.lock").exists():
        return "poetry run "
    return ""


def _pytest_source(root: Path, tool: dict) -> str | None:
    if (root / "pytest.ini").exists():
        return "pytest.ini"

    pytest_config = tool.get("pytest")
    if isinstance(pytest_config, dict) and "ini_options" in pytest_config:
        return "pyproject.toml:tool.pytest.ini_options"

    return None


def _ruff_source(root: Path, tool: dict) -> str | None:
    if (root / "ruff.toml").exists():
        return "ruff.toml"
    if (root / ".ruff.toml").exists():
        return ".ruff.toml"

    if isinstance(tool.get("ruff"), dict):
        return "pyproject.toml:tool.ruff"

    return None


def _extract_makefile_commands(root: Path) -> list[CommandFact]:
    makefile = root / "Makefile"
    if not makefile.exists():
        return []

    try:
        content = makefile.read_text(encoding="utf-8")
    except OSError:
        return []

    recipes = _makefile_recipes(content)
    target_by_kind: dict[CommandKind, str] = {
        "install": "install",
        "test": "test",
        "lint": "lint",
        "build": "build",
        "doctor": "doctor",
        "agents": "agents",
    }
    commands: list[CommandFact] = []
    for kind in COMMAND_ORDER:
        target = target_by_kind[kind]
        if target in recipes:
            command = _makefile_command_for_target(target, recipes[target])
            commands.append(CommandFact(kind, command, f"Makefile:{target}"))
    return commands


def _extract_rust_commands(root: Path) -> list[CommandFact]:
    cargo_toml = root / "Cargo.toml"
    if not cargo_toml.exists():
        return []

    return [
        CommandFact("test", "cargo test", "Cargo.toml"),
        CommandFact("build", "cargo build", "Cargo.toml"),
    ]


def _extract_go_commands(root: Path) -> list[CommandFact]:
    go_mod = root / "go.mod"
    if not go_mod.exists():
        return []

    return [
        CommandFact("test", "go test ./...", "go.mod"),
        CommandFact("build", "go build ./...", "go.mod"),
    ]


def _makefile_command_for_target(target: str, recipe: list[str]) -> str:
    if len(recipe) == 1:
        return recipe[0]
    return f"make {target}"


def _makefile_recipes(content: str) -> dict[str, list[str]]:
    recipes: dict[str, list[str]] = {}
    current_targets: list[str] = []
    target_re = re.compile(r"^([A-Za-z_][\w.-]*)\s*:", re.MULTILINE)
    for line in content.splitlines():
        if line.startswith("\t") and current_targets:
            command = line.strip()
            if command and not command.startswith("#"):
                for target in current_targets:
                    recipes[target].append(command)
            continue

        match = target_re.match(line)
        if not match:
            if line.strip():
                current_targets = []
            continue

        target = match.group(1)
        current_targets = []
        if target.startswith(".") or target.startswith("_"):
            continue
        recipes.setdefault(target, [])
        current_targets = [target]
    return recipes
