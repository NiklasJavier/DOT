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
| **Large multi-skill work** | **`ultracode`** · **`advanced-prompt`** |

| Provider | Also reads in this repo |
|----------|-------------------------|
| Claude | `CLAUDE.md`, `.claude/` |
| Grok | `AGENTS.md`, `CLAUDE.md` |
| OpenAI Codex | `AGENTS.md` (and nested `AGENTS.md`) |
| GitHub Copilot | `AGENTS.md` + `.github/copilot-instructions.md` |

Project-local skill overlays under `.claude/skills/` or `.grok/skills/` are **L4** (this project only).

New global skill: edit SSOT → `just index` → `just install` → `just doctor` → commit in SSOT.
<!-- AGENT-SURFACE-SSOT:END -->

## Project-specific rules

