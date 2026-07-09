# Agent rules

<!-- AGENT-SURFACE-SSOT:BEGIN -->
# GitHub Copilot — repository instructions

You are working in a repository that uses the **Erynoa Agent Surface SSOT** for portable skills and plugins shared across **Claude Code**, **Grok Build**, **OpenAI Codex**, and **GitHub Copilot**.

## Mandatory

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

- Root `AGENTS.md` (same contract; used by Codex, Grok, Copilot agents)
- Root `CLAUDE.md` (Claude-compatible mirror)

## When adding a capability used by multiple agents

1. Implement the skill under the SSOT `skills/<name>/`
2. `just index && just install && just doctor` in the SSOT
3. Commit in the SSOT repo — not only in this application repository
<!-- AGENT-SURFACE-SSOT:END -->

## Project-specific rules

