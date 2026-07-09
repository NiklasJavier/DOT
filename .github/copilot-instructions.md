# Agent rules

<!-- AGENT-SURFACE-SSOT:BEGIN -->
# GitHub Copilot — repository instructions

You are working in a repository that uses the **Erynoa Agent Surface SSOT** for portable skills and plugins shared across **Claude Code**, **Grok Build**, **OpenAI Codex**, and **GitHub Copilot**.

## Mandatory — project doctrine

- **Read and follow** root **`erynoa.md`** (canonical agent handbook for this repo).
- If `erynoa.md` is missing, create it using skill **`erynoa-md`** (or `just stamp-init` from the Agent Surface SSOT).
- Do **not** invent a second full doctrine only in this file — keep this file thin; depth lives in `erynoa.md`.

## Mandatory — global skills

- **Do not** create a second global skill/plugin catalogue inside this app repo.
- Global skills/plugins live only in:
  - `~/Dev/30_projects/31_own/ai-harness`  
  - remote: `git@github.com:ErynoaGroup/.ai-harness.git`
- Edit skills/plugins **only** in that SSOT; then operators run `just install` + `just doctor`.
- For changes to the surface itself, follow skill **`agent-surface`**.
- For large multi-skill work, prefer **`ultracode`**; sharpen intent with **`advanced-prompt`**.
- Home paths such as `~/.claude/skills`, `~/.grok/skills`, `~/.agents/skills` are **derived** (symlinks), not sources of truth.
- Optional project-local overlays under `.claude/skills` / `.grok/skills` apply only to this repository (L4).

## Also read

- Root **`erynoa.md`** (full doctrine)
- Root `AGENTS.md` / `CLAUDE.md` (adapters + surface block)

## When adding a capability used by multiple agents

1. Implement the skill under the SSOT `skills/<name>/`
2. `just index && just install && just doctor` in the SSOT
3. Commit in the SSOT repo — not only in this application repository
<!-- AGENT-SURFACE-SSOT:END -->

<!-- ERYNOA-POINTER:BEGIN -->
## Erynoa project doctrine (canonical)

**Full agent handbook for this repository:** [`erynoa.md`](./erynoa.md)

Every coding agent **MUST** find or create `erynoa.md` when interacting with this repo, then follow it.
Load skill **`erynoa-md`** (`/erynoa-md`) to create, deepen, audit, or sync mirrors.
<!-- ERYNOA-POINTER:END -->


## Project-specific rules

