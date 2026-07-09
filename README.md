# SOT — Server Operation Toolkit

<div align="center">

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Shell](https://img.shields.io/badge/shell-bash%205.0+-121011.svg?logo=gnu-bash&logoColor=white)
![Ansible](https://img.shields.io/badge/automation-ansible-EE0000.svg?logo=ansible&logoColor=white)
![Docker](https://img.shields.io/badge/containers-docker-2496ED.svg?logo=docker&logoColor=white)

[![Tests](https://github.com/NiklasJavier/SOT/actions/workflows/test.yml/badge.svg)](https://github.com/NiklasJavier/SOT/actions/workflows/test.yml)
[![Security](https://github.com/NiklasJavier/SOT/actions/workflows/security.yml/badge.svg)](https://github.com/NiklasJavier/SOT/actions/workflows/security.yml)
[![Lint](https://github.com/NiklasJavier/SOT/actions/workflows/lint.yml/badge.svg)](https://github.com/NiklasJavier/SOT/actions/workflows/lint.yml)

**Reproduzierbares Setup- und Operations-Framework für Linux-Server**

[Schnellstart](#-schnellstart) •
[Features](#-features) •
[CLI-Nutzung](#-cli-nutzung) •
[Konfiguration](#-konfiguration) •
[Entwicklung](#-entwicklung)

</div>

---

---

## Agents & contributor DX

| | |
|--|--|
| **Agents** | Full doctrine + planner: [`erynoa.md`](./erynoa.md) |
| **Docs map** | [`docs/README.md`](./docs/README.md) |
| **Dev shell** | `nix develop` then `just doctor` · `just test` |

> End-user server install remains the curl bootstrap below. **Contributors/agents** use Nix + just.

## 📋 Übersicht

Das **Server Operation Toolkit (SOT)** bietet ein konsistentes CLI für Server-Operationen,
zentrales Logging, Vault-Management und modulare Ansible/Terraform-Integration.

```bash
# Installation (Einzeiler)
curl -fsSL "https://raw.githubusercontent.com/NiklasJavier/SOT/production/bootstrap/init.sh" | bash -s -- -branch production

# Nutzung
SOT help                          # Alle Befehle anzeigen
SOT bootstrap                     # Server konfigurieren
SOT vault                         # Secrets bearbeiten
SOT runner ansible <playbook>     # Playbook ausführen
```

---

## ✨ Features

| Feature | Beschreibung |
|---------|--------------|
| 🖥️ **Einheitliches CLI** | `SOT <befehl>` — automatische Skript-Auflösung, Parameter-Injektion, Logging |
| 🔧 **Modulares Setup** | Dynamische Defaults, Branch-Isolation, verschachteltes YAML-Config |
| 🎭 **Ansible-Integration** | Lokale Playbooks mit Priorität, AAT-Fallback, automatische Inventory-Erkennung |
| 🏗️ **Terraform-Integration** | TID-Sync, automatische Workspace-/Stack-Erkennung |
| 🔐 **Vault-Management** | Ansible-Vault Integration, sichere Secret-Generierung |
| 📚 **Shared Library** | Wiederverwendbare Bash-Funktionen (`lib/`) |
| ✅ **Test-Suite** | 69+ Unit- und Integrationstests |

---

## 🚀 Schnellstart

### Minimale Installation

```bash
curl -fsSL "https://raw.githubusercontent.com/NiklasJavier/SOT/production/bootstrap/init.sh" \
  | bash -s -- -branch production -port 22
```

### Vollständige Installation mit Integrationen

```bash
# Variablen (optional)
export SOTBRANCH="production"
export AATBRANCH="main"
export TIDBRANCH="main"

# Installation
curl -fsSL "https://raw.githubusercontent.com/NiklasJavier/SOT/${SOTBRANCH}/bootstrap/init.sh" \
  | bash -s -- -branch "$SOTBRANCH" -port 22 && \
  SOT aat sync --branch "$AATBRANCH" && \
  SOT tid sync --branch "$TIDBRANCH" && \
  SOT validate && \
  SOT bootstrap
```

### Was passiert?

1. **Clone** → Repository nach `/etc/DevOpsToolkit`
2. **Config** → `config.yaml` mit dynamischen Werten generiert
3. **Symlink** → CLI nach `/usr/sbin/SOT` verlinkt
4. **Sync** → AAT/TID Repositories synchronisiert
5. **Setup** → Host-Playbook ausgeführt

> 💡 Für Tests: `-branch dev` oder `-branch staging` verwenden

---

## 🏗️ Setup-Optionen

| Flag | Beispiel | Beschreibung |
|------|----------|--------------|
| `-branch` | `-branch dev` | Branch-spezifische Settings |
| `-config` | `-config /path/to/config.yml` | Alternative Config laden |
| `-systemname` | `-systemname srv-prod` | Systemname überschreiben |
| `-port` | `-port 22` | SSH-Port setzen |
| `-key` | `-key "ssh-ed25519 AAAA..."` | SSH Public Key speichern |
| `-tools` | `-tools "ansible docker"` | Tools installieren |
| `-aat_enabled` | `-aat_enabled true` | AAT aktivieren |
| `-tid_enabled` | `-tid_enabled true` | TID aktivieren |

---

## 📖 CLI-Nutzung

```bash
SOT [unterordner] <befehl> [optionen]
```

### Wichtigste Befehle

```
   ███████╗ ██████╗ ████████╗
   ██╔════╝██╔═══██╗╚══██╔══╝
   ███████╗██║   ██║   ██║   
   ╚════██║██║   ██║   ██║   
   ███████║╚██████╔╝   ██║   
   ╚══════╝ ╚═════╝    ╚═╝   
```

| Kategorie | Befehl | Beschreibung |
|-----------|--------|--------------|
| 🖥️ **System** | `SOT bootstrap` | Server-Konfiguration ausführen |
| 🔐 **Vault** | `SOT vault [view\|edit\|rekey]` | Vault interaktiv bearbeiten |
| 🔄 **Sync** | `SOT aat sync` | AAT-Repository synchronisieren |
| 🔄 **Sync** | `SOT tid sync` | TID-Repository synchronisieren |
| 🔄 **Sync** | `SOT integrations list` | Alle Integrationen anzeigen |
| 🔄 **Sync** | `SOT integrations add <name> <type>` | Neue Integration hinzufügen |
| 🔄 **Sync** | `SOT validate` | Alle Integrationen validieren |
| ▶️ **Run** | `SOT runner aat <playbook>` | Ansible-Playbook ausführen |
| ▶️ **Run** | `SOT runner tid <stack>` | Terraform-Stack ausführen |
| 🔧 **Wartung** | `SOT update` | SOT aktualisieren |
| 🔧 **Wartung** | `SOT delete` | SOT entfernen |
| ℹ️ **Info** | `SOT help [command]` | Hilfe anzeigen |
| ℹ️ **Info** | `SOT version` | Version anzeigen |
| ℹ️ **Info** | `SOT --interactive` | Interaktives Menü |

### Shell-Completion

```bash
# Bash
source <(SOT --completion bash)

# Zsh  
source <(SOT --completion zsh)

# Permanent (Bash)
SOT --completion bash > /etc/bash_completion.d/sot
```

### Detaillierte Befehlshilfe

```bash
# Hilfe für einen spezifischen Befehl
SOT help bootstrap
SOT help vault
SOT help runner
```

### Automatische Parameter

Jeder Befehl erhält automatisch:
- `--config_file` — Pfad zur config.yaml
- `--vault_file` / `--vault_secret` — Vault-Informationen
- `--modules_dir` / `--scripts_dir` — Verzeichnispfade
- `--log_file` — Log-Datei für Protokollierung

---

## ⚙️ Konfiguration

SOT unterstützt zwei YAML-Formate mit **automatischer Erkennung**:

### Format v1 — Flach (Legacy)

```yaml
# config/default_config.yml
system_name: "SRV-EXAMPLE"
ssh_port: "282"
aat_enabled: "true"
aat_dir: "/opt/AAT"
```

### Format v2 — Verschachtelt (Empfohlen)

```yaml
# config/default_config_v2.yml
system:
  name: "SRV-EXAMPLE"
  username: "__GENERATE_USERNAME__"

ssh:
  port: "282"

aat:
  enabled: "true"
  dir: "/opt/AAT"
  branch: "main"

runner:
  enabled: "true"
  default_mode: "aat"
  sync_before_run: "true"
```

> Der Smart-Loader konvertiert automatisch: `section.key` → `section_key`

### Wichtige Konfigurationsschlüssel

| Kategorie | Schlüssel | Beschreibung |
|-----------|-----------|--------------|
| **System** | `system_name`, `username` | Server-/Benutzerbezeichnungen |
| **SSH** | `ssh_port` | SSH-Port für Firewall & Playbooks |
| **Pfade** | `modules_dir`, `scripts_dir` | Verzeichnisse im Clone |
| **Ansible** | `ansible_local_enabled`, `ansible_local_priority` | Lokale Playbook-Steuerung |
| **AAT** | `aat_enabled`, `aat_dir`, `aat_branch` | AAT-Integration |
| **TID** | `tid_enabled`, `tid_dir`, `tid_branch` | TID-Integration |
| **Vault** | `vault_file`, `vault_secret` | Vault-Konfiguration |
| **Runner** | `runner_enabled`, `runner_default_mode` | Runner-Einstellungen |

---

## 🧩 Module & Integrationen

SOT verwendet ein **dynamisches Integrations-Framework**, das automatisch alle konfigurierten
Repositories erkennt und CLI-Befehle dafür generiert.

### Dynamische Integrationen

```bash
# Alle Integrationen anzeigen
SOT integrations list

# Neue Integration hinzufügen (generiert Config-Template)
SOT integrations add mytools ansible
SOT integrations add infra terraform
SOT integrations add scripts custom

# Integration synchronisieren
SOT <name> sync [--branch <branch>]

# Alle Integrationen validieren
SOT validate
```

**Unterstützte Typen:**
| Typ | Runner | Beschreibung |
|-----|--------|--------------|
| `ansible` | `ansible-playbook` | Ansible-Playbooks mit Inventory-Support |
| `terraform` | `terraform` | Terraform-Stacks mit Workspace-Isolation |
| `custom` | Konfigurierbarer Runner | Eigene Ausführungslogik |
| `script` | `bash` | Einfache Shell-Skripte |

### Lokale Ansible-Module

- `modules/ansible/` ist die erste Anlaufstelle für Playbooks, Inventare und Rollen
- Der Runner durchsucht dieses Verzeichnis vor jeder AAT-Integration
- Branch-/kundenbezogene Variablen über `config/overrides/` ablegbar

### AAT — Ansible Automation Tools

- `SOT aat sync` aktualisiert das externe Repository
- Fallback: Nur wenn kein lokales Playbook gefunden wird
- [AAT Playbook-Übersicht](https://github.com/NiklasJavier/AAT/blob/main/docs/README.md)

### TID — Terraform Infrastructure Deployment

- Terraform-Code lebt vollständig im TID-Repository
- `SOT runner terraform` führt Stacks aus (plan, apply, destroy)
- [TID Service-Übersicht](https://github.com/NiklasJavier/TID/blob/main/docs/README.md)

### Neue Integration hinzufügen

```bash
# 1. Config-Template generieren
SOT integrations add mytools ansible

# 2. Generierte Werte in config.yaml anpassen:
#    mytools_enabled: "true"
#    mytools_repo_url: "https://github.com/user/mytools.git"
#    mytools_dir: "/opt/MyTools"
#    mytools_branch: "main"
#    mytools_type: "ansible"

# 3. Repository synchronisieren
SOT mytools sync

# 4. Validieren
SOT validate
```

---

## 📁 Verzeichnisstruktur

```
SOT/
├── bin/                        # 🚀 CLI-Einstiegspunkt
│   └── sot                     # SOT CLI
│
├── lib/                        # 📚 Shared Library
│   ├── init.sh                 # Hauptlader
│   ├── core/                   # Kernfunktionen
│   │   ├── colors.sh           # Terminal-Farben
│   │   ├── yaml_parser.sh      # YAML-Parser (v1 & v2)
│   │   ├── helpers.sh          # Hilfsfunktionen
│   │   └── bootstrap/          # Bootstrap-Module
│   │       ├── args_parser.sh  # CLI-Argumente
│   │       ├── config_defaults.sh
│   │       ├── tasks.sh
│   │       ├── config_writer.sh
│   │       └── runner.sh
│   ├── cli/                    # CLI-System
│   │   ├── registry.sh         # Befehlsregistrierung
│   │   └── integrations.sh     # Integrations-Framework
│   └── plugins/                # Plugin-System
│       └── manager.sh          # Plugin-Manager
│
├── commands/                   # 📜 CLI-Befehle
│   ├── bootstrap.sh            # Host-Setup
│   ├── runner.sh               # Ansible/Terraform-Runner
│   ├── vault.sh                # Vault-Interaktion
│   ├── maintenance/            # Wartungs-Skripte
│   └── integrations/           # AAT/TID-Sync
│
├── completions/                # 🔤 Shell-Completions
│   ├── sot-completion.bash
│   └── sot-completion.zsh
│
├── modules/                    # 🔌 Plugin-Module
│   ├── ansible/                # Ansible (Playbooks, Rollen)
│   │   ├── module.yml          # Plugin-Metadaten
│   │   ├── install.sh
│   │   └── commands/
│   ├── docker/                 # Docker-Templates
│   └── sdkman/                 # SDKMAN!-Installer
│
├── bootstrap/                  # ⚙️ Bootstrap
│   ├── init.sh                 # Initial-Setup
│   ├── dependencies.sh         # Dependency-Manager
│   └── vault_template.j2       # Vault-Template
│
├── config/                     # 📋 Konfiguration
│   ├── default_config.yml      # Defaults (v1)
│   ├── default_config_v2.yml   # Defaults (v2)
│   └── overrides/              # Environment-Overrides
│
├── tests/                      # 🧪 Tests
│   ├── unit/                   # Unit-Tests
│   └── integration/            # Integrations-Tests
│
└── docs/                       # 📖 Dokumentation
```

---

## 🧪 Tests

```bash
# Alle Tests ausführen
./ci/run-all-tests.sh

# Einzelne Suites
./ci/run-helpers-tests.sh       # 34 Tests — Hilfsfunktionen
./ci/run-yaml-tests.sh          # 5 Tests  — YAML-Parser
./ci/run-bootstrap-tests.sh     # 15 Tests — Bootstrap-Library
./ci/run-integration-tests.sh   # 15 Tests — Integration
./ci/run-cli-tests.sh           # CLI Smoke-Tests
./ci/run-vault-tests.sh         # Vault-Workflow
```

**Test-Abdeckung:**
- ✅ `is_true()`, `is_false()` — Boolean-Parsing
- ✅ YAML-Parsing — Flach & Verschachtelt
- ✅ Config-Loading — Smart-Loader
- ✅ Bootstrap-Module — Argument-Parser, Defaults
- ✅ CLI-Integration — Help, Commands
- ✅ Library-Idempotenz — Mehrfaches Sourcing

---

## 💻 Entwicklung

### Shared Library verwenden

```bash
#!/usr/bin/env bash
source "/etc/DevOpsToolkit/lib/init.sh"

# Farben
echo -e "${GREEN}Erfolg${NC}"
echo -e "${RED}Fehler${NC}"

# Hilfsfunktionen
is_true "yes" && echo "Ja!"
info "Information"
success "Erledigt"
warn "Warnung"
err "Fehler"

# Verzeichnisse
ensure_dir "/path/to/dir"

# YAML-Parsing
declare -A config
load_config "config.yml" config
echo "${config[system_name]}"
```

### Neuen CLI-Befehl erstellen

1. Script unter `commands/` erstellen:
```bash
# commands/mycommand.sh
#!/usr/bin/env bash
source "$CLONE_DIR/lib/init.sh"
info "Mein Befehl läuft"
```

2. Ausführbar machen:
```bash
chmod +x commands/mycommand.sh
```

3. Verwenden:
```bash
SOT mycommand
```

### Tests hinzufügen

Siehe [tests/](tests/) für Anleitungen zum Erstellen neuer Tests.

### Pre-commit Hooks einrichten

```bash
# Installation
pip install pre-commit
pre-commit install

# Manuell alle Checks ausführen
pre-commit run --all-files
```

Enthaltene Hooks:
- **ShellCheck** — Statische Bash-Analyse
- **shfmt** — Shell-Formatierung
- **yamllint** — YAML-Validierung
- **ansible-lint** — Ansible Best Practices
- **gitleaks** — Secret-Detection
- **markdownlint** — Markdown-Formatierung

---

## 🔐 Sicherheit

- **Vault-Template** generiert sichere Zufalls-Secrets (60+ Zeichen)
- **Temporäre Passwortdateien** werden automatisch gelöscht
- **Ansible-Vault** verschlüsselt sensible Daten
- **Branch-Isolation** trennt Umgebungen

```bash
# Vault bearbeiten
SOT vault

# Secret rotieren (manuell in config.yaml)
vault_secret: "<neues-60-zeichen-secret>"
```

---

## 📚 Weitere Dokumentation

| Dokument | Beschreibung |
|----------|--------------|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Beitragsrichtlinien & Coding-Standards |
| [lib/README.md](lib/README.md) | Shared Library Dokumentation |
| [ci/README.md](ci/README.md) | Test-Suite Dokumentation |
| [modules/ansible/README.md](modules/ansible/README.md) | Ansible-Module |
| [.editorconfig](.editorconfig) | Editor-Formatierungsregeln |
| [.pre-commit-config.yaml](.pre-commit-config.yaml) | Pre-commit Hooks |

---

## 🏆 Best Practices

1. **Branch-Isolation** — `production`, `staging`, `dev` für parallele Profile
2. **Config-Overrides** — Environment-spezifische Werte in `config/overrides/`
3. **Lokale Playbooks** — Eigene Rollen unter `modules/ansible/roles/`
4. **Regelmäßiger Sync** — `runner_sync_before_run: "true"` aktivieren
5. **Secret-Rotation** — `vault_secret` regelmäßig erneuern
6. **Tests ausführen** — `./ci/run-all-tests.sh` vor Commits
7. **Pre-commit nutzen** — `pre-commit install` für automatische Checks
8. **EditorConfig** — Konsistente Formatierung in allen Editoren

---

## 📄 Lizenz

MIT License — siehe [LICENSE](LICENSE)

---

<div align="center">

**[⬆ Nach oben](#sot--server-operation-toolkit)**

</div>

<!-- ERYNOA-MODEL:BEGIN -->
## Model

> System sketch (**SE-04**). Depth: [`docs/README.md`](./docs/README.md) · agents: [`erynoa.md`](./erynoa.md).

```mermaid
flowchart LR
  Op[Operator] --> CLI[bin/sot]
  CLI --> Cmd[commands/]
  Cmd --> Lib[lib/]
  Cmd --> Mod[modules/]
  CLI --> Cfg[config/]
  Boot[bootstrap/] -.-> Op
```

| Part | Role |
|------|------|
| `bin/sot` | CLI entry |
| `commands/` · `lib/` | Verbs + shared bash |
| `modules/` | Ansible / Docker / SDKMAN packs |
| `config/` | Defaults + overrides |

<!-- ERYNOA-MODEL:END -->
