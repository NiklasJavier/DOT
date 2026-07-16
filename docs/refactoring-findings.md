# SOT Bash Toolkit — Consolidated Findings

_Synthesis of 10 subsystem-map agents + 5 cross-cutting audit agents. Deduplicated; every distinct file:line defect preserved. The repo is mid-refactor (`setup→bootstrap`, `integrations→extensions`, `flat v1 → nested v2 config`, `cli_wrapper.sh` removed); most defects are drift artifacts of these half-finished renames._

---

## 1. Subsystem Map

**1. CLI entry point / dispatch / registry / aliases / progress** — Turns `sot <cmd> [args]` into a resolved command script and executes it, appending framework metadata. `bin/sot` (set -euo pipefail) bootstraps `SOT_ROOT`, sources `lib/init.sh` + cli/plugins libs, parses config into flat vars, builds a 10-element positional `CLI_METADATA_ARGS`, hand-registers commands, then dispatches via alias-expansion → big `case` → `*`→`resolve_and_execute` (longest-prefix registry match, else filesystem `resolve_command_path`).
- `bin/sot` — entry: path bootstrap, config load, CLI_METADATA_ARGS, dispatch, execute_script (504 lines)
- `lib/cli/registry.sh` — registry data model + register_command; UNUSED auto-discovery; help/menu/completion generators (436)
- `lib/cli/aliases.sh` — CLI_ALIASES map + single-token expansion (192)
- `lib/cli/progress.sh` — progress bars, spinner, task-list widgets (434)
- `lib/init.sh` — idempotent library loader (35)

**2. Core reusable library (colors, helpers, YAML parser)** — Shared foundation: ANSI/semantic colors, colored stderr helpers (err/warn/info/success), generic utilities, and a pure-Bash YAML reader handling both flat v1 and nested v2 schemas. `lib/init.sh` sources colors→yaml→helpers (each self-guarded). YAML has three tiers (flat `parse_yaml_to_vars`, nested `parse_nested_yaml`, smart `load_config` that sniffs indentation and flattens); every line cleaned via `echo|cut|xargs|tr`.
- `lib/core/yaml_parser.sh` — flat + nested parsers, getters, smart load_config (362)
- `lib/core/helpers.sh` — is_true/ensure_dir/resolve_path/log_command + output helpers (192)
- `lib/core/colors.sh` — raw ANSI + deprecated aliases + COLOR_* semantic layer (33)
- `commands/runner.sh` — only production consumer of `load_config` (get_cfg wrapper)
- `lib/core/bootstrap/config_defaults.sh` — parallel/duplicate YAML reader bypassing yaml_parser.sh

**3. Extensions Manager & Plugin Manager** — Two parallel, unrelated registries for "pluggable" capability. Extensions manager (config-var-driven) git-clones external repos (AAT/TID) via indirect `${name}_${prop}` env vars; auto-sourced by init.sh everywhere. Plugin manager (filesystem-driven) discovers `modules/*/module.yml`, populates 10 `PLUGIN_*` assoc arrays via a bespoke parser, and dispatches installers/commands; sourced only by `bin/sot`. No shared code.
- `lib/plugins/manager.sh` — plugin registry, bespoke YAML parser, lifecycle, dispatch (584)
- `lib/extensions/manager.sh` — config-var-driven external-repo manager (235)
- `commands/extensions.sh` — CLI front-end for extensions manager (395)
- `modules/ansible/module.yml` — richest manifest; only 8 flat keys consumed (52)

**4. Config defaults / overrides / completions** — Default templates that seed installs, `__GENERATE_*__` placeholder resolution, and bash/zsh completions. Meant to be the single source of truth for settings, but split across two incompatible schemas (flat `default_config.yml` = production; nested `default_config_v2.yml` = tests/docs only), FOUR config readers, and THREE divergent completion definitions.
- `config/default_config.yml` — v1 FLAT production defaults (still carries dead integrations schema) (82)
- `config/default_config_v2.yml` — v2 NESTED template; referenced only by tests/docs (113)
- `completions/sot-completion.{bash,zsh}` — static completions, stale command set, never installed
- `lib/core/bootstrap/config_writer.sh` — writes runtime config in NESTED v2 format (132)

**5. Bootstrap library (`lib/core/bootstrap/*`)** — Library behind `bootstrap/init.sh`: turns CLI flags + default YAML into resolved config, writes per-branch `config.yaml`, runs ordered setup tasks with a progress UI. All inter-function communication is via mutable UPPERCASE global scalars. Flow: parse_early_args → load_default_config → apply_config_defaults → parse_setup_args → generate_dynamic_defaults → run_tasks.
- `lib/core/bootstrap/args_parser.sh` — parse_early_args + parse_setup_args flag switch (315)
- `lib/core/bootstrap/config_defaults.sh` — YAML loader + `__GENERATE_*__` resolution (203)
- `lib/core/bootstrap/config_writer.sh` — heredoc of globals into config.yaml (132)
- `lib/core/bootstrap/tasks.sh` — task_* (clone, dirs, CLI edit, symlink, deps) (289)
- `lib/core/bootstrap/runner.sh` — TASK_LABELS, critical-task list, run_task(s) (236)

**6. modules/ansible** — Self-contained Ansible tree + `trigger.sh` wrapper that `SOT bootstrap` invokes to configure the local host (packages/hostname/SSH/user/firewall + encrypted ansible-vault secrets). `host_setup.yml` runs roles variables→common→protection→vault; `load_config.yml` merges default+override into one `sot_config` fact and derives `__GENERATE_*__` values.
- `modules/ansible/commands/trigger.sh` — bash wrapper: resolves cfg/inventory, ensures ansible+docker, runs playbook (78)
- `modules/ansible/config/load_config.yml` — central config merge + generated-value derivation (94)
- `modules/ansible/roles/vault/tasks/main.yml` — creates/encrypts vault, temp-file shred cleanup (153)
- `modules/ansible/roles/common/tasks/main.yml` — apt/hostname/hosts/sshd/user/authorized_keys (53)
- `modules/ansible/roles/protection/tasks/main.yml` — UFW install/enable (22)

**7. User-facing command scripts (`commands/*`)** — Concrete verb implementations (bootstrap, runner, vault, doctor, extensions, maintenance). Each is standalone bash sourcing `lib/init.sh`. Three incompatible arg-handling contracts coexist: positional-metadata (bootstrap/vault/cleanup), explicit split (runner only — correct), and getopts+env (doctor/delete/update/extensions — swallow metadata, read empty env).
- `commands/runner.sh` — Ansible/Terraform engine; only correct user-vs-metadata arg split (890)
- `commands/doctor.sh` — health-check/repair (453)
- `commands/maintenance/delete.sh` — full uninstaller; reads unexported env → hardcoded defaults (397)
- `commands/maintenance/update.sh` — git fetch + reset --hard of core + extensions (266)
- `commands/vault.sh` — ansible-vault edit wrapper, RAM-tmpfs secret handling (190)

