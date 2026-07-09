# erynoa.md — project agent doctrine

<!-- AGENT-PLANNER:BEGIN -->
## Agent planner (self-orchestration)

> **Read this first.** Humans: [README.md](./README.md).  
> **Regel №1 — DynHom:** homogen (homes/contracts) · dynamisch (signal-bound depth).  
> Skills: **`erynoa-md`** · **`erynoa-docs`** · Surface: **`agent-surface`**.

| | |
|--|--|
| **Mission** | Server Operation Toolkit — reproducible Linux server setup, CLI ops, vault, modular Ansible/Docker/SDKMAN |
| **Session goal** | `<from user — or: orient + just doctor>` |
| **Success** | `just doctor` green · `just test` green when code changes · no secrets committed |
| **DX** | `nix develop` · `just` · `just doctor` · `just test` · `just lint` |
| **Work-root** | `docs/work/` |
| **Default branch** | **`production`** (trunk for this repo; not `main`) |
| **Remote** | `git@github.com:NiklasJavier/SOT.git` |

**Read order:** (1) this planner (2) `justfile` (3) [README](./README.md) (4) sections below as needed (5) `docs/README.md` · active `docs/work/*`

**Do first**

1. Confirm root + branch (`production` vs topic)  
2. `nix develop` (or note if tools already on PATH)  
3. `just doctor`  
4. Classify task → orchestration row  
5. Execute · verify against **Success**

**Orchestration**

| Task | Route |
|------|--------|
| Orient | M0 · planner + doctor |
| Doctrine/docs form | `erynoa-md` / `erynoa-docs` |
| CLI / bash / modules | implement under `bin/` `commands/` `lib/` `modules/` |
| Quality / standards | `erynoa-md` M3 · `just lint` · `just test` |
| Multi-step feature | SPEC/PLAN in `docs/work/` · trunk-based short branch · PR → `production` |
| Ship gate | M5 · CI workflows green |
| Fuzzy intent | `advanced-prompt` then row above |
| Wide explore | **subagents** read-only (e.g. lib ‖ modules ‖ tests) → parent merge |

**Subagents:** solo default; fan-out if ≥2 independent tracks; full child brief; distilled returns; ≤4; no parallel writers same files.

**Efficiency:** ORIENT→PLAN→ACT→OBSERVE→VERIFY→COMPACT · progressive disclosure · tools > guessing.

**Voice:** *Craft Edge* — sharp, path-backed, short; 🎯📋🧩✓; ⚑ defaults; no slop.

**DynHom:** same Erynoa form as other repos; activate SE/packs by signal only.

**Do not:** skip planner · invent status/homes · brew as team SSOT · secrets in git · force-push `production` · push/PR without user ask · dump doctrine into README/chat
<!-- AGENT-PLANNER:END -->

---

## Identity

| Field | Value |
|-------|--------|
| **Project** | SOT — Server Operation Toolkit |
| **One-line purpose** | Reproducible Linux server setup & ops CLI (bootstrap, vault, ansible runner, modules) |
| **Owners** | Niklas (NiklasJavier) |
| **Legal / license** | MIT · public GitHub |
| **Status / tier** | production-ready · active |
| **Domains** | tooling, infra, ops |
| **Primary stack** | Bash 5+ · YAML config · Ansible modules · Docker templates · optional Terraform integrations |
| **Default branch** | `production` |
| **last_reviewed** | 2026-07-09 |
| **Doctrine skill** | `erynoa-md` |

## North star & non-goals

**North star:** One consistent CLI (`SOT` / `bin/sot`) for server operations with modular extensions and safe vault handling.

**Non-goals:**

- Not a general-purpose configuration management product replacing Ansible itself  
- Not a multi-cloud control plane  
- Not agent doctrine in README (lives here)

## Invariants

1. **I-1** — Public entry for operators remains the `SOT` CLI / `bin/sot` resolution path.  
2. **I-2** — No secrets, vault passwords, or raw `.env` values in git (`.env` gitignored).  
3. **I-3** — Automated checks: unit/integration via `tests/run-all.sh`; lint via shellcheck/yamllint (pre-commit + CI).  
4. **I-4** — Team DX: **Nix** (`flake.nix`) + **just** (`justfile`) — not brew/apt as SSOT.  
5. **I-5** — Agent entry: this file (Planner first); workstreams under `docs/work/`.  
6. **I-6** — Default integration line is **`production`** (repo convention; document if changing).

## Forbidden

1. **F-1** — Commit secrets, tokens, private keys, vault ciphertext meant to stay private, raw PII dumps  
2. **F-2** — Treat `~/.claude/skills` / `~/.grok/skills` as skill SSOT (Agent Surface only)  
3. **F-3** — Force-push or unprotected rewrite of `production` without explicit user OK  
4. **F-4** — Invent parallel top-level doc homes outside Erynoa types (`docs/work` for SPEC/PLAN)

## Definition of Done

