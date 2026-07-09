# Documentation map (SOT)

**Standard:** Erynoa Docs **v1** · skill **`erynoa-docs`** · **DynHom** (same homes, signal-bound depth).

| Path | Purpose | Type |
|------|---------|------|
| [../README.md](../README.md) | Product overview & operator quickstart | L0 human |
| [../erynoa.md](../erynoa.md) | **Agent planner + doctrine** | L0 agent |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Contribution rules | Collab |
| [architecture.md](./architecture.md) | System shape | L1 architecture |
| [bootstrap.md](./bootstrap.md) | Bootstrap how-to | L1 guide |
| [configuration.md](./configuration.md) | Config lookup | L1 reference |
| [cli-reference.md](./cli-reference.md) | CLI lookup | L1 reference |
| [development.md](./development.md) | Dev how-to | L1 guide |
| [style-guide.md](./style-guide.md) | Style conventions | L1 guide |
| [decisions/](./decisions/) | ADRs (SE-06) | L1 decisions |
| **[work/](./work/)** | Specs, plans, ROADMAP (SE-07) | **L2 work-root** |

**Work-root:** `docs/work/` only for new SPEC/PLAN.

## Branching

- Long-lived line: **`production`** (this repo)  
- Short topic branches · PR into `production`  
- Spec-bound: `feat/spec-NN/…` · light: `fix/…`  
- Policy: **`erynoa-docs`** · mechanics: **`using-spec-driven-git`**

## Contributor DX

```bash
nix develop
just doctor
just test
```

## New feature workstream

1. [`work/ROADMAP.md`](./work/ROADMAP.md)  
2. `work/specs/SPEC-NN-slug.md`  
3. `work/plans/PLAN-NN-slug.md`  
4. Branch → implement → docs-as-code → PR → `production`  
5. ROADMAP `done` · promote durable bits to L1 if needed  

Trivial fixes: no SPEC/PLAN. Agent rules: only `erynoa.md`.
