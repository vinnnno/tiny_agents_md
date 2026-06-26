---
name: agents-md-generate
description: Generate, refresh, or converge a minimal verifiable AGENTS.md using the tiny-agents-md deterministic CLI. Use when asked to create AGENTS.md, update generated agent instructions, run an AGENTS.md generation loop, compare generated output, or keep AGENTS.md in sync without relying on an LLM-generated document.
---

# AGENTS.md Generate

Use this skill to orchestrate the deterministic `tiny-agents-md` CLI. Do not manually compose `AGENTS.md` from scratch.

## Workflow

1. Locate the repository root.
2. Prefer the convergence loop:

   ```bash
   tiny-agents-md loop .
   ```

   If the console script is unavailable inside the `tiny-agents-md` repo, use:

   ```bash
   python -m tiny_agents_md loop .
   ```

3. If the user only wants a preview, run:

   ```bash
   tiny-agents-md init . --dry-run
   ```

4. If `loop` is unavailable in an older checkout, fall back to:

   ```bash
   tiny-agents-md init . --write
   tiny-agents-md doctor .
   tiny-agents-md init . --dry-run
   ```

5. Report whether the loop converged, the doctor score, and whether `AGENTS.md` changed.

## Guardrails

- Never invent commands, paths, or project summaries for `AGENTS.md`.
- Do not hand-write a replacement file unless the user explicitly asks for a manual edit.
- Convert useful review feedback into generator or doctor rules when possible, then rerun the loop.
- Keep the no-LLM path intact: generation must work through local file scanning and deterministic rendering.