- [ ] User goal met or explicitly deferred  
- [ ] `just doctor` green  
- [ ] `just test` green when bash/lib/commands/modules touched (or ⚑ justified skip)  
- [ ] No Forbidden violations  
- [ ] Durable conventions written back here  

## How agents work

1. **Planner first** → self-orchestrate (DynHom · Craft Edge · efficiency spine)  
2. Prefer evidence from tree; ⚑ assumptions  
3. Short-lived branches; PR into **`production`** unless user says otherwise  
4. Docs-as-code when operator contract (CLI flags, config keys) changes  
5. M4: update planner/commands when recipes change  

## Architecture map (SE-04 C4-ish)

```text
Operator → bin/sot → commands/* → lib/* → modules/{ansible,docker,sdkman}
                              ↘ config/*.yml
                              ↘ bootstrap/ (curl install path)
CI: .github/workflows/{test,lint,security,deploy}.yml
```

| Module / path | Responsibility | May depend on |
|---------------|----------------|---------------|
| `bin/sot` | CLI entry | `commands/`, `lib/` |
| `commands/` | User-facing verbs (bootstrap, vault, runner, doctor, …) | `lib/` |
| `lib/` | Shared bash (cli, core, plugins, extensions) | — |
| `modules/ansible` | Ansible playbooks/roles/inventory | config, vault |
| `modules/docker` | Compose/Dockerfile templates | — |
| `modules/sdkman` | SDKMAN module install hooks | — |
| `config/` | Default YAML + overrides | — |
| `bootstrap/` | Remote one-liner init | — |
| `tests/` | unit + integration | tree under test |

## Domain language (SE-05)

| Term | Meaning |
|------|---------|
| **SOT** | Server Operation Toolkit (this product) |
| **CLI verb** | Top-level command under `commands/` resolved by `bin/sot` |
| **Module** | Optional capability pack under `modules/` |
| **Vault** | Ansible-vault oriented secret editing flow (`commands/vault.sh`) |
| **Bootstrap** | Host/server initial setup path |
| **production** | Default long-lived branch / release line for this repo |

## Tooling & commands (SE-17)

```bash
nix develop              # flake: just, git, bash, shellcheck, yamllint
just                     # list recipes
just doctor              # layout + critical paths
just test                # tests/run-all.sh
just lint                # shellcheck + yamllint (best-effort)
just fmt-check           # optional shfmt if present
```

One-shot:

```bash
nix develop -c just doctor
nix develop -c just test
```

Legacy human path (still valid for end servers): curl bootstrap — see README.  
**Contributor/agent path:** Nix + just.

## Environments

| Env | Notes |
|-----|--------|
| local dev | `nix develop` · tests · pre-commit |
| target host | bootstrap / ansible over SSH (ops) |
| CI | GitHub Actions: test, lint, security |

## Test strategy (SE-10)

- **Unit:** `tests/unit/`  
- **Integration:** `tests/integration/`  
- **Runner:** `tests/run-all.sh` → `just test`  
- Critical: CLI resolution, config parse, vault helpers — keep green before merge  

## Git & review (SE-08/09)

- **Default branch:** `production` (not `main`)  
- **Model:** short-lived topic branches · PR → `production`  
- **Commits:** Conventional Commits preferred  
- **Spec-bound names** when using `docs/work/`: `using-spec-driven-git`  
- Also present remotes: `dev`, `staging` — treat as deploy lines, not GitFlow religion  

## Specs & plans (SE-07)

| | |
|--|--|
| Map | [docs/README.md](./docs/README.md) |
| Work-root | `docs/work/` |
| ROADMAP | `docs/work/ROADMAP.md` |
| ADRs | `docs/decisions/` |
| SE catalogue | skill `erynoa-docs` → `se-patterns.md` |

## Skills & surface

| | |
|--|--|
| This doctrine | `./erynoa.md` · `erynoa-md` |
| Docs / README style | `erynoa-docs` |
| Global skills | `~/Dev/30_projects/31_own/ai-harness` · `agent-surface` |
| Preferred here | `erynoa-md`, `erynoa-docs`, `advanced-prompt`, `check-work`, `using-spec-driven-git` |

Install health: `cd <SSOT> && just install && just doctor`

## Provider adapters

Thin pointers in `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md` → **this file**.

## Trust & secrets (SE-12)

- Vault materials: never commit plaintext secrets  
- `.env` gitignored  
- CI security workflow present — do not weaken casually  

## Open questions

- [ ] Align public README contributor section from brew/apt toward Nix+just (docs-as-code, optional PR)  
- [ ] Whether to rename default branch to `main` long-term (document only — do not rename without user)

## Decision log

| Date | Decision | Consequence |
|------|----------|-------------|
| 2026-07-09 | Full Erynoa init (Planner, DynHom, Craft Edge, Nix+just, docs/work) | Agents bootstrap from this file |
| 2026-07-09 | Keep default branch name `production` | Branching docs differ from generic `main` default |
