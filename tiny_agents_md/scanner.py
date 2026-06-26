from __future__ import annotations

from pathlib import Path

from .commands import extract_commands
from .models import PathFacts, RepoFacts

SOURCE_DIRS = ("src", "lib", "app")
TEST_DIRS = ("tests", "test", "__tests__")
DOC_DIRS = ("docs", "doc")
CONFIG_DIRS = ("config", ".github", "scripts", "skills")
GENERATED_DIRS = ("dist", "build", "out", "coverage", "generated")

IGNORED_WALK_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "out",
    "coverage",
    "target",
}

LANGUAGE_EXTENSIONS = {
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".py": "Python",
    ".rs": "Rust",
    ".go": "Go",
}


def scan_repo(root: str | Path) -> RepoFacts:
    root_path = Path(root).resolve()
    commands, warnings = extract_commands(root_path)

    return RepoFacts(
        root=root_path,
        languages=_detect_languages(root_path),
        commands=commands,
        paths=_detect_paths(root_path),
        warnings=warnings,
    )


def _detect_paths(root: Path) -> PathFacts:
    return PathFacts(
        source=_detect_source_dirs(root),
        tests=_existing_dirs(root, TEST_DIRS),
        docs=_existing_dirs(root, DOC_DIRS),
        config=_existing_dirs(root, CONFIG_DIRS),
        generated=_existing_dirs(root, GENERATED_DIRS),
    )


def _detect_source_dirs(root: Path) -> tuple[str, ...]:
    source_dirs = list(_existing_dirs(root, SOURCE_DIRS))
    seen = set(source_dirs)

    try:
        entries = sorted(root.iterdir(), key=lambda path: path.name)
    except OSError:
        return tuple(source_dirs)

    excluded = set(TEST_DIRS + DOC_DIRS + CONFIG_DIRS + GENERATED_DIRS)
    excluded.update(IGNORED_WALK_DIRS)

    for entry in entries:
        if not entry.is_dir():
            continue
        if entry.name.startswith(".") or entry.name in excluded:
            continue
        if not (entry / "__init__.py").is_file():
            continue

        rel = f"{entry.name}/"
        if rel not in seen:
            source_dirs.append(rel)
            seen.add(rel)

    return tuple(source_dirs)


def _existing_dirs(root: Path, names: tuple[str, ...]) -> tuple[str, ...]:
    existing: list[str] = []
    for name in names:
        if (root / name).is_dir():
            existing.append(f"{name}/")
    return tuple(existing)


def _detect_languages(root: Path) -> tuple[str, ...]:
    counts: dict[str, int] = {}

    if (root / "package.json").exists():
        counts["JavaScript"] = counts.get("JavaScript", 0) + 1
    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        counts["Python"] = counts.get("Python", 0) + 1
    if (root / "Cargo.toml").exists():
        counts["Rust"] = counts.get("Rust", 0) + 1
    if (root / "go.mod").exists():
        counts["Go"] = counts.get("Go", 0) + 1

    for path in _iter_files(root):
        language = LANGUAGE_EXTENSIONS.get(path.suffix.lower())
        if language:
            counts[language] = counts.get(language, 0) + 1

    return tuple(
        language
        for language, _count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )
    )


def _iter_files(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue

        for entry in entries:
            if entry.is_dir():
                if entry.name not in IGNORED_WALK_DIRS:
                    stack.append(entry)
            elif entry.is_file():
                yield entry
