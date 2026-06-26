from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import RepoFacts
from .scanner import scan_repo

MAX_LINES = 150

GENERIC_PHRASES = (
    "this is a project",
    "follow best practices",
    "write clean code",
    "maintainable code",
    "modern application",
    "robust and scalable",
    "ensure quality",
)

COMMAND_PREFIXES = (
    "npm ",
    "pnpm ",
    "yarn ",
    "make ",
    "python ",
    "python3 ",
    "pytest",
    "ruff ",
    "uv ",
    "poetry ",
    "cargo ",
    "go ",
)


@dataclass(frozen=True)
class DoctorIssue:
    code: str
    severity: str
    message: str
    deduction: int
    suggestion: str | None = None


@dataclass(frozen=True)
class DoctorCommandEvidence:
    command: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class DoctorPathEvidence:
    path: str
    kind: str
    exists: bool = True


@dataclass(frozen=True)
class DoctorReport:
    file: str
    score: int
    rating: str
    issues: tuple[DoctorIssue, ...]
    valid_commands: tuple[DoctorCommandEvidence, ...] = ()
    valid_paths: tuple[DoctorPathEvidence, ...] = ()

    def to_dict(self, include_explain: bool = False) -> dict:
        data = {
            "file": self.file,
            "score": self.score,
            "rating": self.rating,
            "issues": [asdict(issue) for issue in self.issues],
        }
        if include_explain:
            data["validCommands"] = [
                asdict(command) for command in self.valid_commands
            ]
            data["validPaths"] = [asdict(path) for path in self.valid_paths]
        return data


def run_doctor(root: str | Path, file_path: str | Path = "AGENTS.md") -> DoctorReport:
    root_path = Path(root).resolve()
    facts = scan_repo(root_path)
    target_path = _resolve_target_path(root_path, file_path)
    display_file = _display_path(root_path, target_path)
    valid_commands = _command_evidence(root_path, facts)
    valid_paths = _path_evidence(facts)

    if not _is_inside(root_path, target_path):
        return DoctorReport(
            file=display_file,
            score=0,
            rating="misleading",
            issues=(
                DoctorIssue(
                    code="file_outside_repo",
                    severity="critical",
                    message=f"{display_file} is outside the repository root",
                    deduction=100,
                    suggestion="choose an instruction file inside the repository",
                ),
            ),
            valid_commands=valid_commands,
            valid_paths=valid_paths,
        )

    if not target_path.exists():
        return DoctorReport(
            file=display_file,
            score=0,
            rating="misleading",
            issues=(
                DoctorIssue(
                    code="missing_agents_md",
                    severity="critical",
                    message=f"{display_file} is missing",
                    deduction=100,
                    suggestion="run `tiny-agents-md init . --write`",
                ),
            ),
            valid_commands=valid_commands,
            valid_paths=valid_paths,
        )

    try:
        content = target_path.read_text(encoding="utf-8")
    except OSError as exc:
        return DoctorReport(
            file=display_file,
            score=0,
            rating="misleading",
            issues=(
                DoctorIssue(
                    code="unreadable_agents_md",
                    severity="critical",
                    message=f"{display_file} could not be read: {exc}",
                    deduction=100,
                ),
            ),
            valid_commands=valid_commands,
            valid_paths=valid_paths,
        )

    issues = _collect_issues(root_path, facts, content)
    score = max(0, 100 - sum(issue.deduction for issue in issues))
    return DoctorReport(
        file=display_file,
        score=score,
        rating=_rating(score),
        issues=tuple(issues),
        valid_commands=valid_commands,
        valid_paths=valid_paths,
    )


def _resolve_target_path(root: Path, file_path: str | Path) -> Path:
    target = Path(file_path)
    if not target.is_absolute():
        target = root / target
    return target.resolve()


def _display_path(root: Path, target: Path) -> str:
    try:
        return target.relative_to(root).as_posix()
    except ValueError:
        return target.as_posix()


