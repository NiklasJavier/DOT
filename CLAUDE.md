# Agent rules

<!-- AGENT-SURFACE-SSOT:BEGIN -->
## Agent Surface (global skills SSOT)

**Portable skills and plugins are centralized for all providers — not per-app copies.**

| | |
|--|--|
| **SSOT** | `~/Dev/30_projects/31_own/ai-harness` (`git@github.com:ErynoaGroup/.ai-harness.git`) |
| **Override root** | `$AGENT_SURFACE_ROOT` / `$AI_HARNESS_ROOT` |
| **Edit skills/plugins** | Only inside the SSOT (`skills/`, `plugins/`, `hooks/`, `justfile`) |
| **Never** | Treat home skill directories as the source of truth (derived symlinks) |
| **Install / health** | `cd <SSOT> && just install && just doctor` |
| **Docs / index** | `just index` → `docs/SKILLS.md` |
| **Handbook** | Skill **`agent-surface`** (`/agent-surface`) |
| **Repo doctrine** | Skill **`erynoa-md`** · file **`erynoa.md`** |
| **Large multi-skill work** | **`ultracode`** · **`advanced-prompt`** |

| Provider | Also reads in this repo |
|----------|-------------------------|
| All | **`erynoa.md` (canonical)** |
| Claude | `CLAUDE.md`, `.claude/` |
| Grok | `AGENTS.md`, `CLAUDE.md` |
| OpenAI Codex | `AGENTS.md` (and nested `AGENTS.md`) |
| GitHub Copilot | `AGENTS.md` + `.github/copilot-instructions.md` |

Project-local skill overlays under `.claude/skills/` or `.grok/skills/` are **L4** (this project only).

New global skill: edit SSOT → `just index` → `just install` → `just doctor` → commit in SSOT.
<!-- AGENT-SURFACE-SSOT:END -->

<!-- ERYNOA-POINTER:BEGIN -->
## Erynoa project doctrine (canonical)

**Full agent handbook for this repository:** [`erynoa.md`](./erynoa.md)

Every coding agent **MUST** find or create `erynoa.md` when interacting with this repo, then follow it.
Load skill **`erynoa-md`** (`/erynoa-md`) to create, deepen, audit, or sync mirrors.
<!-- ERYNOA-POINTER:END -->


## Project-specific rules

