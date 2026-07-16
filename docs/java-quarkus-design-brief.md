# SOT Rewrite — Consolidated Design Brief (Bash → Java 21 / Quarkus / GraalVM native)

Synthesised from the 9 layer-design agents. Canonical root package: **`de.jklein.sot`** (from the build foundation, matching Maven groupId `de.jklein.sot`). Sibling layers proposed divergent roots (`de.sot`, `dev.sot`, `com.sot`, `io.sot`) — all normalised to `de.jklein.sot.*` below; the naming conflict is logged in §7. Single-module Maven build, Java 21, Quarkus 3.37+, Mandrel/GraalVM native. External tools (ansible, ansible-vault, terraform, git, docker) are kept and shelled out via `ProcessBuilder`; Ansible playbooks/roles are embedded as classpath resources.

---

## 1. Per-Layer Design

### 1.1 project-build-foundation  (effort: L)
Single-module Maven project (`de.jklein.sot:sot`, Java 21) bootstrapped via `quarkus-maven-plugin:3.37.0:create -Dextensions='picocli,quarkus-jackson'`. Foundation owns the cross-cutting skeleton in `de.jklein.sot.runtime` + build files; siblings fill `cli/config/extension/vault/bootstrap/runner/process/doctor`. Provides the ONE shared `YamlMapperProducer` (@Produces YAMLMapper, kills R1's 4 parsers), `SotPaths` (one canonical layout from `$SOT_HOME`, default `/opt/SOT`, kills R4), `AssetExtractor` (classpath `ansible/**`,`docker/**`,`templates/**` → writable runtime dir), and `ReflectionConfig`. `application.properties` pins `quarkus.native.resources.includes`, `add-all-charsets=true`, Mandrel builder image. JVM profile = dev inner loop; `native` profile (`-Dnative`) via container-build. GitHub Actions release matrix (linux amd64/arm64, macos arm64) + thin `install.sh` (only remaining shell). Assets move under `src/main/resources/`.
- pom.xml — config — single-module Maven build, quarkus-bom 3.37+, native profile via -Dnative
- src/main/resources/application.properties — config — native resource includes, add-all-charsets, Mandrel image, banner off
- de.jklein.sot.cli.SotCli — @Command — @TopCommand root shell (quarkus-picocli auto-provides @QuarkusMain); one entrypoint replacing bin/sot
- runtime.YamlMapperProducer — CDI-bean — @Produces the single shared Jackson YAMLMapper
- runtime.SotPaths — CDI-bean — resolves one canonical install/asset/config layout from $SOT_HOME
- runtime.AssetExtractor — CDI-bean — copies embedded assets to writable dir so native shell-outs can exec them
- runtime.ReflectionConfig — config — @RegisterForReflection over all config records + @RegisterResources
- .github/workflows/release.yml — config — native build matrix producing per-platform binaries
- install.sh — resource — platform detect + download prebuilt binary + symlink (the only shell)
- mvnw / .mvn/wrapper — config — pinned Maven wrapper for reproducible builds

### 1.2 cli-command-layer  (effort: L)
Package `de.jklein.sot.cli`. One root `@TopCommand SotCommand implements Callable<Integer>` declaring the whole subcommand tree `{Bootstrap, Doctor, Vault, Runner, Extensions, Plugins, Update, Delete, Interactive, Help, AutoComplete.GenerateCompletion}`. Every command is a CDI bean (quarkus-picocli); state arrives by **constructor injection** of typed services (SotConfig, SotPaths, ExtensionService, VaultService, ProcessRunner, ConsoleService) — never positional argv, which structurally dissolves R3 (no `CLI_METADATA_ARGS`). Global options live once on root with `scope=INHERIT` (`--config/--profile/-v/--no-color`). Dispatch is exactly one path: `CommandLine.execute(args)` in `@QuarkusMain Main`. Aliases use native picocli `@Command(aliases=…)`; a dangling alias is uncompilable. Help/version/completion all derived from live `CommandSpec` (no printf drift). Interactive mode re-renders the same CommandSpec tree.
- SotCommand — @Command — root; declares subcommand tree + inherited globals + version/help mixin
- Main — class — @QuarkusMain; AliasExpander pre-parse, exception+exit-code handlers, the single dispatch
- BootstrapCommand / DoctorCommand / VaultCommand / RunnerCommand / ExtensionsCommand / PluginsCommand / UpdateCommand / DeleteCommand / InteractiveCommand — @Command — verb subcommands injecting typed services
- SotVersionProvider — class — IVersionProvider reading build-time version + git commit
- AliasExpander — CDI-bean — typed Map<String,List<String>> for combo aliases (@f→doctor --fix), expanded pre-parse
- AliasCheatSheetRenderer — class — IHelpSectionRenderer generating alias footer from live spec
- ConsoleService / ProgressReporter — interface — ANSI/color + progress abstraction (TTY/--no-color aware)
- SotExitCode — enum — typed exit codes (OK/USAGE/NOT_FOUND/RUNTIME) via setExitCodeExceptionMapper

### 1.3 config-model  (effort: L)
Package `de.jklein.sot.config`. ONE canonical nested-v2 schema as immutable records rooted at `SotConfig(system, ssh, logging, paths, tools, ansible, vault, runner, Map<String,ExtensionConfig> extensions)`. AAT/TID are no longer hardcoded fields — just entries in `extensions`, each a uniform `ExtensionConfig(enabled, repoUrl, dir, branch, inventoryPath, inventoryVars)`. Parsing happens once in `YamlConfigCodec`: read each source to `JsonNode`, `ConfigMerger` deep-merges override trees onto the default template, then `treeToValue`→`SotConfig` once. SnakeYAML tokenisation makes `#`-in-quotes/apostrophe/backslash corruption impossible; fixed record fields stop a stray `PATH:`/`IFS:` key clobbering shell vars. `PlaceholderResolver` resolves `__GENERATE_*__` sentinels topologically via a `GeneratedValue` enum; `ConfigValidator` runs Hibernate Validator + a hard gate rejecting any surviving placeholder. Vault master secret is NOT a field — `VaultConfig` holds only a `Path secretRef`; `SecretStore` keeps it in a 0600 root-owned file, so Jackson can never serialise it.
- SotConfig — record — root aggregate; single canonical schema + Map<String,ExtensionConfig>
- SystemConfig/SshConfig/LoggingConfig/PathsConfig/ToolsConfig/AnsibleConfig/RunnerConfig — record — typed sections with Bean-Validation constraints
- VaultConfig — record — vault settings WITHOUT plaintext secret (file, content, mail, Path secretRef)
- ExtensionConfig — record — uniform per-extension shape shared by aat/tid/custom
- GeneratedValue — enum — every __GENERATE_*__ sentinel with dependency-ordered derivation lambda
- HostContext — record — host facts (hostname, SecureRandom, install root) for derivation
- YamlConfigCodec — CDI-bean — single YAML read/bind/serialize path
- ConfigMerger — CDI-bean — deep JsonNode merge of default template + overrides before one bind
- PlaceholderResolver — CDI-bean — resolves surviving placeholders topologically → new immutable record
- ConfigValidator — CDI-bean — Hibernate-Validator + hard gate on leftover placeholders
- SecretStore — CDI-bean — reads/writes vault master secret to a 0600 root-owned file
- ConfigService — CDI-bean — single load/get/set/save facade (replaces sed/config_writer/save_plugin_state)
- YamlMapperProducer — CDI-bean — @Produces build-time YAMLMapper (record module tuned)
- default_config.yml — resource — the ONE canonical nested template on classpath

### 1.4 extension-capability-layer  (effort: L)
Package proposed `dev.sot.capability` → normalised `de.jklein.sot.extension`. Collapses module/plugin/extension/integration into ONE **Capability** concept sourced by pluggable `CapabilityProvider` CDI strategies (`origin()`, `discover()`, `materialize/remove/sync()`, `mutable()`). Two beans: `LocalDirectoryProvider` (@Identifier("local"), NIO-walks `$SOT_HOME/modules/*/module.yml`, immutable) and `RemoteGitProvider` (@Identifier("remote-git"), typed `RemoteCapabilityDef` for AAT/TID, git clone/pull) — R2's split dissolves structurally. `CapabilityRegistry` injects `@All List<CapabilityProvider>` (build-time CDI) into one `Map<String,Capability>`. `CapabilityService` is the SINGLE lifecycle owner (list/info/install/remove/enable/disable/sync/run). `ExtensionManifest` is a typed `@RegisterForReflection` record (name, version, `CapabilityType`{TOOL,SERVICE,RUNNER}, Requirements, deps, apiVersion) parsed by one Jackson `ObjectMapper(YAMLFactory)`. State persists via `CapabilityStateStore` → `capabilities.yml`. Remote ops route through shared `GitService`; removal through `SafeFsRemover` (absolute+min-depth+denylist); runner assets invoked via ProcessBuilder argv (never chmod+x-then-exec). Deps resolved topologically before install.
- CapabilityProvider — interface — SPI strategy over one backend (discover/materialize/remove/sync/mutable)
- LocalDirectoryProvider — CDI-bean — @Identifier("local"); walks modules/*/module.yml
- RemoteGitProvider — CDI-bean — @Identifier("remote-git"); typed RemoteCapabilityDef, clone/pull via GitService
- CapabilityRegistry — CDI-bean — @All List<CapabilityProvider> → one Map<String,Capability>
- CapabilityService — CDI-bean — single lifecycle owner (validation, dep resolution, state, view)
- ExtensionManifest — record — typed model of module.yml (one schema, one parser)
- Capability — record — runtime aggregate: manifest + origin + resolved path + enabled state + provider id
- CapabilityType — enum — TOOL|SERVICE|RUNNER; old 'integration' → REMOTE_GIT origin
- CapabilityStateStore — CDI-bean — typed round-trip persistence to capabilities.yml
- ManifestParser — CDI-bean — wraps ObjectMapper(YAMLFactory); parse+validate at discovery
- ExtensionsCommand — @Command — picocli parent (aliases ex) with subcommand beans
- RemoteCapabilityDef — record — typed remote def (name/repoUrl/branch/dir/runner) from config

### 1.5 process-orchestration-layer  (effort: M)
Package proposed `com.sot.exec` → normalised `de.jklein.sot.process` (+ `runner/` for the typed invocation builders). One `@ApplicationScoped ProcessRunner` wraps `ProcessBuilder`, taking a typed `ProcessSpec` (executable, args, env, workingDir, StdinSource, timeout, failOnNonZero, interactive) → `ProcessResult(exitCode, elapsed, timedOut)`. Two virtual-thread drainers avoid pipe-buffer deadlock, emitting `OutputLine` to a `ProgressSink`; `TeeSink` fans to UI + append-only log (replaces `run_with_logging`/`tee`). Secrets NEVER touch argv: `SecretMaterializer` holds a `char[]` `Secret` and passes it via 0600 temp file / scrubbed env / stdin. Typed invocation records (`AnsiblePlaybookInvocation`, `AnsibleVaultInvocation`, `TerraformInvocation`, `DockerInvocation`) each build the arg list in ONE `toProcessSpec()`. `GitService.gitSync(GitSyncSpec(dir,url,branch,SyncMode))` with `PULL` vs `RESET_HARD` (--force-gated) collapses 4 git-sync sites (R6). `WorkspaceManager` extracts embedded assets to a 0700 hashed work dir; interactive tools use `inheritIO()`.
- ProcessRunner — CDI-bean — ProcessBuilder facade; ProcessSpec→ProcessResult; concurrent draining, timeout, exit policy
- ProcessSpec — record — immutable invocation descriptor
- ProcessResult — record — exitCode, elapsed, timedOut, diagnostic tail
- ProcessExecutionException — class — thrown on non-zero/timeout with redacted command line
- ProgressSink — interface — seam to progress UI; TeeSink also appends to log file
- Secret — class — char[]-backed AutoCloseable holder with clear(); never toString/log
- SecretMaterializer — CDI-bean — passes secrets via 0600 temp file / env / stdin, never argv; shred in finally
- GitService — CDI-bean — single gitSync(GitSyncSpec) + ensureTool preflight
- GitSyncSpec — record — dir/url/branch/SyncMode{PULL,RESET_HARD}
- AnsiblePlaybookInvocation / AnsibleVaultInvocation / TerraformInvocation / DockerInvocation — record — typed options → single toProcessSpec() arg builder
- WorkspaceManager — CDI-bean — extracts embedded assets to 0700 hashed work dir (idempotent, content-hash)
- ToolPreflight — CDI-bean — resolves+validates git/ansible/terraform/docker on PATH once

### 1.6 bootstrap-installer-native-packaging  (effort: L)
Package proposed `io.sot.bootstrap` → normalised `de.jklein.sot.bootstrap`. Two-tier install: a ~50-line `install.sh` (uname os/arch → download `sot-<os>-<arch>` + `.sha256` from pinned Release → verify → `install -m755` to `/usr/local/bin/sot`) and the in-binary `sot bootstrap` / `sot self-update`. Bootstrap runs a typed task pipeline: `BootstrapTask` interface (`id()`, `critical()`, `TaskResult run(ctx)`) implemented by CDI beans (Preflight, MaterializeAssets, DirectoryLayout, DependencyInstall, VaultReference, Finalize), injected `@All`; `TaskRunner` aggregates `TaskResult`s into a `BootstrapReport` whose footer + exit code reflect ACTUAL outcomes (kills the "always prints success" lie). One `InstallLayout` record derives every path from a single `rootDir` (default `/opt/sot`) — no self-clone, no CLI-file sed-patch. `sot self-update`: `GitHubReleaseClient` (JDK HttpClient) → `ChecksumVerifier` (SHA-256) → `BinaryUpdater` writes sibling temp, verifies, `Files.move(ATOMIC_MOVE)` over itself, re-execs (replaces update.sh's unguarded `git reset --hard`).
- install.sh — resource — thin platform-detecting downloader (only remaining shell)
- BootstrapCommand — @Command — sot bootstrap; typed options, builds ctx, runs TaskRunner, sets exit code
- SelfUpdateCommand — @Command — sot self-update; GitHubReleaseClient→ChecksumVerifier→BinaryUpdater + confirm gate
- BootstrapTask — interface — id()/critical()/TaskResult run(ctx)
- TaskRunner — CDI-bean — @All List<BootstrapTask>, runs in order, aggregates BootstrapReport
- TaskResult — record — id, Status(PASS/FAIL/SKIP), Duration, message, Optional<Throwable>
- BootstrapReport — record — aggregate; computes overall success + exit code
- InstallLayout — record — single-source path model from one rootDir
- AssetExtractor — CDI-bean — materialises embedded assets driven by build-generated assets/manifest.txt
- ProcessRunner — CDI-bean — single ProcessBuilder wrapper for all subprocess calls (shared w/ §1.5)
- DependencyInstaller — interface — per-tool strategy (Sdkman/Docker/Ansible), CDI-discovered, extensible
- GitHubReleaseClient — CDI-bean — JDK HttpClient querying Releases API for os/arch asset+checksum URLs
- ChecksumVerifier — CDI-bean — SHA-256 MessageDigest verification
- BinaryUpdater — CDI-bean — resolves real path, downloads temp, verifies, atomic-move, re-exec
- BuildInfo — config — build-time-stamped version/commit for update comparison

### 1.7 security-vault-layer  (effort: L)
Package proposed `de.sot.security.vault` → normalised `de.jklein.sot.vault`. The secret NEVER becomes a `String`: it lives only in `Secret`, a final AutoCloseable over `char[]`/`byte[]` whose `close()` zero-fills and `toString()` returns `"****"` — no_log becomes a type property. `VaultPasswordSource` is a sealed interface — `Interactive` (`console.readPassword()`), `PasswordFile(Path)` (0600 root-owned, referenced by path in config), `EnvVar(SOT_VAULT_PASSWORD)`; `SecretResolver` picks highest-priority source and fails loud when none in non-interactive runs. Master secret never from argv/config.yaml. `TransientPasswordFile` materialises a Secret into a tmpfs dir (`XDG_RUNTIME_DIR`→`/dev/shm`, tmpfs-verified else fail) with mode-at-O_CREAT 0600 + SecureRandom name (kills epoch-name symlink race); `close()` overwrites+unlinks. `PosixGuards` centralises NOFOLLOW opens / 0700 dirs / root-ownership asserts. `AnsibleVaultRunner` wraps ProcessBuilder for encrypt/view/rekey (password via 0600 file or `/dev/stdin`, never argv); `edit` uses `Redirect.INHERIT`. `SecretGenerator` (SecureRandom) replaces Jinja `lookup('password')`; `VaultTemplateRenderer` uses a type-safe `@CheckedTemplate` Qute `secrets.yml`. `VaultService` owns init/view/edit/rekey/read — view+rekey now real.
- Secret — class — final AutoCloseable char[]/byte[] carrier; zero-fills, masks toString; only in-memory secret carrier
- VaultPasswordSource — interface — sealed source (Interactive/PasswordFile(0600)/EnvVar); never argv/config
- SecretResolver — CDI-bean — resolves highest-priority source to a Secret; fails loud when none non-interactively
- TransientPasswordFile — class — AutoCloseable tmpfs 0600 file, SecureRandom name, overwrite+unlink on close
- PosixGuards — class — atomic 0600/0700 creation, NOFOLLOW opens, root-ownership + tmpfs assertions
- AnsibleVaultRunner — CDI-bean — ProcessBuilder wrapper; password via file/stdin, inherits TTY for edit, never logs
- SecretGenerator — CDI-bean — SecureRandom secret generation replacing Jinja lookup('password')
- VaultTemplateRenderer — CDI-bean — renders type-safe Qute vault template into transient file
- VaultSecrets — record — typed decrypted vault; fail-loud accessors, no weak defaults, never logged
- VaultService — CDI-bean — facade owning init/view/edit/rekey/read lifecycle
- VaultCommand — @Command — picocli parent (Init/View/Edit/Rekey) injecting VaultService
- vault template (secrets.yml) — resource — @CheckedTemplate Qute asset, replaces vault_template.j2

### 1.8 testing-strategy  (effort: L)
Tests in `src/test/java/de/jklein/sot/...` mirroring production, + `src/test/resources` fixtures. THREE tiers. **Tier 1** fast JVM component tests (`@QuarkusTest`): real CDI wiring, the single external seam `ProcessRunner` (interface) is swapped — `@InjectMock` (quarkus-junit5-mockito) or `RecordingProcessRunner` (`@Alternative`, test-scope) capturing ordered `ProcessInvocation(argv,env,stdin,cwd)`; no ansible/git/docker ever runs. **Tier 2** CLI e2e via `@QuarkusMainTest` → `QuarkusMainLauncher.launch(args)` → `LaunchResult`, asserting the whole command tree / exit codes / help. **Tier 3** native smoke: same class subclassed `@QuarkusMainIntegrationTest` (failsafe, `-Dnative`) black-box; since Mockito can't inject, native tests use `FakeToolPathResource` (temp bin of thin fake tools on PATH). Signature tests: `ConfigRoundtripTest` (jqwik `load(save(cfg))==cfg` + golden-file) replaces 4 parsers; `VaultBehaviorTest` asserts no secret on argv, 0600 RAM file, gone-after; `ExtensionManagerTest`, `PathGuardTest`, `DoctorServiceTest`, `CompletionTest` close Bash gaps. AssertJ + JaCoCo per-package gate in CI; `%test` props point install-root/PATH at `@TempDir`.
- ProcessRunner — interface — single mockable seam over ProcessBuilder
- RecordingProcessRunner — CDI-bean — @Alternative test double recording ordered ProcessInvocation
- CliMainTest — class — @QuarkusMainTest driving QuarkusMainLauncher.launch → LaunchResult
- NativeSmokeIT — class — @QuarkusMainIntegrationTest against the built native binary
- FakeToolPathResource — resource — @QuarkusTestResource prepending fake ansible/vault/git/docker to PATH
- ConfigRoundtripTest — class — jqwik property roundtrip + golden-file over the one SotConfig record
- VaultBehaviorTest — class — behavioural: no secret on argv, 0600 RAM file via PosixFilePermissions, gone after
- ExtensionManagerTest — class — unified registry over LocalDir + GitRepo providers + enable/disable roundtrip
- PathGuardTest — class — safe-delete denylist (/, /usr, empty, min-depth) + fail-closed guards
- DoctorServiceTest — class — diagnostics over @InjectMock ProcessRunner (tool present/absent)
- TestProcessProfile — config — %test props + QuarkusTestProfile pointing paths at @TempDir

### 1.9 ci-cd-release  (effort: L)
Four hand-rolled Bash-CI workflows collapse into 3 declarative Maven-owned workflows + JReleaser; the build tool (not a dir glob) defines what is compiled/tested/scanned, so drift is impossible. `ci.yml` (PR/push): `setup-graalvm@v1` (Mandrel/GraalVM 21 pinned) → `./mvnw -B verify` (Surefire + Failsafe @QuarkusTest, Spotless google-java-format, JaCoCo) → SonarCloud Quality Gate as a REQUIRED check (no continue-on-error) → shellcheck+shfmt on the ONE `install.sh` → one `linux-amd64` native smoke job (`SOT version`, config round-trip, `doctor --dry-run`, `generate-completion`). `native-build.yml` (reusable `workflow_call`): matrix over `ubuntu-24.04`, `ubuntu-24.04-arm`, `macos-13`, `macos-14` (no QEMU); Linux uses `--static --libc=musl`. `release.yml` (tag `v*`): calls native-build, then `jreleaser-maven-plugin` assemble+release → per-platform `.tar.gz`/`.zip`, `checksums_sha256.txt`, Syft SBOM, cosign signatures on GitHub Releases; `install.sh` verifies checksum + cosign before extracting. Gates FAIL the build (no `|| true`), correctness proven by executing the binary.
- .github/workflows/ci.yml — config — PR/push gate: mvnw verify, Spotless, JaCoCo, Sonar Quality Gate, install.sh lint, linux-amd64 native smoke
- .github/workflows/native-build.yml — config — reusable matrix over 4 native runners, per-arch binary + smoke + artifact
- .github/workflows/release.yml — config — tag v*: native-build → JReleaser assemble+release (binaries/checksums/SBOM/cosign)
- jreleaser.yml — config — per-platform archive + checksum + Syft SBOM + cosign + GitHub Releases publisher
- install.sh — resource — detect os/arch, download tarball, verify checksum+cosign, extract, symlink
- .pre-commit-config.yaml — config — Spotless, shellcheck/shfmt scoped to install.sh, yamllint, ansible-lint, gitleaks
- sonar-project + pom plugins — config — Spotless/JaCoCo/Sonar/JReleaser; build tool defines scanned set

---

## 2. Consolidated Package Tree

```
de.jklein.sot/                            root package (Maven groupId de.jklein.sot, artifactId sot)
├── cli/                                  Picocli command tree — the single dispatch surface (§1.2)
│   ├── SotCommand (SotCli)               @TopCommand root; declares subcommand tree + inherited globals
│   ├── Main                              @QuarkusMain; AliasExpander pre-parse + CommandLine.execute
│   ├── BootstrapCommand                  `sot bootstrap` → bootstrap.BootstrapService/TaskRunner
│   ├── SelfUpdateCommand                 `sot self-update` → bootstrap.BinaryUpdater
│   ├── DoctorCommand                     `sot doctor [--fix]` → doctor.DoctorService
│   ├── VaultCommand (+Init/View/Edit/Rekey) `sot vault …` → vault.VaultService
│   ├── RunnerCommand                     `sot runner <ext> <playbook>` → process/runner invocations
│   ├── ExtensionsCommand (aliases ex)    list/install/remove/sync/run → extension.CapabilityService
│   ├── PluginsCommand                    list/info/enable/disable → same CapabilityService
│   ├── UpdateCommand / DeleteCommand     maintenance verbs (typed @Option flags)
│   ├── InteractiveCommand                numbered menu built from live CommandSpec
│   ├── SotVersionProvider                IVersionProvider (build-time version + git commit)
│   ├── AliasExpander                     typed combo-alias map (@f→doctor --fix), pre-parse
│   ├── AliasCheatSheetRenderer           IHelpSectionRenderer (alias footer from spec)
│   ├── ConsoleService / ProgressReporter ANSI/color + progress abstraction (TTY/--no-color)
│   └── SotExitCode                       typed exit codes via setExitCodeExceptionMapper
├── config/                               ONE canonical typed config schema (§1.3)
│   ├── SotConfig                         root record aggregate + Map<String,ExtensionConfig>
│   ├── SystemConfig/SshConfig/LoggingConfig/PathsConfig/ToolsConfig/AnsibleConfig/RunnerConfig  typed sections
│   ├── VaultConfig                       vault settings WITHOUT secret (Path secretRef only)
│   ├── ExtensionConfig                   uniform per-extension shape (aat/tid/custom)
│   ├── RemoteCapabilityDef               typed remote def (name/repoUrl/branch/dir/runner)  [extension-consumed]
│   ├── GeneratedValue (enum)             __GENERATE_*__ sentinels + ordered derivation
│   ├── HostContext                       host facts (hostname, SecureRandom, root) for derivation
│   ├── YamlConfigCodec                   single YAML read/bind/serialize path
│   ├── ConfigMerger                      deep JsonNode merge of default + overrides
│   ├── PlaceholderResolver               resolves sentinels topologically → new record
│   ├── ConfigValidator                   Hibernate-Validator + hard gate on leftover placeholders
│   ├── SecretStore                       reads/writes vault master secret to 0600 root file
│   └── ConfigService                     single load/get/set/save facade
├── extension/                            unified Capability model (proposed pkg `capability`) (§1.4)
│   ├── CapabilityProvider (interface)    SPI: discover/materialize/remove/sync/mutable
│   ├── LocalDirectoryProvider            @Identifier("local"); walks modules/*/module.yml
│   ├── RemoteGitProvider                 @Identifier("remote-git"); RemoteCapabilityDef → GitService
│   ├── CapabilityRegistry                @All List<CapabilityProvider> → one Map<String,Capability>
│   ├── CapabilityService                 single lifecycle owner (list/info/install/remove/enable/disable/sync/run)
│   ├── ExtensionManifest                 typed model of module.yml (one schema)
│   ├── Capability                        runtime aggregate (manifest+origin+path+state+provider)
│   ├── CapabilityType (enum)             TOOL|SERVICE|RUNNER
│   ├── CapabilityStateStore              typed round-trip persistence → capabilities.yml
│   ├── ManifestParser                    ObjectMapper(YAMLFactory) parse+validate at discovery
│   └── SafeFsRemover                     absolute+min-depth+denylist guarded removal
├── vault/                                secret-safe ansible-vault layer (proposed pkg `security.vault`) (§1.7)
│   ├── Secret                            final AutoCloseable char[]/byte[]; zero-fill + mask  [SHARED w/ process]
│   ├── VaultPasswordSource (sealed)      Interactive / PasswordFile(0600) / EnvVar
│   ├── SecretResolver                    highest-priority source → Secret; fail-loud
│   ├── TransientPasswordFile             tmpfs 0600 file, SecureRandom name, overwrite+unlink
│   ├── PosixGuards                       NOFOLLOW opens, 0600/0700, root-ownership + tmpfs asserts
│   ├── AnsibleVaultRunner                ProcessBuilder for encrypt/view/rekey; edit via inheritIO
│   ├── SecretGenerator                   SecureRandom generation (replaces Jinja lookup)
│   ├── VaultTemplateRenderer             @CheckedTemplate Qute → transient file
│   ├── VaultSecrets                      typed decrypted vault (fail-loud, never logged)
│   └── VaultService                      facade owning init/view/edit/rekey/read
├── process/                              ProcessBuilder exec engine (proposed pkg `exec`) (§1.5)
│   ├── ProcessRunner (interface)         single mockable exec seam  [testing requires interface]
│   ├── ProcessRunnerImpl                 @ApplicationScoped concurrent-draining implementation
│   ├── ProcessSpec / ProcessResult       typed invocation descriptor + result
│   ├── ProcessExecutionException         non-zero/timeout with redacted command line
│   ├── ProgressSink (interface) / TeeSink UI seam + append-only log (replaces run_with_logging)
│   ├── SecretMaterializer                secrets via 0600 file / env / stdin, never argv
│   ├── GitService / GitSyncSpec          single gitSync(PULL|RESET_HARD) + ensureTool
│   ├── WorkspaceManager                  extract embedded assets → 0700 hashed work dir
│   └── ToolPreflight                     resolve+validate git/ansible/terraform/docker on PATH
├── runner/                               typed external-tool invocation builders (§1.5 co-located; split per foundation tree)
│   ├── AnsiblePlaybookInvocation         → single toProcessSpec()
│   ├── AnsibleVaultInvocation            → wires --vault-password-file to SecretMaterializer
│   ├── TerraformInvocation               → terraform -chdir/action/var-file
│   └── DockerInvocation                  → docker arg builder
├── bootstrap/                            in-binary bootstrap + self-update (proposed pkg `io.sot.bootstrap`) (§1.6)
│   ├── BootstrapService / TaskRunner     @All List<BootstrapTask>, aggregates BootstrapReport
│   ├── BootstrapTask (interface)         id()/critical()/TaskResult run(ctx)
│   ├── PreflightTask / MaterializeAssetsTask / DirectoryLayoutTask / DependencyInstallTask / VaultReferenceTask / FinalizeTask  task beans
│   ├── TaskResult / BootstrapReport      honest per-task + aggregate outcome (drives exit code)
│   ├── InstallLayout                     single-source path model from one rootDir
│   ├── DependencyInstaller (interface)   Sdkman/Docker/Ansible install strategies
│   ├── GitHubReleaseClient               JDK HttpClient → Releases API
│   ├── ChecksumVerifier                  SHA-256 MessageDigest
│   ├── BinaryUpdater                     atomic self-replace + re-exec
│   └── BuildInfo                         build-time version/commit stamp
├── doctor/                               diagnostics (§1.2 DoctorCommand backing)
│   └── DoctorService                     tool/config/path preflight findings (over ProcessRunner)
└── runtime/                              cross-cutting foundation skeleton (§1.1)
    ├── YamlMapperProducer                @Produces the ONE shared Jackson YAMLMapper
    ├── SotPaths                          one canonical layout from $SOT_HOME
    ├── AssetExtractor                    embedded assets → writable runtime dir (manifest-driven)
    └── ReflectionConfig                  @RegisterForReflection(all records) + @RegisterResources

src/main/resources/                       embedded assets + runtime config
├── application.properties                native resource includes, add-all-charsets, Mandrel image, banner off
├── config/default_config.yml             the ONE canonical nested config template
├── templates/vault/secrets.yml           @CheckedTemplate Qute vault template
├── ansible/**                            playbooks/roles/inventory (embedded, extracted at runtime)
├── docker/**                             Dockerfiles/compose templates (embedded)
├── modules/**/module.yml                 bundled capability manifests
└── assets/manifest.txt                   build-generated list AssetExtractor iterates (native can't Files.walk)

build & CI (repo root)
├── pom.xml                               single-module Maven; quarkus-bom 3.37+, native profile, JReleaser/Spotless/JaCoCo/Sonar plugins
├── mvnw / .mvn/wrapper                   pinned Maven wrapper
├── install.sh                            THE ONLY remaining shell: detect os/arch, download+verify(checksum+cosign), install -m755
├── jreleaser.yml                         per-platform archive + checksum + SBOM + cosign + Releases publisher
├── .pre-commit-config.yaml               Spotless, shellcheck/shfmt(install.sh), yamllint, ansible-lint, gitleaks
└── .github/workflows/{ci,native-build,release}.yml   Maven-owned gates + native matrix + tagged release
```

---

## 3. Full Quarkus Extension / Dependency List

### Runtime
- **io.quarkus:quarkus-picocli** — CLI command tree, @QuarkusMain/PicocliRunner, AutoComplete.GenerateCompletion, @QuarkusMainTest infra
- **io.quarkus:quarkus-arc** — CDI container; build-time `@All List<…>` bean wiring (providers, tasks) — no runtime scanning
- **io.quarkus:quarkus-jackson** — JSON/YAML ObjectMapper + build-time ObjectMapperCustomizer
- **com.fasterxml.jackson.dataformat:jackson-dataformat-yaml** — YAML backend (pulls SnakeYAML) for config, module.yml, decrypted vault YAML
- **io.quarkus:quarkus-hibernate-validator** — Bean Validation on config records (@Min/@Max port, @Pattern names)
- **io.quarkus:quarkus-qute** — type-safe @CheckedTemplate for the vault `secrets.yml` template (no runtime reflection)
- (io.smallrye.common `@Identifier` for named providers ships with Arc — build-time processed)

### Test
- **io.quarkus:quarkus-junit5** — @QuarkusTest / @QuarkusMainTest / @QuarkusMainIntegrationTest
- **io.quarkus:quarkus-junit5-mockito** — @InjectMock ProcessRunner
- **io.quarkus:quarkus-jacoco** — per-package coverage gate
- **org.assertj:assertj-core** — assertions
- **net.jqwik:jqwik** — property-based config round-trip generators

### Build / release plugins & actions (not Quarkus extensions)
- **io.quarkus:quarkus-maven-plugin** — build + native packaging
- **org.jreleaser:jreleaser-maven-plugin** — per-platform archives, checksums, SBOM, cosign, Releases
- **com.diffplug.spotless:spotless-maven-plugin** — google-java-format
- **org.jacoco:jacoco-maven-plugin** — coverage thresholds
- **org.sonarsource.scanner.maven:sonar-maven-plugin** — SonarCloud Quality Gate
- **graalvm/setup-graalvm@v1** (Mandrel/GraalVM CE 21, pinned) · **anchore/sbom-action** (Syft) · **sigstore/cosign**

---

## 4. Capability Mapping: Bash → Java

Legend for the last column: **[S]** = dissolves *structurally* (the Java design makes the finding impossible by construction); **[C]** = still needs *deliberate design care* (a real risk survives and is only mitigated, not eliminated — see §5/§6).

| Bash file / subsystem | Replacing Java component(s) | Root cause / theme dissolved |
|---|---|---|
| `bin/sot` (path bootstrap, CLI_METADATA_ARGS, dispatch case, resolve_command_path, run_interactive_mode) | `cli.Main` + `SotCommand` tree + constructor-injected services | **R3** positional argv contract; **Theme A** dual dispatch (81-82) — [S] |
| `lib/cli/registry.sh` (register_command, categorized/detail help, interactive menu, completion gens) | `SotCommand` subcommand tree + `AliasCheatSheetRenderer` + `InteractiveCommand` | **Theme A/I** registry-vs-fs duality; help drift (84,124); empty-path plugin cmds (83) — [S] |
| `lib/cli/aliases.sh` | picocli `@Command(aliases=…)` + `AliasExpander` | **Theme F** dead alias `s`→setup 127-exit (122); dead/multi-word aliases (134/135) — [S] |
| `lib/cli/progress.sh`, `lib/core/colors.sh` + 6 copy-pasted ANSI blocks | `cli.ConsoleService` / `ProgressReporter` (one compiled binary) | **R6** duplicated color; **Theme E** — [S] |
| `completions/*.{bash,zsh}` | picocli `AutoComplete.GenerateCompletion` (spec-derived) | **R7 / Theme I** completion triplication + drift (175) — [S] |
| `lib/core/yaml_parser.sh`, `parse_plugin_yaml`, `config_defaults` inline regex, `config/default_config{,_v2}.yml` | `config.YamlConfigCodec` + `runtime.YamlMapperProducer` + one `default_config.yml` + `SotConfig` records | **R1** 4 parsers / schema split; **Theme D** flat-vs-nested; **Theme G** #-truncation, xargs corruption; **Theme H** PATH/IFS key injection — [S] |
| `lib/core/bootstrap/config_defaults.sh` (generate_dynamic_defaults) | `config.PlaceholderResolver` + `GeneratedValue` + `ConfigValidator` gate | **Theme F** `__GENERATE_SCRIPTS_DIR__` leaks to disk (130) — [S] |
| `lib/core/bootstrap/config_writer.sh`, `sed`, `save_plugin_state`, `config/overrides/` | `config.ConfigService.save` + `ConfigMerger` | **Theme D** 3 mutation paths + unimplemented overrides — [S] |
| `lib/plugins/manager.sh` + `lib/extensions/manager.sh` + `commands/extensions.sh` (3 managers, 4 terms) | `extension.CapabilityRegistry` + `CapabilityService` + `CapabilityProvider` strategies | **R2 / Theme B** four terms, three disjoint subsystems (89-92) — [S] |
| `modules/*/module.yml`, `parse_plugin_yaml` (4th parser), PLUGIN_DEPENDENCIES | `extension.ExtensionManifest` + `ManifestParser`; topological dep resolution | **Theme B** schema-vs-parser incoherence (89); ignored deps (90); type taxonomies (91) — [S] |
| `_update_config_value` / `save_plugin_state` (never persists) | `extension.CapabilityStateStore` (typed round-trip) | **Theme B/F** persistence lie (126,132) — [S] |
| `commands/vault.sh`, `modules/ansible/roles/{vault,read_vault_parameter}`, `bootstrap/vault_template.j2` | `vault.VaultService` + `AnsibleVaultRunner` + `Secret` + `TransientPasswordFile` + `VaultTemplateRenderer` + `VaultSecrets` | **R5 / Theme H** secret on argv (158), plaintext in config (157), persistent vault_pass.txt (159), debug dump no no_log (161), weak default creds (167), unimplemented view/rekey (129/210) — [S]; symlink race (165), tmpfs guarantee, secure-delete — [C] |
| `config/load_config.yml` vault wiring + config-merge/derive | `config.SecretStore` (0600 secretRef) + `PlaceholderResolver` | **R5/Theme H** secret out of YAML — [S] |
| `commands/runner.sh` (ansible-playbook/terraform, run_with_logging tee, sync_repo), `modules/ansible/commands/trigger.sh` | `process.ProcessRunner` + `runner.*Invocation` records + `TeeSink` + `ToolPreflight` | **R3/R6** positional argv + duplicated arg-build; scattered `command -v` — [S] |
| `bootstrap/init.sh`/`tasks.sh` git clone, `lib/extensions/manager.sh` fetch+pull, `update.sh` fetch+reset --hard+clean | `process.GitService.gitSync(GitSyncSpec, SyncMode PULL/RESET_HARD)` | **R6** 4 divergent git-sync sites; **Theme G** unguarded destructive reset (145) — [S]; RESET_HARD data-loss — [C] |
| `modules/docker/install.sh` mktemp extraction | `process.WorkspaceManager` / `runtime.AssetExtractor` (0700 hashed dir) | native asset extraction; TOCTOU-safe temp — [S] |
| `bootstrap/init.sh` curl\|bash self-clone + re-exec + re-clone | `install.sh` (thin) + prebuilt native binary + `bootstrap.InstallLayout` | **R4** two roots (/opt/SOT vs /etc/DevOpsToolkit vs /opt/AAT), **Theme C** self-clone/CLI-edit/SETUP_DIR (95-99) — [S]; install-root default disagreement — [C] |
| `lib/core/bootstrap/{tasks,runner,args_parser}.sh` | `bootstrap.BootstrapTask` beans + `TaskRunner` + `BootstrapReport` | **Theme F** always-prints-success lie (149); unparsed $1/$2 options (128) — [S] |
| `bootstrap/dependencies.sh` (sdkman/docker/ansible) | `bootstrap.DependencyInstaller` strategies (CDI) | **Theme F** silently-dropped -tools tokens (136,138) — [S] |
| `commands/maintenance/update.sh` | `bootstrap.SelfUpdateCommand` + `BinaryUpdater` + `ChecksumVerifier` + `GitHubReleaseClient` | **Theme G/H** unguarded reset (146); unverified update (162) — [S]; cross-device atomic-move, TLS/CA — [C] |
| `commands/maintenance/delete.sh` (safe delete, create_vault_backup) | `extension.SafeFsRemover` + `PathGuardTest` denylist; vault backups never serialise Secret | **R5/Theme H** rm -rf on config paths + sed injection (147,163,168); secret in /tmp BACKUP_INFO.txt (160) — [S] |
| `lib/init.sh` source loader / double-sourcing, SOT_ROOT probing | `runtime.SotPaths` + Quarkus Arc bean graph | **R4 / Theme E** library load model, double-source, SCRIPT_ROOT drift (117) — [S] |
| `modules/ansible/**`, templates, docker (loose tree) | `src/main/resources/**` + `AssetExtractor` (+ `assets/manifest.txt`) | asset embedding for native — [S]; manifest completeness — [C] |
| `tests/{run-all,setup-env,unit/*,integration/*}.sh` + mock ansible-vault | `@QuarkusTest` suites + `RecordingProcessRunner` + `FakeToolPathResource` + `CliMainTest` + `ConfigRoundtripTest` + `VaultBehaviorTest` | **Theme K** grep-string tests (integration.sh:56/78), `set -e` counter footgun, zero coverage, bash>=4/macOS 3.2 (201) — [S] |
| `.github/workflows/{test,lint,security,deploy}.yml`, `.pre-commit-config.yaml`, `tests/run-all.sh` 7-suite list | `ci.yml` + `native-build.yml` + `release.yml` + `jreleaser.yml` (+ scoped pre-commit) | **R7** false-green security.yml `\|\| true`, ci/ dir drift; **Theme I** informational-not-gating (175) — [S]; native musl/exec assumption — [C] |
| doctor (untested Bash diagnostics) | `doctor.DoctorService` + `cli.DoctorCommand` + `DoctorServiceTest` | **Theme K** untested doctor gap — [S] |

**Findings summary (of the 88):** The large majority dissolve **structurally [S]** — they were artefacts of Bash's dynamic model (string dispatch, `source` loading, unquoted word-splitting, positional argv, dir-glob CI, per-getter re-parse) and cannot recur in a typed, CDI-wired, single-binary design (R1, R2, R3, R4-layout, R6, R7 and themes A, B, D, E, F, I, J, K are essentially eliminated). A residual set still needs **deliberate design care [C]**, all captured in §5/§6: (1) native-image reflection/resource registration for Jackson+SnakeYAML records; (2) the **static-musl-vs-fork/exec** contradiction; (3) tmpfs guarantee + secure-delete + `/dev/shm` symlink race for secrets on non-Linux/container hosts; (4) legacy-config migration; (5) cross-device atomic self-replace + TLS/CA for self-update; (6) `assets/manifest.txt` completeness. Theme **L** is *not tagged in any layer's `dissolvesFindings`* — no layer claims it (flagged in §7).

---

## 5. Native-Image Constraints (consolidated)

**Reflection registration (Jackson + SnakeYAML)**
- `@RegisterForReflection` on ALL Jackson-mapped records — config (`SotConfig` + all section records), `ExtensionManifest`/`Requirements`/`Dependency`/`RemoteCapabilityDef` + `CapabilityType`, `VaultSecrets`, GitHub-release DTOs. Centralise in `runtime.ReflectionConfig(targets={…})`; records are reflectively constructed by ObjectMapper and fail at runtime with missing-constructor otherwise.
- SnakeYAML backend needs reflective registration (constructor/introspector classes) or restrict to `tree + treeToValue` to minimise surface. Explicit `@RegisterForReflection` guards against dead-code stripping of record accessors. Verify with a native integration test that round-trips a full config (`#`-in-quotes, apostrophes, all sections).
- picocli: `@Command/@Option/@Mixin` auto-registered by quarkus-picocli; but `IVersionProvider`, `IHelpSectionRenderer`, `IExitCodeExceptionMapper`, and `AutoComplete.GenerateCompletion` are reflectively instantiated → `@RegisterForReflection` each.
- Hibernate Validator constraint metadata is registered at build time — annotate record components so the extension picks them up.

**Resource embedding + AssetExtractor**
- `quarkus.native.resources.includes=ansible/**,docker/**,templates/**,config/**,modules/**,assets/manifest.txt` — mandatory or the assets are simply absent from the binary.
- A native binary **cannot exec files from inside the image** and **cannot `Files.walk` the classpath**. `AssetExtractor` therefore iterates a build-generated `assets/manifest.txt` and copies each entry via `getResourceAsStream` to a writable runtime dir (`SotPaths`/`InstallLayout`) BEFORE ProcessBuilder invokes ansible/git/docker. Extraction is idempotent (content-hash / checksum) and 0700; verify every glob resolves post-build.

**No dynamic classloading (closed-world)**
- All CDI beans, the Picocli command tree, `@All List<CapabilityProvider>`, and `@All List<BootstrapTask>` are resolved at **build time** — no runtime classpath scanning, no `Class.forName`. Adding a provider/task = adding a compile-time bean, never dropping a `.sh` at runtime. This is the structural replacement for Bash's `source`/`discover_*` model. Extensions remain **git repos orchestrated via process-exec**, never loaded as Java classes.

**Build-time vs runtime init**
- `$SOT_HOME`/env must be read at **runtime** (`SotPaths` @ApplicationScoped), not captured at build time.
- Build-time-init the `YAMLMapper`/`ObjectMapper` via `@Produces` + customizer; version/commit baked into a generated properties resource (`BuildInfo`), no runtime `git` call.
- `SecureRandom` and security providers must `--initialize-at-run-time` so keys aren't baked into the binary (Quarkus default — verify).

**Charsets & locale**
- `quarkus.native.add-all-charsets=true` + explicit UTF-8 `file.encoding` so German UTF-8 output and non-ASCII vault content encode correctly; assert in the native smoke test.

**Process exec & static-linking (critical)**
- `ProcessBuilder`/`ProcessImpl` uses `posix_spawn` in native with no config. **BUT fully-static (musl) native images cannot fork/exec external processes** — the whole tool shells out to ansible/git/docker, so Linux must be **mostly-static (glibc) or dynamic**, NOT `--static --libc=musl`. (This directly contradicts the bootstrap + ci-cd layers, which both chose `--static --libc=musl` for portability — see §6/§7.) `ToolPreflight`/`doctor` must fail fast when a tool is absent. CI must assert real subprocess exec from the built binary (`FakeToolPathResource`).
- `java.nio` `Files.createTempFile` + `PosixFilePermissions` (0600/0700) work natively on Linux with no reflection — the mechanism for secret files. macOS lacks `/dev/shm` tmpfs (vault `TransientPasswordFile` assumption).

**TLS / self-update**
- JDK `HttpClient` over TLS for release download requires `quarkus.ssl.native=true` (+ https URL handler) and a CA truststore embedded at build time; allow `-Djavax.net.ssl.trustStore` override. SHA-256 `MessageDigest` (SUN provider) is registered by default.
- `@QuarkusMainIntegrationTest` (black-box native) cannot inject Mockito/@Alternative → native tests use `FakeToolPathResource` real fake-tool scripts on PATH.

---

## 6. Risks (consolidated) — top 8

1. **Static-musl vs fork/exec contradiction (architecture-breaking).** Bootstrap + ci-cd chose `--static --libc=musl` Linux binaries; the process layer states musl-static *cannot* fork/exec — and the entire tool shells out to ansible/git/docker. **Mitigation:** build **mostly-static (glibc)** or dynamic Linux images; encode libc in the asset name; CI must assert `ProcessBuilder` exec works in the built native binary before any release. *(Must be resolved before native packaging is finalised.)*
2. **Native-image reflection/resource miss surfaces only at runtime** as a silent empty/half-bound config or missing assets. **Mitigation:** centralise `@RegisterForReflection` in `ReflectionConfig`; a mandatory native `@QuarkusIntegrationTest` that loads `default_config.yml`, parses every real `module.yml`, and runs a runner dry-run — turning a runtime reflection failure into a caught CI failure. Build-time assertion that every `resources.includes` glob + `manifest.txt` entry resolves.
3. **Secret residual exposure.** `char[]` `Secret` can still surface in a heap/GC copy before zeroing; secure-delete is unreliable on CoW/SSD/journaled FS; a 0600 tmpfs file is briefly root-readable. **Mitigation:** confidentiality rests on tmpfs(RAM)+0600+immediate-unlink+SecureRandom-name+O_EXCL/NOFOLLOW (kills the epoch-name symlink race, finding 165); overwrite is best-effort defence-in-depth; try-with-resources bounds lifetime; disable core dumps; accept documented residual risk.
4. **tmpfs absent / not-tmpfs (containers, macOS).** `/dev/shm` may be missing or persistent-disk-backed, silently writing the password to disk. **Mitigation:** `PosixGuards` verifies the dir is a real tmpfs mount and **fails loud** rather than silently persisting; this also gates macOS support (no `/dev/shm`).
5. **Legacy `config.yaml` migration.** Existing files carry dead v1 `integrations` blocks / renamed keys and fail strict binding. **Mitigation:** one-time migration reader (`FAIL_ON_UNKNOWN=false` + `MigrationModule` mapping old→canonical keys) that rewrites to the new schema, then flips to strict; same pattern for legacy flat `<name>_enabled`/`<name>_repo_url` → `RemoteCapabilityDef` and `capabilities.yml`.
6. **Destructive `RESET_HARD` data-loss regression** from Bash `update.sh`. **Mitigation:** `SyncMode.RESET_HARD` requires an explicit `--force` gate; `PULL` is the default; both paths are one audited `GitService` method.
7. **Self-replacing binary fails cross-device / EACCES**, or TLS/CA breaks release download. **Mitigation:** write the temp binary into the *target's own parent directory*, verify checksum + cosign before `Files.move(ATOMIC_MOVE)`, fall back to a clear "run install.sh as root" message on EXDEV/EACCES; embed CA bundle at build time with an override + manual-download fallback.
8. **Long/flaky multi-arch native builds & GraalVM/Mandrel drift** produce non-reproducible binaries. **Mitigation:** PRs run JVM verify + one `linux-amd64` native smoke; the full 4-arch matrix runs only on tag/release (`fail-fast:false` isolates arch failures); pin the exact Mandrel version + `ubi9-mandrel-builder-image` tag; Renovate/Dependabot bumps via a PR that must pass the native gate.

*(Also tracked, lower rank: pipe-buffer deadlock on chatty ansible runs → two virtual-thread drainers; `ansible-vault edit` needs a real TTY → `inheritIO()` only on the interactive path; jqwik generating YAML-unroundtrippable values → constrain generators to validation rules; mocked ProcessRunner drifting from real CLI contracts → an opt-in `@Tag("real-tools")` suite; SonarCloud treated as informational → bind Quality Gate as a required branch-protection check.)*

---

## 7. Open Questions / Decisions the design surfaced

1. **Root package name (must be settled first).** Layers proposed 5 different roots: `de.jklein.sot` (foundation, = Maven groupId), `de.sot` (cli, vault-as `de.sot.security.vault`), `dev.sot` (config, capability), `com.sot` (process/`exec`), `io.sot` (bootstrap). **Decision taken here:** canonicalise on `de.jklein.sot.*` (matches groupId). Every sibling must be re-homed.
2. **"Capability" vs "Extension" naming split.** The extension layer models everything as `Capability*` (CapabilityService/Provider/Registry, package `capability`), but the CLI layer injects `ExtensionService` and the foundation names the package `extension/`. Same for `ExtensionsCommand` vs `CapabilityService`. Needs one vocabulary — pick Capability internally or Extension throughout.
3. **`ProcessRunner`: interface vs concrete bean.** The process layer defines it `@ApplicationScoped` concrete; the testing layer *requires it to be an interface* (for `@InjectMock` and the `@Alternative RecordingProcessRunner`). Resolve as **interface + `ProcessRunnerImpl`** (assumed in the tree above).
4. **Install root default disagreement.** Foundation `SotPaths` default `/opt/SOT`; bootstrap `InstallLayout` default `/opt/sot`; the binary itself installs to `/usr/local/bin/sot`; legacy Bash used `/opt/AAT` + `/etc/DevOpsToolkit`. One canonical `rootDir` + case convention must be chosen (and `SotPaths` vs `InstallLayout` are two overlapping path models to merge into one).
5. **Static vs mostly-static native linking (see Risk #1).** Direct contradiction: process layer says musl-static breaks fork/exec; bootstrap + ci-cd both ship `--static --libc=musl`. Must decide **mostly-static glibc / dynamic** (required for shelling out) vs the portability the others assumed.
6. **Overlapping "single shared" beans to dedupe.** Multiple layers each claim to own the one YAML mapper (`runtime.YamlMapperProducer` vs `config.YamlConfigCodec`/`YamlMapperProducer` vs `extension.ManifestParser`'s own `ObjectMapper(YAMLFactory)`); the one `Secret` type (defined in both vault and process); secret-materialisation (vault `TransientPasswordFile`+`SecretResolver` vs process `SecretMaterializer`); asset extraction (`runtime.AssetExtractor` vs `process.WorkspaceManager` vs `bootstrap.AssetExtractor`); `ProcessRunner` (process vs bootstrap vs vault's direct `AnsibleVaultRunner`). Each must collapse to a single shared implementation.
7. **Self-update mechanism coexistence.** Two update paths exist: in-binary `sot self-update` (bootstrap: HttpClient + atomic swap + re-exec) and `install.sh` re-download. Decide whether both are supported and which is canonical; ci-cd added **cosign signature** verification that the foundation's simpler `shasum`-only `install.sh` lacks — align them.
8. **macOS support is only partially coherent.** Release matrix (foundation/ci-cd) and `install.sh` (uname darwin) target macOS arm64, but (a) native static-linking is Linux-only anyway, and (b) the vault layer's tmpfs secret handling (`/dev/shm`/`XDG_RUNTIME_DIR`) has no macOS equivalent. Define the macOS secret-file strategy or scope macOS out.
9. **Keeping Ansible/Terraform/Docker.** Unanimous and unchanged — all remain external processes shelled out via `ProcessBuilder`, with playbooks/roles embedded as resources; no layer proposed removing Ansible. (Recorded as a settled decision, not an open one.)
10. **`module.yml` schema evolution / backward-compat window.** Extension layer wants `apiVersion` + a warn-not-fail validation window for older manifests lacking newer nested fields; interacts with the config migration reader (Risk #5) — one migration policy should cover both.
11. **Theme L is unaccounted for.** No layer's `dissolvesFindings` references theme **L** (themes A-K are all covered). Either L maps to a subsystem no agent was assigned (candidate: logging/observability or the maintenance/delete surface, only partially covered by `PathGuardTest`/`TeeSink`), or the theme list is off-by-one. Confirm what L is and which component owns it before claiming full 88-finding coverage.