def _is_inside(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


def _collect_issues(root: Path, facts: RepoFacts, content: str) -> list[DoctorIssue]:
    issues: list[DoctorIssue] = []
    commands = _extract_backtick_commands(content)
    paths = _extract_backtick_paths(content)

    _add_scan_warning_issues(facts, issues)
    _add_invalid_command_issues(root, facts, commands, issues)
    _add_missing_test_issue(root, facts, commands, issues)
    _add_missing_path_issues(root, paths, issues)
    _add_generated_boundary_issue(facts, content, issues)
    _add_format_issues(content, issues)
    _add_noise_issues(root, content, issues)

    return issues


def _add_scan_warning_issues(facts: RepoFacts, issues: list[DoctorIssue]) -> None:
    for warning in facts.warnings:
        if "package manager conflict" in warning:
            issues.append(
                DoctorIssue(
                    code="package_manager_conflict",
                    severity="critical",
                    message=warning,
                    deduction=15,
                    suggestion="remove stale lockfiles or choose one package manager",
                )
            )


def _add_invalid_command_issues(
    root: Path,
    facts: RepoFacts,
    commands: set[str],
    issues: list[DoctorIssue],
) -> None:
    expected = _valid_repository_commands(root, facts)
    for command in sorted(commands):
        if command not in expected:
            issues.append(
                DoctorIssue(
                    code="invalid_command",
                    severity="critical",
                    message=f"`{command}` is not a detected repository command",
                    deduction=20,
                    suggestion="remove the command or replace it with a detected command",
                )
            )


def _valid_repository_commands(root: Path, facts: RepoFacts) -> set[str]:
    return {command.command for command in _command_evidence(root, facts)}


def _command_evidence(root: Path, facts: RepoFacts) -> tuple[DoctorCommandEvidence, ...]:
    evidence: dict[str, set[str]] = {}

    def add(command: str, source: str) -> None:
        evidence.setdefault(command, set()).add(source)

    for command in facts.commands:
        add(command.command, command.source)

    for command, source in _valid_package_json_command_sources(root, facts).items():
        add(command, source)
    for command, source in _valid_makefile_command_sources(root).items():
        add(command, source)
    for command, source in _valid_rust_command_sources(root).items():
        add(command, source)
    for command, source in _valid_go_command_sources(root).items():
        add(command, source)

    return tuple(
        DoctorCommandEvidence(command=command, sources=tuple(sorted(sources)))
        for command, sources in sorted(evidence.items())
    )


def _path_evidence(facts: RepoFacts) -> tuple[DoctorPathEvidence, ...]:
    evidence: list[DoctorPathEvidence] = []
    for kind in ("source", "tests", "docs", "config", "generated"):
        paths = getattr(facts.paths, kind)
        for path in paths:
            evidence.append(DoctorPathEvidence(path=path, kind=kind))
    return tuple(sorted(evidence, key=lambda item: (item.kind, item.path)))


def _valid_package_json_commands(root: Path, facts: RepoFacts) -> set[str]:
    return set(_valid_package_json_command_sources(root, facts))


def _valid_package_json_command_sources(root: Path, facts: RepoFacts) -> dict[str, str]:
    package_json = root / "package.json"
    if not package_json.exists() or _has_package_manager_conflict(facts):
        return {}

    try:
        data = json.loads(package_json.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}

    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return {}

    package_manager = _js_package_manager(root, data)
    if package_manager is None:
        return {}

    commands: dict[str, str] = {}
    for script in scripts:
        source = f"package.json:scripts.{script}"
        if package_manager == "npm":
            commands[f"npm run {script}"] = source
            if script in {"test", "start"}:
                commands[f"npm {script}"] = source
        else:
            commands[f"{package_manager} {script}"] = source
    return commands


def _has_package_manager_conflict(facts: RepoFacts) -> bool:
    return any("package manager conflict" in warning for warning in facts.warnings)


def _js_package_manager(root: Path, package_json: dict) -> str | None:
    declared = _declared_package_manager(package_json)
    present = [
        name
        for name, filename in (
            ("pnpm", "pnpm-lock.yaml"),
            ("yarn", "yarn.lock"),
            ("npm", "package-lock.json"),
        )
        if (root / filename).exists()
    ]
    if len(present) > 1:
        return None
    if declared and present and declared != present[0]:
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


def _valid_makefile_commands(root: Path) -> set[str]:
    return set(_valid_makefile_command_sources(root))


def _valid_makefile_command_sources(root: Path) -> dict[str, str]:
    makefile = root / "Makefile"
    if not makefile.exists():
        return {}

    try:
        content = makefile.read_text(encoding="utf-8")
    except OSError:
        return {}

    commands: dict[str, str] = {}
    target_re = re.compile(r"^([A-Za-z_][\w.-]*)\s*:", re.MULTILINE)
    for match in target_re.finditer(content):
        target = match.group(1)
        if target.startswith(".") or target.startswith("_"):
            continue
        commands[f"make {target}"] = f"Makefile:{target}"
    return commands


def _valid_rust_commands(root: Path) -> set[str]:
    return set(_valid_rust_command_sources(root))


def _valid_rust_command_sources(root: Path) -> dict[str, str]:
    if not (root / "Cargo.toml").exists():
        return {}
    return {
        "cargo build": "Cargo.toml",
        "cargo test": "Cargo.toml",
        "cargo run": "Cargo.toml",
        "cargo check": "Cargo.toml",
    }


def _valid_go_commands(root: Path) -> set[str]:
    return set(_valid_go_command_sources(root))


def _valid_go_command_sources(root: Path) -> dict[str, str]:
    if not (root / "go.mod").exists():
        return {}
    return {
        "go test ./...": "go.mod",
        "go build ./...": "go.mod",
    }


def _add_missing_test_issue(
    root: Path,
    facts: RepoFacts,
    commands: set[str],
    issues: list[DoctorIssue],
) -> None:
    test_command = facts.command_for("test")
    if test_command is None:
        return
    if test_command.command in commands or commands & _test_command_aliases(root, facts):
        return

    issues.append(
        DoctorIssue(
            code="missing_detected_test_command",
            severity="important",
            message=f"detected test command `{test_command.command}` is not listed",
            deduction=10,
            suggestion="add the detected test command to Project Commands",
        )
    )


def _test_command_aliases(root: Path, facts: RepoFacts) -> set[str]:
    aliases: set[str] = set()
    package_json = root / "package.json"
    if not package_json.exists() or _has_package_manager_conflict(facts):
        return aliases

    try:
        data = json.loads(package_json.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return aliases

    scripts = data.get("scripts")
    if not isinstance(scripts, dict) or "test" not in scripts:
        return aliases

    package_manager = _js_package_manager(root, data)
    if package_manager == "npm":
        aliases.update({"npm test", "npm run test"})
    elif package_manager in {"pnpm", "yarn"}:
        aliases.add(f"{package_manager} test")
    return aliases


def _add_missing_path_issues(
    root: Path,
    paths: set[str],
    issues: list[DoctorIssue],
) -> None:
    for path_text in sorted(paths):
        candidate = root / path_text.rstrip("/")
        if candidate.exists():
            continue
        issues.append(
            DoctorIssue(
                code="missing_path",
                severity="critical",
                message=f"`{path_text}` does not exist",
                deduction=15,
                suggestion="remove the path or regenerate AGENTS.md",
            )
        )


def _add_generated_boundary_issue(
    facts: RepoFacts,
    content: str,
    issues: list[DoctorIssue],
) -> None:
    if not facts.paths.generated:
        return

    lower = content.lower()
    has_generated_boundary = "generated" in lower and (
        "do not edit" in lower or "do not modify" in lower
    )
    if has_generated_boundary:
        return

    issues.append(
        DoctorIssue(
            code="missing_generated_boundary",
            severity="important",
            message="generated directories are present but not marked as do-not-edit",
            deduction=10,
            suggestion="add a rule such as `Do not modify generated files.`",
        )
    )


def _add_format_issues(content: str, issues: list[DoctorIssue]) -> None:
    line_count = len(content.splitlines())
    if line_count > MAX_LINES:
        issues.append(
            DoctorIssue(
                code="too_long",
                severity="minor",
                message=f"AGENTS.md has {line_count} lines; expected at most {MAX_LINES}",
                deduction=5,
                suggestion="remove low-signal prose and keep only actionable guidance",
            )
        )

    command_line_re = re.compile(
        r"^\s*-\s*(?:Install|Test|Lint|Build|Doctor|Check Agents)\s*:\s*(?!`)(.+)$",
        re.IGNORECASE,
    )
    for line in content.splitlines():
        match = command_line_re.match(line)
        if not match:
            continue
        if _looks_like_command(match.group(1).strip()):
            issues.append(
                DoctorIssue(
                    code="command_not_backticked",
                    severity="minor",
                    message=f"command should be wrapped in backticks: {line.strip()}",
                    deduction=5,
                    suggestion="wrap commands in backticks",
                )
            )


def _add_noise_issues(root: Path, content: str, issues: list[DoctorIssue]) -> None:
    lower = content.lower()
    for phrase in GENERIC_PHRASES:
        if phrase in lower:
            issues.append(
                DoctorIssue(
                    code="generic_boilerplate",
                    severity="minor",
                    message=f'generic boilerplate phrase found: "{phrase}"',
                    deduction=5,
                    suggestion="replace generic prose with concrete commands, paths, or rules",
                )
            )

    readme = root / "README.md"
    if not readme.exists():
        return

    try:
        readme_content = readme.read_text(encoding="utf-8")
    except OSError:
        return

    agents_lines = _normalized_content_lines(content)
    readme_lines = _normalized_content_lines(readme_content)
    duplicates = sorted((agents_lines & readme_lines))[:5]
    for duplicate in duplicates:
        issues.append(
            DoctorIssue(
                code="readme_duplicate",
                severity="minor",
                message=f"line appears duplicated from README: {duplicate}",
                deduction=5,
                suggestion="keep README-oriented prose out of AGENTS.md",
            )
        )


def _extract_backtick_commands(content: str) -> set[str]:
    commands: set[str] = set()
    for value in _extract_fenced_commands(content):
        if _looks_like_command(value):
            commands.add(value)
    for value in _extract_inline_backticks(content):
        if _looks_like_command(value):
            commands.add(value)
    return commands


def _extract_backtick_paths(content: str) -> set[str]:
    paths: set[str] = set()
    for value in _extract_inline_backticks(content):
        if _looks_like_command(value):
            continue
        if value.endswith("/") or "/" in value or "\\" in value:
            paths.add(value.replace("\\", "/"))
    return paths


def _extract_inline_backticks(content: str) -> list[str]:
    without_fences = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    return [match.strip() for match in re.findall(r"`([^`\n]+)`", without_fences)]


def _extract_fenced_commands(content: str) -> list[str]:
    commands: list[str] = []
    fence_re = re.compile(r"```(?:bash|sh|shell)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
    for block in fence_re.findall(content):
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            command = line.split("#", 1)[0].strip()
            if command:
                commands.append(command)
    return commands


def _looks_like_command(value: str) -> bool:
    value = value.strip()
    return any(value == prefix.strip() or value.startswith(prefix) for prefix in COMMAND_PREFIXES)


def _normalized_content_lines(content: str) -> set[str]:
    content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    lines: set[str] = set()
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("```"):
            continue
        line = re.sub(r"\s+", " ", line).strip("-* >").strip().lower()
        if len(line) >= 30:
            lines.add(line)
    return lines


def _rating(score: int) -> str:
    if score >= 90:
        return "excellent"
    if score >= 75:
        return "good"
    if score >= 50:
        return "needs work"
    return "misleading"
