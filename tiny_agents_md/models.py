from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

CommandKind = Literal["install", "test", "lint", "build", "doctor", "agents"]


@dataclass(frozen=True)
class CommandFact:
    kind: CommandKind
    command: str
    source: str


@dataclass(frozen=True)
class PathFacts:
    source: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    docs: tuple[str, ...] = ()
    config: tuple[str, ...] = ()
    generated: tuple[str, ...] = ()


@dataclass(frozen=True)
class RepoFacts:
    root: Path
    languages: tuple[str, ...] = ()
    commands: tuple[CommandFact, ...] = ()
    paths: PathFacts = field(default_factory=PathFacts)
    warnings: tuple[str, ...] = ()

    def command_for(self, kind: CommandKind) -> CommandFact | None:
        for command in self.commands:
            if command.kind == kind:
                return command
        return None