**8. Remote installer / bootstrap entrypoint / deps / vault templating** — The `curl|bash` (or local `sudo`) entrypoint: clones the repo, generates per-branch `config.yaml`, installs SDKMAN/Docker/Ansible, wires CLI symlinks, and supplies the Jinja2 vault template. `bootstrap/init.sh` detects bootstrap-mode via `BASH_SOURCE`, clones to `/opt/SOT`, re-execs locally; tasks re-clone to `/etc/DevOpsToolkit`. _(Heavy overlap with subsystem 5.)_
- `bootstrap/init.sh` — entrypoint: curl|bash detection, re-clone/re-exec, SETUP_TASKS (208)
- `bootstrap/dependencies.sh` — tool-installer dispatcher (sdkman/docker/ansible only) (122)
- `bootstrap/vault_template.j2` — Jinja2 vault template generating db/api secrets (55)
- `modules/ansible/roles/vault/tasks/main.yml` — consumes vault_content/secret/file, encrypts

**9. Documentation & Project Meta** — German Markdown docs (README + docs/*), CONTRIBUTING, four GitHub Actions workflows, pre-commit, editorconfig. Only `test.yml` tracks the post-refactor `tests/` layout; every prose doc, `security.yml`, and the completions still describe a repo that no longer exists.
- `README.md` — primary doc; heavily drifted (ci/, integrations, paths, dead links) (516)
- `docs/cli-reference.md` — documents removed command surface + wrong injected-param contract (248)
- `.github/workflows/test.yml` — the ONE meta file updated to tests/ layout — source of truth (106)
- `.github/workflows/security.yml` — ShellCheck targets nonexistent scripts//ci/ dirs (silent no-op) (179)

**10. Test suite (`tests/` + test.yml)** — Bash harness: master runner + 3 unit + 4 integration suites, hand-rolled assertions, no framework. `run-all.sh` runs a hardcoded 7-suite list in subprocesses; `setup-env.sh` builds runtime `ci/` scratch, a mock `ansible-vault`, and fixture config/vault files. CI runs unit → integration (after real `bootstrap/init.sh`) → full suite.
- `tests/run-all.sh` — master runner, hardcoded 7-suite list (74)
- `tests/setup-env.sh` — CI fixture: ci/ scratch, mock ansible-vault, exports env (100)
- `tests/unit/{helpers,yaml,setup}.sh` — unit suites (helpers/YAML/bootstrap-config)
- `tests/integration/{cli,config,integration,vault}.sh` — integration suites

---

## 2. Consolidated Problem Inventory

Severity in brackets. Merged entries cite all locations.

### A. Command dispatch & routing
- **[medium]** Two parallel resolution mechanisms + duplicated arms: `doctor/update/delete/plugins` have explicit `case` arms AND registry entries, while `bootstrap/vault/runner/extensions` rely solely on `*`→`resolve_and_execute` (registry longest-prefix vs filesystem `resolve_command_path`). Behavior depends on which branch a verb hits. `bin/sot:421-500`. → Route everything through one alias-expansion → `resolve_and_execute` table; keep only true meta-flags.
- **[low]** `integrations)` case arm is unreachable — alias expansion rewrites `integrations`→`extensions` before the case evaluates. `bin/sot:453-456`. → Delete.
- **[low]** Plugin commands registered with an empty script path, so they only run via the special-cased `plugin_exists` branch, never through `resolve_and_execute` — registry and dispatch are disconnected. `bin/sot`, `lib/plugins/manager.sh`. → Give plugin commands a real executor token.
- **[low]** `show_categorized_help` hardcodes the alias cheat-sheet (`sot s = sot setup`) as literal printf lines instead of deriving from `CLI_ALIASES`, so it drifts. `lib/cli/registry.sh:180-215`. → Generate from live data.

### B. Plugin / Extension / Integration / Module conceptual overlap
- **[high]** FOUR overlapping terms for two concepts, backed by THREE disjoint subsystems: `modules/` dirs discovered as "plugins" (`PLUGIN_*`); external git repos (aat/tid) managed as "extensions" via `<name>_enabled` env vars; "integration" still a first-class plugin TYPE + legacy `integrations` command + README wording. A plugin and an extension are the same concept but share no discovery, config format, lifecycle, or CLI path; even entrypoints differ (init.sh sources extensions, bin/sot sources plugins). `lib/plugins/manager.sh:26-40`, `lib/extensions/manager.sh:19-30`, `bin/sot:67,453`, `config/default_config.yml:29-59`. → Collapse to ONE concept with one registry; model a remote git repo as one provider strategy behind the same interface.
- **[high]** Two managers reimplement the same lifecycle (enabled-check, list, info-render, run-subcommand) against different backends (env-vars vs assoc-arrays); enable/disable exists a THIRD time in `commands/extensions.sh`. `lib/extensions/manager.sh:39-234`, `lib/plugins/manager.sh:218-499`, `commands/extensions.sh:318-340`. → Merge into one manager.
- **[high]** `module.yml` contract is incoherent: manifests declare rich nested structure (requirements.packages lists, templates list-of-maps, config maps, playbooks/roles, block scalars) but `parse_plugin_yaml` is a naive one-level parser that flattens to `${section}_${key}` and collapses lists. Only ~8 flat keys are consumed; `requirements/config/playbooks/roles/templates/sdks/notes` are declared and silently ignored; `dependencies:` (plugin deps) is conflated with `requirements.packages` (OS packages). `lib/plugins/manager.sh:50-103,154-167`, `modules/*/module.yml`. → Make manifest schema and parser agree (restrict to flat keys or parse with real YAML + versioned schema; validate at discovery).
- **[medium]** `PLUGIN_DEPENDENCIES` populated and displayed but never enforced — `install_plugin` runs the installer without resolving deps. `lib/plugins/manager.sh:166,493`.
- **[medium]** Two overlapping type taxonomies: extensions header says `ansible|terraform|script`, plugins use `tool|service|integration`; the plugin `integration` type IS the extensions concept. `lib/plugins/manager.sh:13,31`.
- **[low]** Extension record rendered three times (manager `extension_info` + `cmd_list` + `show_usage`), each re-querying/re-formatting. `lib/extensions/manager.sh:186-204`, `commands/extensions.sh:79-115,27-73`.

### C. Path & installation drift
- **[high]** Two contradictory install roots: bootstrap clones to `/opt/SOT` and re-execs there, but `task_clone_repository` clones AGAIN to `CLONE_DIR=/etc/DevOpsToolkit` and derives MODULES_DIR/CLI_FILE from it; `bin/sot` even has an `/opt/AAT` (foreign product) SOT_ROOT fallback. Double-clone, split-brain paths, plugin discovery can look under the wrong root. `bootstrap/init.sh:34`, `bin/sot:19,26-27`, `lib/core/bootstrap/config_defaults.sh:122`, `config/default_config.yml:13`. → One canonical root; derive all paths from `SOT_ROOT`; remove /opt/AAT fallback.
- **[high]** CLI-edit vs symlink target are different trees: `task_edit_cli` patches `$CLONE_DIR/bin/sot` (/etc/DevOpsToolkit) while `task_create_cli_symlink` points `/usr/sbin/SOT` + `/usr/local/lib/sot` + `/usr/local/bin/sot-bin` at `$SOT_ROOT/bin/sot` (/opt/SOT) — users invoke the un-patched copy. `lib/core/bootstrap/tasks.sh:139-150,172-186`. → Unify install root.
- **[high]** `SETUP_DIR="$CLONE_DIR/setup"` is a leftover from the setup→bootstrap rename (dir no longer exists). It feeds `VAULT_CONTENT="$SETUP_DIR/vault_template.j2"` (real path `bootstrap/vault_template.j2`) and `BRANCH_DIR`, so both resolve under a nonexistent `setup/`. config_writer persists the resolved-but-wrong path, so the Ansible fixup (which only rewrites empty/placeholder values) never fires and the vault role points at a missing template → vault creation fails (masked in CI, which hardcodes the correct path). `lib/core/bootstrap/config_defaults.sh:125,192`, `bootstrap/init.sh:162`, `modules/ansible/roles/vault/tasks/main.yml:60`, `tests/setup-env.sh:64`. → Rename SETUP_DIR→BOOTSTRAP_DIR, or emit the raw placeholder and let Ansible own derivation.
- **[medium]** `bin/sot` vault_file fallback points at `$DEFAULT_ROOT/templates/vault.j2`, but there is no `templates/` dir (file is `bootstrap/vault_template.j2`). `bin/sot:84`.
- **[low]** Symlink target drift: `/usr/sbin/SOT` (config, config_defaults, docs) vs `/usr/local/bin/SOT` (bin/sot:87 fallback) vs `/usr/local/bin/sot-bin` (tasks.sh:186). → Align to one.

### D. Config format drift (v1 flat vs v2 nested)
- **[high]** `config_writer` emits NESTED v2 runtime config, but `bin/sot:75` reads it with FLAT `parse_yaml_to_vars` and the ansible loader recursive-combines it against FLAT defaults. Flat-parsing nested YAML strips section prefixes: `ssh:\n  port:282` yields `$port` not `$ssh_port`, `$data_dir` not `$opt_data_dir`, and collides `aat/tid/runner enabled:`→`$enabled` and `branch:` (last wins, clobbering the real top-level branch). The user's chosen values never override flat defaults. `lib/core/bootstrap/config_writer.sh:14,87`, `bin/sot:75`, `modules/ansible/config/load_config.yml:27`. → Pick ONE on-disk format everywhere.
- **[high]** Schema drift v1↔v2: keys renamed (`ssh_key_function_enabled`→`ssh.key_enabled`, `opt_data_dir`→`paths.data_dir`, `systemlink_path`→`paths.systemlink`); field-sets differ (v1 aat `_type/_runner/_description`; v2 aat `inventory_path/inventory_vars`); different repo_url/dir. No authoritative schema. v2 is dead in production (only `tests/unit/yaml.sh` + docs reference it). `config/default_config_v2.yml`, `config/default_config.yml`.
- **[high]** AAT/TID acronyms expand differently per file: "Azure Automation Toolkit"/"Traefik Infrastructure Deployment" (v1 + bootstrap.md) vs "Ansible Automation Tools"/"Terraform Infrastructure Deployment" (v2 + README); v1 `tid_type: ansible` contradicts terraform treatment; v1 uses placeholder URLs (`yourorg/aat.git`) vs v2 real (`NiklasJavier/AAT.git`). `bin/sot` loads the stale v1 file by default. `config/default_config.yml:43-59`, `config/default_config_v2.yml:78-90`, `README.md:267-273`, `docs/bootstrap.md:164-165`.
- **[high]** Three-to-four independent YAML parsers: canonical `yaml_parser.sh` (5 fns), `parse_plugin_yaml` (manager.sh:50-103), `load_default_config` inline regex (config_defaults.sh:38-52), plus ansible `include_vars` — each re-implements comment/CR/quote strip + colon split with divergent behavior. `lib/core/yaml_parser.sh`, `lib/plugins/manager.sh:50-103`, `lib/core/bootstrap/config_defaults.sh:38-52`, `commands/doctor.sh:225-233`. → Route all reads through `yaml_parser.sh`.
- **[medium]** v1↔v2 flat-key mapping is not truly 1:1 despite the "backwards compatible" claim (`tools` vs `tools_install`, `ssh_key_function_enabled` vs `ssh.key_enabled`), so `load_config` yields different flat keys per schema. `lib/core/yaml_parser.sh`.
- **[medium]** Config-mutation done three incompatible ways: `_update_config_value` sudo-sed (extensions.sh:230-239), undefined `save_plugin_state` (manager.sh:296), and `config_writer.sh` (bootstrap only). None shared. → One get/set helper.
- **[medium]** Overrides mechanism documented but unimplemented on the shell side: `config/overrides/README.md` claims bootstrap auto-populates override files, but `tasks.sh:131` only `mkdir`s the empty dir and no shell code loads/merges overrides (only ansible merges a single `CONFIG_YAML`). `config/overrides/README.md`.
- **[medium]** `modules/ansible/config/load_config.yml` hard-wired to FLAT schema (`sot_config.clone_dir/.username/.opt_data_dir`); fed nested v2 config, every derivation and the recursive combine silently misfire. `modules/ansible/config/load_config.yml`.
- **[medium]** Dead "Integrationen" schema block in `default_config.yml` (`aat_type/aat_runner/aat_description`, `tid_*`, commented `mytools_*`) — superseded by extensions, never read. `config/default_config.yml:29-70`.
- **[medium]** `scripts_dir` key generated + documented but never read — the CLI keys off `commands_dir` instead. `config/default_config.yml:15`, `docs/configuration.md:67`, `README.md:221`, `bin/sot:81,96`.
- **[low]** `runner.sh` `get_cfg` nested-key fallbacks (`aat.enabled`) are never exercised because only flat keys are ever produced — dead defensive branches. `commands/runner.sh:106-135`.

### E. Library load model & global-variable coupling
- **[high]** Child scripts receive framework state through a 10-slot POSITIONAL contract (`CLI_METADATA_ARGS`) appended AFTER user args (`"$script" "$@" "${CLI_METADATA_ARGS[@]}"`), interpreted three incompatible ways: runner slices the LAST 10 (correct); bootstrap reads `$1/$2` (front); vault reads `$4/$5` (fixed front) — the latter two only work with ZERO user args. Config vars are also never `export`ed, so env-reading commands get empty values. Root cause of the F-theme "silent no-op" bugs and the H-theme argv secret leak. `bin/sot:100-111,310`, `commands/runner.sh:20-40`, `commands/bootstrap.sh:19-20`, `commands/vault.sh:36-37`. → Export namespaced `SOT_*` env vars; delete the positional contract.
- **[medium]** Redundant/order-dependent sourcing: `discover_plugins` runs twice (auto at `manager.sh:580` with unset MODULES_DIR, then explicitly `bin/sot:119`); `progress.sh` sourced twice (`init.sh:24` + `bin/sot:65`); the two managers enter via different files. Guards prevent breakage but the graph does hidden double work. → Make `init.sh` the single sourcing entrypoint; remove the auto-run.
- **[medium]** Command scaffolding boilerplate is inconsistent: the root var is named `SCRIPT_ROOT` (runner/vault/bootstrap), `ROOT_DIR` (doctor/demo), and `SOT_ROOT` (extensions/delete/update), computed with `../` vs `../..`, some guarding a missing lib and some not. `commands/*` (nine files). → One sourcing helper + one var name.
- **[medium]** Fallback ANSI color block copy-pasted into 6 files and drifted from the canonical palette (`GREY='\033[1;90m'` vs colors.sh `GREY=$DIM`; uses `PINK` which is only a legacy alias), so output color differs depending on whether the lib loaded. `commands/vault.sh:24-31`, `commands/maintenance/{delete,cleanup_old_users}.sh`, `modules/{docker,sdkman,ansible}/install.sh`.
- **[low]** The validate-then-assign arg-parse block is repeated ~25× in `args_parser.sh` (differing only in var name/message), plus the `while/case/shift` loop reimplemented in four files. `lib/core/bootstrap/args_parser.sh:48-315`, `commands/maintenance/{update,delete}.sh`, `commands/doctor.sh`. → `require_value` helper.

### F. Broken features / bugs
- **[high]** Alias `s`→`setup` is broken end-to-end: no `setup` command/`commands/setup.sh` exists (only `bootstrap`), so `sot s` dies with exit 127. `lib/cli/aliases.sh:25`, `bin/sot:415-419`.
- **[high]** Interactive menu doubly broken: `show_interactive_menu` already consumes the choice via `read`, then `run_interactive_mode` issues a SECOND `read` (first keystroke lost); and the index→command mapping differs (per-category menu excluding `info` vs a flat global `sort` of ALL commands), so selecting N runs a different command than displayed. `lib/cli/registry.sh:262-316`, `bin/sot:368-400`.
- **[high]** `sot help <cmd>` prints "Befehl nicht gefunden" for every pathless registered command (`plugins`, `help`, `version`, `aliases`, all plugin commands) because `show_command_detail` treats an empty stored path as "not found". `lib/cli/registry.sh:229-232`.
- **[high]** `runner.sh` `sync_repo()` execs removed `commands/integrations/{aat,tid}_sync.sh`; since `runner_sync_before_run` defaults true, a plain `SOT runner aat <pb>` calls sync unconditionally and the missing file exits 127 under set -e, aborting the runner before the playbook. `commands/runner.sh:201-219`, `config/default_config.yml:77`. → Call `extension_sync`.
- **[high]** `extensions.sh` `_update_config_value` guards on `[[ -n "${CONFIG_FILE:-}" && -f … ]]`, but `CONFIG_FILE` is never exported → guard always fails → install/remove/enable/disable never persist `<name>_enabled`. Activation is a silent no-op. `commands/extensions.sh:230-239`.
- **[high]** `delete.sh` `create_vault_backup` reads `vault_file/vault_secret` from env (never exported) → always empty → backup silently skipped; the whole `--no-backup` feature is dead. Same cause makes CLONE_DIR/OPT_DATA_DIR/LOG_FILE always fall back to hardcoded defaults, ignoring config. `commands/maintenance/delete.sh:66-73,164-205`.
- **[high]** `bootstrap.sh` advertises `--check`/`--tags` in @usage/@example but never parses options; it reads `modules_dir=$1/config_file=$2`, so `SOT bootstrap --tags ssh` passes garbage to trigger.sh. `commands/bootstrap.sh:6-7,18-19`.
- **[high]** `vault.sh` reads `vault_file=${4}/vault_secret=${5}` (correct only with zero user args), so `SOT vault edit` shifts positions and yields the wrong secret; `view`/`rekey` are documented but unimplemented (always `ansible-vault edit`). `commands/vault.sh:37-38,151`.
- **[high]** `SCRIPTS_DIR` is never resolved in `generate_dynamic_defaults`, so the literal `__GENERATE_SCRIPTS_DIR__` survives into `config.yaml` and the final overview. `lib/core/bootstrap/config_defaults.sh:105-203`, `config_writer.sh:59`, `tasks.sh:265`.
- **[high]** `task_edit_cli` seds for `# __SOT_ROOT_PLACEHOLDER__` which no longer exists in bin/sot (removed with cli_wrapper.sh) — silent no-op that still logs "SOT_ROOT gesetzt" — then appends a hardcoded CONFIG_FILE line duplicating bin/sot:72's own default logic. `lib/core/bootstrap/tasks.sh:139-150`.
- **[high]** Plugin enable/disable never persists: `save_plugin_state` is called (`manager.sh:297,316`) but defined nowhere (guarded by `declare -f`), so state is lost on process exit. `lib/plugins/manager.sh:296-317`.
- **[medium]** `SOT validate` is dead routing: `bin/sot` routes it to `extensions.sh validate`, which has no such case → falls to `*)`, `extension_get` returns empty → "Unbekannter Command: validate". README's install one-liner chains `SOT validate && SOT bootstrap`, so following the README aborts. `bin/sot:465`, `commands/extensions.sh:350`, `README.md:81`.
- **[medium]** Aliases point at non-existent commands: `cfg`→config, `log`→logs, `@l`→logs --tail, `@c`→config --show (no config/logs command registered). `lib/cli/aliases.sh:68-75`.
- **[medium]** Multi-word alias keys (`integrations list/sync`, `aat sync/install`, `tid sync/install`) can never fire — `expand_alias_args` only looks up `$1`. `lib/cli/aliases.sh:50-61`.
- **[medium]** `dependencies.sh` only installs sdkman/docker/ansible (TOOL_COUNT + dispatch hardcoded); any other `-tools` token is silently ignored, contradicting the free-form flag. `bootstrap/dependencies.sh:60-119`.
- **[medium]** `extensions.sh` post-install hint prints `sot runner $name`, but runner only accepts aat/ansible/tid/terraform/list; the real path is `sot ex run <name>`. `commands/extensions.sh:179`.
- **[low]** `dependencies.sh` uses `${BOLD}` but only defines GREEN/GREY/RED/NC locally; run standalone under set -u (as the README documents) this is an unbound-variable fatal error. `bootstrap/dependencies.sh:82`.
- **[low]** `spinner_start` installs `trap '…' EXIT`, unconditionally clobbering any pre-existing EXIT trap for the whole process. `lib/cli/progress.sh:260`.

### G. Error handling & robustness (incl. destructive-without-guards)
- **[high]** Comment-stripping is done blindly with `line="${line%%#*}"` (yaml_parser.sh lines 33,77,120,169,249,335; config_defaults.sh:38-51) BEFORE quotes are handled, so any value containing `#` — vault secrets, passwords, URL fragments, even quoted `"ab#cd"` — is silently truncated. → Only treat whitespace-preceded `#` outside quotes as a comment.
- **[high]** Whitespace trimming uses `xargs`, which interprets quotes/backslashes: a value like `it's` or a lone quote emits "unterminated quote" to stderr and corrupts/empties the value; also collapses internal whitespace. `lib/core/yaml_parser.sh` (lines 43-44,86-87,126-127,180-181). → Trim via bash parameter expansion.
- **[high]** `cleanup_old_users.sh` mass-deletion keyed on unvalidated `currentUsername="${3:-}"`: if invoked with <3 args (as docs/tests imply) it is empty, so NO user matches the exclusion and ALL `/home/[A-Z]{11}` users + homes are `userdel -r`/`rm -rf`'d, gated only by one yes/no prompt with `2>/dev/null || true` swallowing failures. `commands/maintenance/cleanup_old_users.sh:29,55,61-63`. → Fail closed when empty; require user by name.
- **[high]** `update.sh` `--force` is dead code (parsed into FORCE, never read); `update_repo()` unconditionally runs `sudo git reset --hard origin/$branch` + `git clean -fd` with no confirmation, though the header implies one exists. Same unguarded pattern in `task_clone_repository`. `commands/maintenance/update.sh:49,58,150-152`, `lib/core/bootstrap/tasks.sh:97-99`. → Implement the gate or remove the flag.
- **[high]** The "clone-if-absent else update" git-sync pattern is reimplemented four times with divergent semantics — pull (bootstrap/init.sh, extensions/manager.sh) vs destructive `reset --hard`+`clean` (tasks.sh, update.sh) — so "update SOT" is non-destructive in one path and data-losing in another; each duplicates its own git-install guard. `bootstrap/init.sh:85-94`, `lib/core/bootstrap/tasks.sh:93-107`, `lib/extensions/manager.sh:128-149`, `commands/maintenance/update.sh:107-162`. → One `git_sync_repo` helper.
- **[medium]** `safe_delete()` runs `sudo rm -rf` on config-derived paths (clone_dir, opt_data_dir, systemlink_path, log_file) with only a `[[ -d ]]` check — no guard against empty/`/`/`/usr`. `extensions.sh:220` similarly `rm -rf`s a config-derived dir. `commands/maintenance/delete.sh:127-158,66-72`. → Assert absolute + non-empty + min-depth + denylist.
- **[medium]** Inconsistent strict mode: `bootstrap.sh`, `demo-progress.sh`, `trigger.sh`, `modules/docker/install.sh`, `modules/ansible/install.sh` set no `set -euo pipefail` (docker install continues after a failed `apt-get update`; bootstrap.sh assigns empty paths silently). Their siblings all set it. → Add strict mode to every executed script.
- **[medium]** `run_tasks` unconditionally prints "✓ Installation erfolgreich abgeschlossen" even when non-critical tasks (writeConfigFile, editCliFile, installDependencies) fail, and exits 0. `lib/core/bootstrap/runner.sh:164-229`. → Track a failure flag; reflect it in footer + exit.
- **[medium]** Colors emitted unconditionally with no TTY/NO_COLOR detection, so raw ANSI escapes leak into pipes, redirected logs, and files. `lib/core/colors.sh`, `lib/core/helpers.sh:110-154`. → Blank vars when `! -t 1` or NO_COLOR.
- **[medium]** `get_nested_value`/`get_yaml_value` re-read and re-scan the entire file on every call, forking 3-5 subprocesses per line — quadratic if used in loops. `lib/core/yaml_parser.sh:109-143,225-297`. → Load once into an array.
- **[low]** Under set -u several functions read bare `$1` after `shift`, aborting with "unbound variable" before the intended friendly error. `commands/extensions.sh:128,184,319`, `lib/core/bootstrap/args_parser.sh:63,72`. → Use `${1:-}`.
- **[low]** `resolve_path` runs `cd "$(dirname …)"` NOT in a subshell (masked only because it's always called via `$(…)`). `lib/core/helpers.sh:85-105`.
- **[low]** Quote stripping removes one leading/trailing quote independently (asymmetric/embedded quotes mishandled); only one nesting level supported; list items dropped. Inconsistent CRLF handling in the `load_config` sniffer (strips `#` but not `\r`, unlike other loops). `lib/core/yaml_parser.sh:47-50,335`.

### H. Security & shell safety
- **[high]** The Ansible-Vault master secret is written in cleartext into `config.yaml` (`vault.secret`); `.settings` is `mkdir -p` (no mode) and the file `touch`'d (no chmod) → world-readable 0644 under root's default umask, and `runner.sh` further feeds the whole file to ansible via `-e "@$config_file"`. Fully defeats ansible-vault's at-rest encryption. `lib/core/bootstrap/config_writer.sh:87`, `tasks.sh:135,111-132`, `commands/runner.sh:715`. → Store only a reference to a 0600 root-owned file; chmod 600 + mode 0700.
- **[high]** Vault secret passed on the command line (`CLI_METADATA_ARGS` includes `vault_secret`, appended in `execute_script`), so it is world-readable via `ps aux`/`/proc/<pid>/cmdline` for the duration of any child command. `bin/sot:104,310`, `commands/vault.sh:37`, `commands/runner.sh:37`. → Never pass secrets on argv; use env or a 0600 file.
- **[high]** `read_vault_parameter` defaults `--vault-password-file` to a persistent unencrypted `{{opt_data_dir}}/vault_pass.txt` that nothing creates 0600 or removes — a permanent plaintext copy of the vault password. `modules/ansible/roles/read_vault_parameter/tasks/main.yml:3,13`. → Use the RAM-tmpfs+shred pattern.
- **[high]** `create_vault_backup` writes the vault secret in cleartext into `/tmp/sot-backup-<timestamp>/BACKUP_INFO.txt` and copies the vault file into world-traversable `/tmp`; dir is `mkdir -p` (0755) and files written before `chmod 600` (TOCTOU window). `commands/maintenance/delete.sh:165,184-198`. → `mkdir -m 700` in a root-only dir; never persist the secret to a text file.
- **[high]** `read_vault_parameter` `debug: msg: "{{ vars | to_yaml }}"` dumps the ENTIRE variable namespace (db_password, api_key, vault_secret, decrypted vault vars) to stdout/logs with no `no_log`. `modules/ansible/roles/read_vault_parameter/tasks/main.yml:38-39`. → Remove; audit for `no_log`.
- **[medium]** Bootstrap trust chain has no integrity/authenticity verification: `curl|bash` entrypoint, unpinned git clone + exec, network-downloaded `default_config.yml` parsed straight into root-driving shell vars, `curl … | bash` for SDKMAN and `sh get-docker.sh`. MITM/compromised upstream = root RCE. `bootstrap/init.sh:102`, `config_defaults.sh:27`, `modules/sdkman/install.sh:27`, `modules/docker/install.sh:33`. → Pin commits; verify checksums/signatures.
- **[medium]** `_update_config_value` builds a `sudo sed -i "s|^${key}:.*|…|"` from an unsanitized user-supplied extension name (`${name}_enabled`); sed metacharacters/`|` can corrupt the program or retarget lines in the root-owned config. `commands/extensions.sh:230-238`. → Validate name `^[a-z0-9_]+$`; avoid sed.
- **[medium]** Unrestricted YAML-key→shell-var assignment: `parse_yaml_to_vars` derives the var name from the key (only spaces/dashes→underscore, no allowlist) then `printf -v` — a key like `PATH:`/`IFS:`/`LD_*:` in the user-editable config silently clobbers that shell var in the running CLI. `lib/core/yaml_parser.sh:43-53`, `lib/core/bootstrap/config_defaults.sh:57-63`. → Allowlist/namespace-prefix; reject dangerous names.
- **[medium]** Vault role writes password + decrypted content to predictable epoch-named files in shared `/dev/shm` (`.vault_pass_{{epoch}}`, `.temp_vault_content_{{epoch}}.yml`) — guessable, enabling a symlink pre-creation race against a root-written secret. `modules/ansible/roles/vault/tasks/main.yml:47,56,61`. → Use `ansible.builtin.tempfile`.
- **[low]** `run_with_progress` runs its count arg via `eval "$count_cmd"` — latent injection the moment any config/user value flows in. `lib/cli/progress.sh:424`. → Array invocation.
- **[low]** On a missing vault key the role substitutes hardcoded weak secrets (`db_password: default_password`, `api_key: default_api_key`, `default_server_ip`), masking a failed decrypt with predictable credentials. `modules/ansible/roles/read_vault_parameter/tasks/main.yml:23-24`. → `fail` loudly.
- **[low]** Loader `chmod +x` then executes discovered scripts in one step (plugin installers, commands, hooks) as the invoking user (often root) — security rests entirely on filesystem perms of `/opt/SOT`; a group/world-writable tree = root RCE. `lib/plugins/manager.sh:273,350,398`, `bin/sot:307`. → Require pre-executable root-owned files; verify dir perms.

### I. Docs / README / CI drift
- **[high]** The entire `ci/` test-runner directory is documented everywhere but does not exist: `./ci/run-all-tests.sh` + `run-{helpers,yaml,bootstrap,integration}-tests.sh` with fixed counts. Real harness is `tests/run-all.sh` + `tests/{unit,integration}/*.sh`. `README.md:366-377,499`, `CONTRIBUTING.md:163-218`, `docs/development.md:139-207`, `docs/configuration.md:196`. → Mechanical find/replace to the tests/ layout.
- **[high]** `security.yml` ShellCheck-strict steps scan nonexistent `scripts/` (57-60) and `ci/` (67-70) dirs, end in `|| true` → silently green; the real `commands/` (largest attack surface) is never strict-checked. False-green security summary. `.github/workflows/security.yml:57-70`. → Point globs at lib//commands//bootstrap//tests/.
- **[high]** The injected-parameter contract is documented two wrong ways: `cli-reference.md`'s table claims positional `$1=command,$2=config_file…` at the FRONT, and `README` claims NAMED flags (`--config_file`, `--vault_file`) — reality is 10 metadata args appended AFTER user args. `docs/cli-reference.md:197-213`, `README.md:169-174`.
- **[high]** `cli-reference.md` + README document a command surface removed by the integrations→extensions refactor: `SOT integrations validate`, `SOT aat/tid sync`, `SOT maintenance update/delete/cleanup_old_users`, `SOT integrations list/add`. Actual registry exposes bootstrap/doctor/vault/runner/update/delete/extensions/plugins. `docs/cli-reference.md:96-193`, `README.md:134-297`.
- **[high]** Completions are pre-refactor: top-level verbs `setup … integrations`, an `integrations add ansible|terraform` flow, hardcoded `/etc/DevOpsToolkit` config path, `complete -F … SOT`/`#compdef SOT` while the binary is `sot`; no completion for bootstrap/doctor/extensions/plugins. Three definitions (static bash, static zsh, `registry.sh` generator) all mutually inconsistent; the static files are never installed. `completions/sot-completion.{bash,zsh}`, `lib/cli/registry.sh:322-412`. → Generate from `CLI_COMMANDS` at runtime.
- **[medium]** README full-install quickstart chains `SOT aat sync && SOT tid sync && SOT validate && SOT bootstrap`, but post-refactor aat/tid are extensions not installed by default (bootstrap explicitly says run `sot ex install aat`) → quickstart fails as written. `README.md:76-82`.
- **[medium]** README documents `SOT integrations add <name> <type>` as a config-template generator; no such generator exists (`extensions.sh` maps `add`→`install`, which clones an already-configured extension). `README.md:135,242,281`, `commands/extensions.sh:354`.
- **[medium]** README links `lib/README.md` and `ci/README.md` (both absent); dir tree + CONTRIBUTING still show `lib/cli/integrations.sh`, `commands/integrations/`, `config/validators/` (gone). `README.md:322,331,484,485`, `CONTRIBUTING.md:8-35`.
- **[medium]** `architecture.md` references `get_config_value()` (defined nowhere) and shows single-arg `load_config` (real signature needs a target array name); also names removed `setup_sot.sh`. `docs/architecture.md:60,105,133,139`, `docs/configuration.md:172-174`.
- **[medium]** `bootstrap.md` documents nonexistent `sot debug delete` / `sot config edit` and links dead `EXTENSIONS.md`/`CONFIG.md`; `style-guide.md` links dead `BOOTSTRAP.md`. `docs/bootstrap.md:175,216,283-284`, `docs/style-guide.md:317`.
- **[medium]** Install/config paths contradict across docs: `configuration.md` says `/etc/DevOpsToolkit/config.yaml`, `bootstrap.md` says `/opt/SOT/production/.settings/config.yaml`, README says clone `/etc/DevOpsToolkit` + symlink `/usr/sbin/SOT`, `bin/sot` defaults `/opt/SOT`. Real path is `/etc/DevOpsToolkit/setup/<branch>/.settings/config.yaml` — matching no doc. `docs/configuration.md:11`, `docs/bootstrap.md:92,164`, `README.md:86,180`.
- **[low]** Value drift: `runner_default_mode` documented "ansible" vs code "aat"; vault-secret length "32-stellig" (configuration.md) vs "60+ Zeichen" (README). `docs/configuration.md:107,125`, `README.md:464`.
- **[low]** `.pre-commit-config.yaml` excludes nonexistent `ci/bin/`; `development.md` references absent `.vscode/extensions.json` + `CHANGELOG.md`. `.pre-commit-config.yaml:18-22`, `docs/development.md:38,287-291`.
- **[low]** Reverse drift: `doctor` and the whole `plugins` meta-command are documented nowhere; `demo-progress.sh` is undocumented and hidden. Inconsistent `SOT` vs `sot` casing across bin/sot usage strings + README. `docs/cli-reference.md`, `bin/sot:128,151,157`, `README.md:36,139`.

### J. Dead code & leftover-from-refactor artifacts
- **[medium]** `discover_commands` + `extract_script_metadata` (registry.sh:47-135) are never called — the entire `# @cmd/@category/@description` header convention is parsed by nothing (all commands hand-registered). Its `integrations/*)→CMD_CATEGORY=sync` branch references a removed dir and a category not in CLI_CATEGORIES.
- **[low]** Dead helpers with zero product callers: `log_command`, `find_config_file_arg`, `run_with_timeout`, `dim`, `resolve_path`, `is_false` (tests only), legacy `parse_yaml_to_vars`/`get_yaml_value`. `lib/core/helpers.sh`, `lib/core/yaml_parser.sh`. Deprecated `PINK`/`GREY` aliases. `lib/core/colors.sh:22-23`.
- **[low]** `run_plugin_hook` + all 6 call sites are permanently dead (no module ships a `hooks/` dir and the no-metadata branch never sets `PLUGIN_HOOKS`); `register_plugin` no-metadata fallback is unreachable (all modules have module.yml); `plugin.yml` candidates reference a file that doesn't exist. `lib/plugins/manager.sh:144,172-208,328-355`.
- **[low]** `task_sync_extensions` (tasks.sh:196-211) defined but never wired into SETUP_TASKS (extension sync moved to `sot ex install`); `run_tasks_sync` (runner.sh:231-236) self-labelled deprecated, zero callers.
- **[low]** cli_wrapper.sh leftovers: `# __SOT_ROOT_PLACEHOLDER__` sed target (tasks.sh:142) matches nothing; `createCliWrapperSbinLink` label (runner.sh:23, init.sh:179) still names the removed wrapper; `initalScriptOverview` typo frozen into the task-name contract (init.sh:183).
- **[low]** `FULL`/`-full` flag parsed + echoed but drives no behavior (args_parser.sh:61-69); `SDKMAN_DEFAULT_CANDIDATES` read but never set (dependencies.sh:31); `bin/sot:3-11` banner block is an unused duplicate of `show_banner`.
- **[low]** Half-migrated setup naming: `_SOT_SETUP_LIB_INIT_LOADED`, `SETUP_LIB_DIR`, `tests/unit/setup.sh` (guard/header still say "SOT Setup Library").
- **[low]** Ansible dead artifacts: `roles/variables/variables/main.yml` in a non-standard subdir Ansible never loads; `protection/handlers/main.yml` empty placeholder; `protection/meta/main.yml` uses invalid `collections:` key; empty `group_vars/`/`hooks/`/`vault/` gitkeeps; large commented-out example block in `vault_template.j2:27-54`.

### K. Tests
- **[high]** `integration.sh:56` greps `sot help` output for "setup" (renamed to bootstrap) — never matches, FAILS on CI (label was updated, grep string wasn't). `tests/integration/integration.sh:56`.
- **[high]** `integration.sh:78` checks `[[ -d commands/integrations ]]` — dir removed in the extensions refactor → FAILS. `tests/integration/integration.sh:78`.
- **[high]** `((TESTS_FAILED++))`/`((TESTS_RUN++))` under set -euo pipefail returns exit 1 when the counter is 0, so the first failing assertion ABORTS the whole suite (masking later tests). Same footgun in `helpers.sh:22,34` and `setup.sh:24,36`; `config.sh`/`vault.sh` use the safe idiom — inconsistent. → Extract one harness with `x=$((x+1))`.
- **[medium]** Vault "security" tests are mostly `grep` over the script SOURCE + localized German UI strings ("sicher gelöscht", "shred", "no_log: true") — they assert keywords present, not that secure deletion happens; any reformat breaks them. `tests/integration/vault.sh:86`. → Behavioral assertions via the mock ansible-vault.
- **[medium]** Zero coverage for the refactor's headline systems: `lib/extensions/manager.sh`, `lib/plugins/manager.sh`, `commands/extensions.sh`, `config_writer/runner/tasks.sh`, `doctor.sh`, `maintenance/*`. `tests/run-all.sh:49`.
- **[medium]** `yaml.sh` has no pass/fail counter and exits 1 on the first mismatch (fail-fast), hiding all later YAML assertions. `tests/unit/yaml.sh:20`.
- **[medium]** README claims "69+ tests" with per-suite counts (34/5/15/15) — actual `run_test` counts are ~42/32/32/6 and cli.sh/config.sh use a different style; both total and breakdown are wrong. `README.md:54,371-374`.
- **[low]** Expectations hardcoded to fixture values (`ssh_port=282`, `aat_enabled=true`) across yaml/setup/config/integration suites — any config edit breaks multiple suites.
- **[low]** Whole suite requires bash ≥4 (`declare -A/-g`); on the developer's macOS bash 3.2 nothing runs (`bin/sot help` aborts with `declare: -g: invalid option`) — tests are Linux/CI-only. `tests/unit/helpers.sh:7`.

### L. Ansible module quality
- **[high]** `protection/tasks/main.yml:19` enables UFW with `policy: allow` — a default-ALLOW inbound firewall, making it a no-op (opposite of a hardening baseline). → `deny` incoming.
- **[high]** `container_setup.yml:10` references `role: readVaultParameter` but the directory is `read_vault_parameter` (snake_case in module.yml too); Ansible role lookup is exact-match → play fails immediately, container_setup is non-functional. `modules/ansible/playbooks/container_setup.yml:10`.
- **[high]** Vault password lifecycle is inconsistent: the vault role writes+shreds an ephemeral epoch-named pass file and `vault_secret` is a never-persisted `lookup('password','/dev/null')`, yet `read_vault_parameter` decrypts with `{{opt_data_dir}}/vault_pass.txt` which is never created — decryption is guaranteed to fail and the encryption password is unrecoverable. `modules/ansible/roles/read_vault_parameter/tasks/main.yml:3`, `roles/vault/tasks/main.yml:47`, `config/load_config.yml:74`.
- **[high]** `common/tasks/main.yml:16` regexp is literally `^127\\.0\\.1\\.1\\s+.*` (double-backslash bytes); in a single-quoted YAML scalar the backslashes stay literal so `\\.`/`\\s` never match a real line → `lineinfile` APPENDS a duplicate `127.0.1.1` entry. `modules/ansible/roles/common/tasks/main.yml:16`.
- **[medium]** Inverted hardening posture: `common` adds a root SSH `authorized_key` (enabling root SSH login) while the created user gets no sudo/password (unusable for admin). `modules/ansible/roles/common/tasks/main.yml:28-39`.
- **[medium]** Debian/Ubuntu-only: hardcoded `ansible.builtin.apt` + `ppa:ansible/ansible` with no `when: ansible_os_family` guard, despite os_family being tracked in the vault template. `modules/ansible/roles/common/tasks/main.yml`, `roles/protection`, `install.sh`. → `ansible.builtin.package` + guards.
- **[medium]** `load_config.yml:94` sets `ansible_facts: "{{ sot_config }}"`, injecting every config key as a top-level fact and abusing/clobbering the reserved `ansible_facts` namespace (fragile ordering vs fact-gathering). → Reference `sot_config.*` directly.
- **[medium]** `trigger.sh:56-67` bakes Docker detection/installation into the generic Ansible trigger, so every host_setup run does an unrelated docker check/install. `modules/ansible/commands/trigger.sh:56-67`.
- **[low]** `ansible.cfg:12-13` comment "Aktiviert detaillierte Fehlermeldungen" sits directly above `deprecation_warnings = False` (which disables them) — contradictory.
- **[low]** Both playbooks declare an empty `tasks:` key above `roles:` — dead noise. `host_setup.yml:6`, `container_setup.yml:6`.

---

## 3. Refactor Opportunities

Deduplicated across map `refactorOpportunities` + audit `recommendation`s. Effort S/M/L.

**Target architecture (from the audit agents' unification proposal):** Collapse module/plugin/extension/integration to ONE "extension" concept behind a SINGLE registry with one manifest contract and one loader, where a source is either a local dir (`modules/`) or a remote git repo (aat/tid) expressed as two provider strategies behind the same interface. Merge `lib/plugins/` + `lib/extensions/` into one module; delete the rival manager, the `integration` type, and the legacy `integrations` command. Load ONE canonical config once into an associative array / exported `SOT_*` env vars (kill the positional metadata contract); use ONE YAML parser; derive ALL install paths from ONE `SOT_ROOT` constant.

- **Unify extensions + plugins into one capability manager** — one registry/lifecycle/dispatch; git-repo extensions become a provider strategy; deletes the duplicated `extension_*`/`plugin_*` code and the third enable/disable in extensions.sh. **L**
- **Pick ONE config schema (flat v1 or nested v2) and delete the other** — root cause of D-theme mis-parses/broken merges; then drop the dual-key `get_cfg` fallbacks and case-variant probing. **L**
- **Consolidate to one YAML parser + one config-read/write path** — route all reads through `yaml_parser.sh` (fold in `parse_plugin_yaml` + `config_defaults.sh` inline loop); one get/set config-mutation helper used by extensions.sh + plugin persistence + bootstrap. **M**
- **Fix the shared YAML line-parser once** (strip `\r`; treat only whitespace-preceded `#` outside quotes as comment; trim via parameter expansion not xargs; strip matched quote pair) — kills both HIGH data-corruption bugs. **M**
- **Replace positional `CLI_METADATA_ARGS` with exported `SOT_*` env vars** — decouples user args from framework state; fixes bootstrap/vault/extensions/delete at once; removes the argv secret leak. **L**
- **Unify on one install root** — eliminate `/opt/SOT` vs `/etc/DevOpsToolkit` double-clone (+ remove /opt/AAT fallback); derive CLI_FILE/MODULES_DIR/symlink from one constant so the executed CLI is the patched one; single-source install paths into docs. **M-L**
- **Fix vault_template + `__GENERATE_*__` resolution** — repoint to `bootstrap/` (or emit raw placeholder for Ansible fixup); add SCRIPTS_DIR; fail loudly if any `__GENERATE_*__` survives into config.yaml. **S**
- **Stop persisting VAULT_SECRET in plaintext** — store the password in a 0600 root-only file (referenced by path); `chmod 600` config.yaml + `.settings` 0700; remove `vault_secret` from argv; use `ansible.builtin.tempfile` + no_log. **M**
- **Extract one `git_sync_repo <dir> <url> <branch> <mode>` + `ensure_git()` helper** — replaces the 4 divergent clone-or-update sites; decide once whether update is destructive; add a confirmation/`--force` gate. **M**
- **Harden destructive maintenance** — fail-closed on empty currentUsername; denylist guard in `safe_delete`; wire `--force`; secure temp dirs (`mktemp -d`/`mkdir -m700`). **M**
- **Unify dispatch on one table-driven resolver** — delete per-verb `case` arms; route through alias-expansion → `resolve_and_execute`; give plugin commands a real executor. **M**
- **Wire up `discover_commands` + `@cmd` metadata; delete the hand-written registry** — single source of truth for command listing. **M**
- **Derive aliases/help/completions from live `CLI_ALIASES`/`CLI_COMMANDS`** — delete the three stale completion definitions + dead aliases (`s`→setup, cfg/log/@l/@c, multi-word keys); fixes drift structurally. **M**
- **Fix + consolidate the interactive menu** — one read, one index→command ordering; fix pathless-command `help`. **S**
- **Correct Ansible hardening + bugs** — UFW deny-incoming; snake_case role refs; `/etc/hosts` regex escaping; drop the full-vars debug dump; OS abstraction (`package` + os_family); stop abusing `ansible_facts`; separate Docker from the generic trigger. **S-M**
- **Standardize a command-scaffolding snippet + one root var name (`SOT_ROOT`)**; centralize the fallback color block; `require_value` arg helper. **S-M**
- **Make dependency install data-driven** — loop over TOOLS dispatching to `modules/<tool>/install.sh`; compute TOOL_COUNT from the resolved list. **M**
- **Honest task-result reporting** — track per-task exit; footer + exit reflect actual outcome; consider promoting installDependencies/writeConfigFile to critical. **S**
- **Add strict mode + TTY/NO_COLOR awareness** to every executed script / colors.sh. **S**
- **Tests:** fix the two stale `integration.sh` assertions (immediate green-CI win); extract `tests/lib/assert.sh` fixing the set -e counter footgun; add coverage for extensions/plugins/config_writer; convert vault.sh to behavioral assertions; recompute test counts. **S-L**
- **Docs/CI:** global find/replace `ci/`→`tests/`; fix `security.yml` ShellCheck globs to real dirs; regenerate command docs + completions from the registry; add a docs-lint/link-checker to CI; single-source install paths; write the missing `docs/extensions.md`. **S-M**
- **Prune dead code** — save_plugin_state/hooks lifecycle, task_sync_extensions/run_tasks_sync, __SOT_ROOT_PLACEHOLDER__/createCliWrapperSbinLink, FULL flag, dead helpers, v2 file, dead integrations config block, ansible dead artifacts. **S**

---

## 4. Severity Tally

Counts across the deduplicated Section-2 inventory (max severity per merged entry):

| Severity | Count |
|----------|-------|
| High     | 27    |
| Medium   | 36    |
| Low      | 25    |
| **Total**| **88**|

Per-theme totals: A 0H/1M/3L · B 3H/2M/1L · C 3H/1M/1L · D 4H/6M/1L · E 1H/3M/1L · F 11H/5M/2L · G 5H/5M/3L · H 5H/4M/3L · I 5H/6M/3L · J 1M/8L(grouped) · K 3H/4M/2L · L 4H/4M/2L.

### Top 10 highest-impact items
1. **Config format split (writer emits nested v2, all readers assume flat v1)** [D, high] — user-chosen settings are silently stripped/mis-merged; ssh.port/data_dir/enabled/branch collide, so real setups run on defaults. Corrupts the primary config contract.
2. **Vault secret handled insecurely at every step** [H, high×4] — cleartext in world-readable config.yaml, on argv (`ps aux`), in a persistent `vault_pass.txt`, and in a `/tmp` backup; plus a full-vars debug dump. Collectively defeats ansible-vault entirely.
3. **`cleanup_old_users.sh` mass-deletes all users on empty `$3`** [G, high] — the "current user" default is empty, so with <3 args it `userdel -r`/`rm -rf`s every matching home behind one prompt. Catastrophic, irreversible data loss.
4. **Four concepts / two managers for one "capability" idea** [B, high] — module/plugin/extension/integration split across three disjoint subsystems is the central architectural debt that all other extensibility bugs (persistence, dispatch, manifest) stem from.
5. **Two install roots + CLI-edit-vs-symlink mismatch** [C, high] — `/opt/SOT` vs `/etc/DevOpsToolkit` double-clone means users invoke an un-patched CLI and cannot locate config.yaml; poisons bootstrap correctness.
6. **Positional `CLI_METADATA_ARGS` contract + never-exported config vars** [E/F, high] — the single design flaw that breaks `bootstrap --check`, `vault edit`, extensions enable/disable, and delete backup, and leaks the vault secret on argv.
7. **`runner.sh` sync_repo calls removed integrations scripts** [F, high] — because `runner_sync_before_run` defaults true, the headline `SOT runner aat <pb>` aborts (exit 127) before any playbook runs.
8. **UFW `policy: allow`** [L, high] — the hardening role installs a firewall that permits everything by default: a security control that is worse than absent.
9. **Vault password lifecycle mismatch + broken container_setup role ref** [L, high] — encrypt uses an ephemeral secret, decrypt reads a file that is never created; the container play also references a nonexistent role — the Ansible vault/container flow cannot work end-to-end.
10. **YAML parser `#`-truncation + xargs corruption** [G, high] — the shared parser silently mangles any value containing `#`, quotes, or backslashes (secrets, passwords, URLs) — a data-integrity bug under every config read.

_Runner-up (docs/CI): the pervasive `ci/`-directory drift + `security.yml` false-green + two red integration-test assertions mean CI reports success while the documented workflow and security scan are inoperative._
