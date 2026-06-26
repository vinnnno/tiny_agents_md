from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tiny_agents_md.cli import main
from tiny_agents_md.doctor import run_doctor
from tiny_agents_md.generator import render_agents_md
from tiny_agents_md.scanner import scan_repo


class GenerationTests(unittest.TestCase):
    def test_typescript_pnpm_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(
                root / "package.json",
                {
                    "scripts": {
                        "test": "vitest run",
                        "lint": "eslint .",
                        "build": "tsc",
                    }
                },
            )
            (root / "pnpm-lock.yaml").write_text("", encoding="utf-8")
            _mkdirs(root, "src", "tests", "dist")

            facts = scan_repo(root)
            md = render_agents_md(facts)

            self.assertIn("- Install: `pnpm install`", md)
            self.assertIn("- Test: `pnpm test`", md)
            self.assertIn("- Lint: `pnpm lint`", md)
            self.assertIn("- Build: `pnpm build`", md)
            self.assertIn("- `src/`", md)
            self.assertIn("- `tests/`", md)
            self.assertIn("- `dist/` generated, do not edit", md)
            self.assertIn("- Do not modify generated files.", md)

            test_command = facts.command_for("test")
            self.assertIsNotNone(test_command)
            self.assertEqual(test_command.source, "package.json:scripts.test")

    def test_package_manager_conflict_skips_js_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "package.json", {"scripts": {"test": "vitest"}})
            (root / "pnpm-lock.yaml").write_text("", encoding="utf-8")
            (root / "package-lock.json").write_text("{}", encoding="utf-8")

            facts = scan_repo(root)
            md = render_agents_md(facts)

            self.assertEqual(facts.commands, ())
            self.assertIn("package manager conflict", "\n".join(facts.warnings))
            self.assertNotIn("pnpm test", md)
            self.assertNotIn("npm test", md)

    def test_package_json_with_utf8_bom_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '\ufeff{"scripts":{"test":"vitest"}}',
                encoding="utf-8",
            )

            facts = scan_repo(root)
            md = render_agents_md(facts)

            self.assertIn("- Test: `npm test`", md)
            self.assertEqual(facts.warnings, ())

    def test_python_uv_pytest_and_ruff_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                """
[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
""".strip(),
                encoding="utf-8",
            )
            (root / "uv.lock").write_text("", encoding="utf-8")
            _mkdirs(root, "src", "tests")

            facts = scan_repo(root)
            md = render_agents_md(facts)

            self.assertIn("- Test: `uv run pytest`", md)
            self.assertIn("- Lint: `uv run ruff check .`", md)
            self.assertNotIn("- Build:", md)
            self.assertIn("- Run the test command before finishing", md)

    def test_pyproject_with_utf8_bom_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                "\ufeff[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n",
                encoding="utf-8",
            )

            facts = scan_repo(root)
            md = render_agents_md(facts)

            self.assertIn("- Test: `pytest`", md)
            self.assertEqual(facts.warnings, ())

    def test_python_package_directory_is_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_dir = root / "demo_pkg"
            package_dir.mkdir()
            (package_dir / "__init__.py").write_text("", encoding="utf-8")
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "__init__.py").write_text("", encoding="utf-8")

            facts = scan_repo(root)
            md = render_agents_md(facts)

            self.assertIn("- `demo_pkg/`", md)
            self.assertIn("- `tests/`", md)
            self.assertIn("demo_pkg/", facts.paths.source)
            self.assertNotIn("tests/", facts.paths.source)

    def test_makefile_targets_fill_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text(
                """
install:
\tpython -m pip install -e .
test:
\tpython -m unittest
lint:
\tpython -m py_compile tiny_agents_md/*.py
build:
\tpython -m build
doctor:
\tpython -m tiny_agents_md doctor .
agents:
\tpython -m tiny_agents_md loop .
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_repo(root)
            md = render_agents_md(facts)

            self.assertIn("- Install: `python -m pip install -e .`", md)
            self.assertIn("- Test: `python -m unittest`", md)
            self.assertIn("- Lint: `python -m py_compile tiny_agents_md/*.py`", md)
            self.assertIn("- Build: `python -m build`", md)
            self.assertIn("- Doctor: `python -m tiny_agents_md doctor .`", md)
            self.assertIn("- Check Agents: `python -m tiny_agents_md loop .`", md)

    def test_multi_line_makefile_target_uses_make_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text(
                """
test:
\tpython -m compileall demo
\tpython -m unittest
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_repo(root)
            md = render_agents_md(facts)

            self.assertIn("- Test: `make test`", md)

    def test_rust_manifest_generates_test_and_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Cargo.toml").write_text(
                """
[package]
name = "demo"
version = "0.1.0"
edition = "2021"
""".strip(),
                encoding="utf-8",
            )

            facts = scan_repo(root)
            md = render_agents_md(facts)

            self.assertIn("- Test: `cargo test`", md)
            self.assertIn("- Build: `cargo build`", md)

    def test_go_mod_generates_test_and_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "go.mod").write_text(
                """
module example.com/demo

go 1.22
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_repo(root)
            md = render_agents_md(facts)

            self.assertIn("- Test: `go test ./...`", md)
            self.assertIn("- Build: `go build ./...`", md)

    def test_explicit_package_script_wins_over_makefile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "package.json", {"scripts": {"test": "vitest"}})
            (root / "Makefile").write_text(
                "test:\n\tpython -m unittest\n",
                encoding="utf-8",
            )

            facts = scan_repo(root)
            md = render_agents_md(facts)

            self.assertIn("- Test: `npm test`", md)
            self.assertNotIn("- Test: `make test`", md)

    def test_cli_dry_run_prints_diff_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "package.json", {"scripts": {"test": "vitest"}})
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main(["init", str(root), "--dry-run"])

            self.assertEqual(exit_code, 0)
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertIn("+- Test: `npm test`", stdout.getvalue())
            self.assertEqual(stderr.getvalue(), "")

    def test_cli_init_writes_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "package.json", {"scripts": {"build": "tsc"}})
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(["init", str(root)])

            self.assertEqual(exit_code, 0)
            self.assertTrue((root / "AGENTS.md").exists())
            self.assertIn("- Build: `npm run build`", (root / "AGENTS.md").read_text())

    def test_cli_loop_writes_and_converges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text("test:\n\tpython -m unittest\n", encoding="utf-8")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(["loop", str(root)])

            self.assertEqual(exit_code, 0)
            self.assertTrue((root / "AGENTS.md").exists())
            output = stdout.getvalue()
            self.assertIn("doctor score 100/100", output)
            self.assertIn("Loop converged.", output)

    def test_cli_loop_rejects_bad_min_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                exit_code = main(["loop", str(root), "--min-score", "101"])

            self.assertEqual(exit_code, 2)
            self.assertIn("--min-score must be between 0 and 100", stderr.getvalue())


class DoctorTests(unittest.TestCase):
    def test_doctor_accepts_generated_agents_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text("test:\n\tpython -m unittest\n", encoding="utf-8")
            _mkdirs(root, "tests")
            facts = scan_repo(root)
            (root / "AGENTS.md").write_text(render_agents_md(facts), encoding="utf-8")

            report = run_doctor(root)

            self.assertEqual(report.score, 100)
            self.assertEqual(report.rating, "excellent")
            self.assertEqual(report.issues, ())

    def test_doctor_accepts_alternate_instruction_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text("test:\n\tpython -m unittest\n", encoding="utf-8")
            _mkdirs(root, "tests")
            facts = scan_repo(root)
            (root / "CLAUDE.md").write_text(render_agents_md(facts), encoding="utf-8")
            stdout = io.StringIO()

            report = run_doctor(root, "CLAUDE.md")
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["doctor", str(root), "--file", "CLAUDE.md"])

            self.assertEqual(report.file, "CLAUDE.md")
            self.assertEqual(report.score, 100)
            self.assertEqual(exit_code, 0)
            self.assertIn("File: CLAUDE.md", stdout.getvalue())

    def test_doctor_reports_invalid_commands_paths_and_boilerplate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "package.json", {"scripts": {"test": "vitest"}})
            (root / "pnpm-lock.yaml").write_text("", encoding="utf-8")
            (root / "AGENTS.md").write_text(
                """
# AGENTS.md

## Project Commands
- Build: `npm run build`

## Project Structure
- `docs/`

## Agent Rules
- Follow best practices.
""".lstrip(),
                encoding="utf-8",
            )

            report = run_doctor(root)
            codes = {issue.code for issue in report.issues}

            self.assertIn("invalid_command", codes)
            self.assertIn("missing_path", codes)
            self.assertIn("missing_detected_test_command", codes)
            self.assertIn("generic_boilerplate", codes)
            self.assertLess(report.score, 75)

    def test_doctor_ignores_readme_code_block_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text("test:\n\tpython -m unittest\n", encoding="utf-8")
            facts = scan_repo(root)
            agents = render_agents_md(facts)
            (root / "AGENTS.md").write_text(agents, encoding="utf-8")
            (root / "README.md").write_text(
                f"# Example\n\n```md\n{agents}\n```\n",
                encoding="utf-8",
            )

            report = run_doctor(root)
            codes = {issue.code for issue in report.issues}

            self.assertNotIn("readme_duplicate", codes)
            self.assertEqual(report.score, 100)

    def test_doctor_reports_package_manager_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "package.json", {"scripts": {"test": "vitest"}})
            (root / "pnpm-lock.yaml").write_text("", encoding="utf-8")
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            (root / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")

            report = run_doctor(root)
            codes = {issue.code for issue in report.issues}

            self.assertIn("package_manager_conflict", codes)

    def test_doctor_accepts_fenced_bash_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "package.json", {"scripts": {"test": "vitest"}})
            (root / "AGENTS.md").write_text(
                """
# AGENTS.md

## Commands

```bash
npm test  # test
```

## Project Structure
- `src/`
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src").mkdir()

            report = run_doctor(root)
            codes = {issue.code for issue in report.issues}

            self.assertNotIn("missing_detected_test_command", codes)
            self.assertNotIn("missing_path", codes)

    def test_doctor_accepts_npm_run_test_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "package.json", {"scripts": {"test": "vitest"}})
            (root / "AGENTS.md").write_text(
                """
# AGENTS.md

## Commands

```bash
npm run test  # test
```
""".lstrip(),
                encoding="utf-8",
            )

            report = run_doctor(root)
            codes = {issue.code for issue in report.issues}

            self.assertNotIn("invalid_command", codes)
            self.assertNotIn("missing_detected_test_command", codes)

    def test_doctor_accepts_declared_makefile_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text(
                "release:\n\tpython -m build\n",
                encoding="utf-8",
            )
            (root / "AGENTS.md").write_text(
                """
# AGENTS.md

## Commands

```bash
make release
```
""".lstrip(),
                encoding="utf-8",
            )

            report = run_doctor(root)
            codes = {issue.code for issue in report.issues}

            self.assertNotIn("invalid_command", codes)

    def test_doctor_accepts_standard_cargo_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Cargo.toml").write_text(
                "[package]\nname = \"demo\"\nversion = \"0.1.0\"\nedition = \"2021\"\n",
                encoding="utf-8",
            )
            (root / "AGENTS.md").write_text(
                """
# AGENTS.md

## Commands

```bash
cargo build
cargo test
cargo run
cargo check
```
""".lstrip(),
                encoding="utf-8",
            )

            report = run_doctor(root)
            codes = {issue.code for issue in report.issues}

            self.assertNotIn("invalid_command", codes)

    def test_doctor_cli_min_score_controls_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text(
                """
# AGENTS.md

## Agent Rules
- This is a project.
""".lstrip(),
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                passing = main(["doctor", str(root), "--min-score", "95"])
            with contextlib.redirect_stdout(io.StringIO()):
                failing = main(["doctor", str(root), "--min-score", "96"])

            self.assertEqual(passing, 0)
            self.assertEqual(failing, 1)

    def test_doctor_cli_rejects_bad_min_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                exit_code = main(["doctor", str(root), "--min-score", "101"])

            self.assertEqual(exit_code, 2)
            self.assertIn("--min-score must be between 0 and 100", stderr.getvalue())

    def test_doctor_json_explain_includes_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text("test:\n\tpython -m unittest\n", encoding="utf-8")
            _mkdirs(root, "tests")
            facts = scan_repo(root)
            (root / "AGENTS.md").write_text(render_agents_md(facts), encoding="utf-8")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(["doctor", str(root), "--json", "--explain"])

            self.assertEqual(exit_code, 0)
            data = json.loads(stdout.getvalue())
            self.assertEqual(data["file"], "AGENTS.md")
            self.assertIn(
                {
                    "command": "python -m unittest",
                    "sources": ["Makefile:test"],
                },
                data["validCommands"],
            )
            self.assertIn(
                {
                    "path": "tests/",
                    "kind": "tests",
                    "exists": True,
                },
                data["validPaths"],
            )

    def test_doctor_cli_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(["doctor", str(root), "--json"])

            self.assertEqual(exit_code, 1)
            data = json.loads(stdout.getvalue())
            self.assertEqual(data["file"], "AGENTS.md")
            self.assertEqual(data["score"], 0)
            self.assertEqual(data["issues"][0]["code"], "missing_agents_md")


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _mkdirs(root: Path, *names: str) -> None:
    for name in names:
        (root / name).mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    unittest.main()
