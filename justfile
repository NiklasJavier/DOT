# SOT — command surface (Erynoa DX: Nix + just)
# Enter:  nix develop
# One-shot: nix develop -c just <recipe>
# List:   just --list

set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# document shell entry
shell:
    @echo "run: nix develop   # just, bash, shellcheck, yamllint, git"

# layout + critical paths
doctor:
    #!/usr/bin/env bash
    set -euo pipefail
    test -f flake.nix
    test -f justfile -o -f Justfile
    test -f erynoa.md
    test -f bin/sot
    test -d commands
    test -d lib
    test -d tests
    test -f tests/run-all.sh
    test -d docs/work
    echo "ok: SOT layout + erynoa + nix/just"

# full test suite
test:
    bash tests/run-all.sh

# lint (tools from nix develop)
lint:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v shellcheck >/dev/null 2>&1; then
      shellcheck -x bin/sot commands/*.sh lib/core/*.sh lib/cli/*.sh 2>/dev/null || shellcheck bin/sot commands/*.sh || true
      echo "shellcheck: done (see warnings above if any)"
    else
      echo "warn: shellcheck not on PATH — use nix develop"
      exit 1
    fi
    if command -v yamllint >/dev/null 2>&1; then
      yamllint -c .yamllint config modules 2>/dev/null || yamllint -c .yamllint . || true
      echo "yamllint: done"
    else
      echo "warn: yamllint not on PATH — use nix develop"
      exit 1
    fi

# pre-commit if installed
check:
    #!/usr/bin/env bash
    set -euo pipefail
    just doctor
    if command -v pre-commit >/dev/null 2>&1; then
      pre-commit run --all-files
    else
      just lint
      just test
    fi

# tooling note (no global brew SSOT)
install:
    @echo "Contributor tools: nix develop (flake.nix)"
    @echo "Host bootstrap (ops): see README curl installer — separate from dev DX"
