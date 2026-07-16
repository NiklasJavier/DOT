# SOT — Rewrite-Plan: natives Java-CLI (Quarkus + GraalVM), Nix-Substrat, dynamischer App-Manager

> **Was gebaut wird:** SOT wird komplett von Bash auf ein **natives Java-CLI** umgebaut — **Java 21 · Quarkus 3.37+ · Picocli · GraalVM/Mandrel native-image**, gebaut mit **Gradle** + **Justfile**, ausgeliefert als **Nix-Flake**.
>
> **Vier Säulen:**
> 1. **Dynamischer App-Manager** — ein CLI-App-Selektor, der eigene Anwendungen installiert/updatet und **überwacht** (was ist veraltet), über alle Apps hinweg, ohne Toolneubau.
> 2. **100 % Nix als Substrat** — die CLI installiert Nix und zieht **alle** Abhängigkeiten und Apps über **Nix** (kein apt/brew). Reproduzierbar.
> 3. **Cross-Platform** — nativ auf **Linux + macOS**, **Windows via WSL2 (NixOS-WSL)**.
> 4. **Ein Bootstrap-Befehl pro Plattform** — `curl … /cli/install.sh | bash` (Linux/macOS) bzw. `irm …/cli/install.ps1 | iex` (Windows), von **deiner** Domain.
>
> **Evidenz:** [`refactoring-findings.md`](./refactoring-findings.md) (88 Ist-Befunde = funktionale Spec), [`java-quarkus-design-brief.md`](./java-quarkus-design-brief.md) · [`java-quarkus-appmanager-brief.md`](./java-quarkus-appmanager-brief.md) · [`java-quarkus-nix-substrate-brief.md`](./java-quarkus-nix-substrate-brief.md) (Schicht-Entwürfe). Alter Bash-Plan [`refactoring-plan.md`](./refactoring-plan.md) = **superseded**.

---

## 1. Die vier Kern-Anforderungen → Umsetzung

| # | Anforderung | Umsetzung (Kurz) |
|---|---|---|
| **A** | Ein-Befehl-Install via URL, alle Plattformen | Linux/macOS: `curl -fsSL https://<host>/cli/install.sh \| bash`. Windows: `irm https://<host>/cli/install.ps1 \| iex`. Beide bootstrappen Nix bzw. WSL2+NixOS und `nix profile install` das CLI. → §3 |
| **B** | Dynamischer App-Manager mit Update-Überwachung | Apps = deklarative `app.yml`-Manifeste aus konfigurierbarem Katalog; feste Install-/Version-Strategien; `sot app`-Selektor; `sot app outdated`. Neue App = Manifest, **kein Rebuild**. → §2 |
| **C** | **100 % Nix**, keine apt/brew — Deps & Apps über Nix | `NixService` (einziges Gateway zu `nix`), eine reproduzierbare **Toolchain-Flake** (pinned nixpkgs + `flake.lock`) im dedizierten SOT-Profil; Apps via `nix profile install`. `apt-deb`/`DependencyInstaller` gelöscht. → §4 |
| **D** | Cross-Platform Linux/macOS nativ, Windows via VM | SOT selbst = **Nix-Flake** (4 Systeme), Binary-Cache liefert das vorgebaute native Binary. Windows = **NixOS-WSL** + Windows-`sot.exe`-Shim → `wsl -e sot`. → §5 |

**Der Kniff „tief dynamisch" trotz GraalVM-Closed-World:** GraalVM native lädt keine Java-Klassen zur Laufzeit. Also: die **Menge** der Strategien (nix, nix-flake, docker-compose, git-repo, script) und der Version-Resolver ist fest **einkompiliert**; **welche Apps/Tools** existieren + ihre Config sind **100 % Laufzeit-Daten** (Manifeste aus git/HTTP, Nix-Attribute/Flake-Refs). Dynamik ohne Closed-World-Bruch.

---

## 2. App-Manager (Anforderung B) — jetzt Nix-first

### 2.1 Zwei getrennte Achsen
- **Katalog (WOHER, Laufzeit-Daten):** `CatalogSource` = `git` / `http-index` / `bundled`. Neue App = `app.yml` hinzufügen.
- **Strategie (WIE, einkompiliert):** `InstallStrategy`-Beans nach `AppSourceType`. **Nix-first.**

**`AppSourceType` = `NIX` · `NIX_FLAKE` · `GIT_REPO` · `DOCKER_COMPOSE` · `SCRIPT`** *(neu: NIX/NIX_FLAKE; entfernt: `APT_DEB`, und `GITHUB_RELEASE_BINARY` — eigene Apps fallen unter `NIX_FLAKE`).*

### 2.2 `app.yml` — Nix-Quellen
```yaml
# nixpkgs-Attribut (System-Tool/CLI)
source: { type: nix, attr: opentofu, nixpkgs: github:NixOS/nixpkgs/nixos-24.11, mode: profile }  # mode: profile|build
version: { strategy: nix, constraint: '>=1.7.0 <2.0.0' }        # auf attr .version wenn SemVer
---
# eigene App als Flake (inkl. SOT-Katalog-Apps)
source: { type: nix-flake, flakeRef: github:NiklasJavier/grafana-stack, attr: default, rev: v10.4.0 }
version: { strategy: nix-flake }   # vergleicht installierte locked rev vs. `nix flake metadata --json` .locked.rev
---
# docker-compose-Stack — docker selbst kommt AUS Nix
source: { type: docker-compose, repoUrl: https://github.com/NiklasJavier/monitoring, composeFile: docker-compose.yml }
requires: { tools: [docker] }      # NixToolProvisioner stellt docker via Nix bereit
```

### 2.3 Install & Update über Nix
- Zwei neue `InstallStrategy`-Beans: **`NixpkgsInstallStrategy`** (`NIX`) und **`NixFlakeInstallStrategy`** (`NIX_FLAKE`), beide über `NixProfileManager`.
- **Pro-App-Profil** `{stateRoot}/profiles/<appId>` (eigene Generationen, atomarer Rollback, sauberes Remove); `<profile>/bin/*` → gemeinsames PATH-Dir. `install`=`nix profile install --profile p <installable>`, `update`=`nix profile upgrade`, `remove`=`nix profile remove` + Symlinks/Dir weg. Alles zieht aus dem **Binary-Cache** (Download, kein Compile).
- **Pin/Update:** `NIX_FLAKE` via `flake.lock`; `NIX` via nixpkgs-Rev; EXACT-Pin → eingefrorener Rev in `installed.yml`, RANGE → Rev nur solange `attr.version` in der Constraint bleibt.

### 2.4 Update-Überwachung über Nix
- **`UpdateStrategy` = `NIX` · `NIX_FLAKE` · `GITHUB_RELEASE` · `GIT_TAG` · `DOCKER_IMAGE` · `STATIC` · `SCRIPT`** *(neu NIX/NIX_FLAKE; entfernt APT).*
- **`NixVersionResolver`** liest installierte locked rev aus `nix profile list --json`, Upstream aus `nix flake metadata <ref> --json` (`.locked.rev`) bzw. `nix eval --raw <nixpkgsRef>#<attr>.version` → faltet in `UpdateMonitorService.checkAll()` (Virtual-Thread-Fan-out, `VersionCache` mit TTL/Serve-Stale). Fehler je App → `UNKNOWN`.
- Kein Daemon: `sot bootstrap` legt einen systemd-Timer → `sot app check --quiet --notify`; `sot app outdated`/`status` lesen den Cache offline.

### 2.5 Selektor & Command-Surface
`sot app` (Aliase `apps`/`a`) — bare auf TTY = interaktiver zeilenorientierter Selektor (kein JLine, native-sicher), in einer Pipe = `list`. Verben: `list/search/info/install/update/outdated/status/check/remove/pin/unpin/catalog`. `sot ex` = lebender Filter `role=runner` (AAT/TID). Global: `--json/--yes/--no-color/--catalog/--dry-run`.

---

## 3. Installation: ein Befehl pro Plattform (Anforderung A + D)

Da Nix das Substrat ist, wird **SOT selbst zu einem Nix-Flake-Paket** — `install.sh` installiert Nix und `nix profile install` das CLI (Prebuilt aus dem **Binary-Cache**, kein Compile). Self-Update = `nix profile upgrade`.

```bash
# Linux / macOS
curl -fsSL https://<host>/cli/install.sh | bash
# Ohne Installation ausprobieren (überall wo Nix ist)
nix run github:NiklasJavier/SOT -- app list
# Windows (PowerShell, elevated) → WSL2 + NixOS-WSL + sot-Shim
irm https://<host>/cli/install.ps1 | iex
```

**`install.sh`** (Linux/macOS/WSL — einzige verbleibende Shell):
```bash
set -euo pipefail
FLAKE="github:NiklasJavier/SOT"; CACHE_URL="https://<cache>"; CACHE_KEY="<cache>:BASE64KEY="
command -v nix >/dev/null || {                       # 1. Nix via Determinate-Installer (Multi-User-Daemon, Flakes an)
  curl -fsSL https://install.determinate.systems/nix | sh -s -- install --no-confirm
  . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh; }
mkdir -p "$HOME/.config/nix"                          # 2. Binary-Cache eintragen
grep -q "$CACHE_URL" "$HOME/.config/nix/nix.conf" 2>/dev/null || cat >>"$HOME/.config/nix/nix.conf" <<EOF
experimental-features = nix-command flakes
extra-substituters = $CACHE_URL
extra-trusted-public-keys = $CACHE_KEY
EOF
nix profile install "$FLAKE" --accept-flake-config   # 3. SOT aus Flake+Cache (Download-only)
echo "sot installiert. Nächster Schritt: sot bootstrap"
```

- **Debian-spezifisch:** installiert Nix + `sot` — **kein** apt. Laufzeit-Tools kommen später **über Nix** (`sot bootstrap`). Setzt nur `curl`/`ca-certificates` voraus.
- **Self-Update:** `sot self-update` → `nix profile upgrade sot` (atomar, `nix profile rollback` möglich; kein re-exec/ATOMIC_MOVE mehr).
- **Kein-Cache-Fallback:** ohne erreichbaren Cache würde Nix aus Quelle bauen (langsam) → Cache ist Pflicht (Risiko 1, §11).

Windows-Details (install.ps1, Shim, NixOS-WSL) → §5.3.

---

## 4. Nix als Substrat (Anforderung C)

Ein neues Package **`de.jklein.sot.nix`**. **`NixService`** ist das **einzige** Gateway zu `nix` (über den geteilten `ProcessRunner`, nie `Runtime.exec`):
```java
interface NixService {
  NixEnvironment probe();                 // present, version, flakesEnabled, daemonMode, insideNixOS, system, substituters
  void ensureExperimentalFeatures();      // persistiert 'nix-command flakes'
  NixResult profileInstall(NixProfileRef p, FlakeRef ref);  NixResult profileUpgrade(NixProfileRef p, String nameOrAll);
  NixResult profileRemove(NixProfileRef p, String name);    ProfileList profileList(NixProfileRef p);
  NixResult build(FlakeRef ref);  JsonNode eval(FlakeRef ref, String attr);  FlakeMetadata flakeMetadata(FlakeRef ref);
  void ensureSubstituter(BinaryCache cache);   // substituter + trusted-public-key idempotent
}
```

**Reproduzierbare Toolchain (ersetzt `DependencyInstaller`/apt):**
- **`ToolchainManager`** rendert (Qute) eine SOT-eigene Flake `$SOT_HOME/toolchain/flake.nix` mit `packages.<system>.toolchain = pkgs.buildEnv [ … ]`, **pinned nixpkgs-Input + committed `flake.lock`** = volle Reproduzierbarkeit, installiert als **eine atomare Generation** in ein **dediziertes** Profil `$SOT_HOME/state/profile` (nie das User-Default-Profil).
- **`NixToolchainReconciler`** (von bootstrap **und** doctor genutzt): Soll-Menge = Kern-Tools ∪ ⋃(`requires.tools` aller installierten Apps) → `NixPackageCatalog` (toolId→nixpkgs-Attr + `NixPkgKind`) → Flake neu rendern → `profileUpgrade`. Voll laufzeit-dynamisch, ohne Java-Rebuild.
- **`NixInstaller.ensure()`** = idempotenter Determinate-Installer-Fallback (Multi-User-Daemon), **übersprungen wenn `insideNixOS`** (NixOS-WSL bringt Nix mit).
- **docker-Daemon:** docker-**CLI** = `PROFILE_PKG` (via Nix); **Daemon** = `SYSTEM_SERVICE` → `doctor` delegiert plattformabhängig (NixOS-WSL `virtualisation.docker.enable`, macOS colima/Docker Desktop). Nie einen Daemon ins Profil installieren.
- **`NixDoctorCheck`:** meldet nix present, Flakes an, Cache erreichbar, jedes Tool auf PATH, docker-Socket.
- **Standard-Tool-Mapping:** `git→git`, `ansible→ansible`, `terraform→opentofu` *(Default opentofu, vermeidet BSL/unfree; via `SotConfig.tools` überschreibbar)*, `jq→jq`, `cosign→cosign`, `age→age`, `sops→sops`, `docker-cli→docker-client`, `docker→SYSTEM_SERVICE`.

---

## 5. Cross-Platform-Delivery (Anforderung D)

### 5.1 SOT als Nix-Flake
`flake.nix` im Repo-Root, 4 Systeme (`x86_64-linux, aarch64-linux, x86_64-darwin, aarch64-darwin`). **`packages.<system>.default`** = **`fetchurl`-Wrapper** um das CI-gebaute native Binary (SHA-256-gepinnt), `autoPatchelfHook` (Linux, minimal `buildInputs = [stdenv.cc.cc.lib zlib]`) bzw. `install -Dm755` (darwin). `apps.default` (`nix run`), `devShells.default` (jdk21+gradle+just+mandrel). `nixConfig.extra-substituters` deklariert den Cache → `--accept-flake-config` konfiguriert selbst.

> **Build-Entscheidung:** **fetchurl-Wrapper statt gradle2nix** für v1 — ein hermetischer GraalVM-Native-Build in der Nix-Sandbox ist schwer/brüchig über 4 Systeme und bringt **keinen** UX-Gewinn (der Cache liefert ohnehin Prebuilt). Das CI-Binary ist die getestete Wahrheit; gradle2nix bleibt als späterer `packages.sot-src`-Track.

### 5.2 Binary-Cache
```
# nix.conf (von install.sh/bootstrap geschrieben)
experimental-features = nix-command flakes
extra-substituters = https://<cache>
extra-trusted-public-keys = <cache>:BASE64KEY=
```
CI (`release.yml`): native je System bauen → JReleaser publiziert Assets → SHA-256 → `flake.nix`-Hashes aktualisieren → `nix build .#default` je Runner → **Cache-Push** signierter Store-Paths. `nix profile install` lädt dann Prebuilt.

### 5.3 Windows via WSL2 (NixOS-WSL)
Windows = dünner Bootstrapper + Shim; **alle** echte Logik läuft in **NixOS-WSL** (dort ist Nix nativ, `install.sh` läuft unverändert). Kein Windows-natives GraalVM-Target.

- **`install.ps1`** (reboot-resumable State-Machine via `$env:SOT_RESUME`, `HKCU\…\RunOnce`): **0** Preflight (Build ≥19041, Self-Elevate, Virtualisierung) → **A** WSL2 (`wsl --install --no-distribution`, Reboot) → **B** NixOS-WSL installieren (Tarball `nixos.wsl` von `/cli/` laden + `.sha256` prüfen; `wsl --install --from-file` ab 2.4.4, sonst `wsl --import NixOS <dir> nixos.wsl --version 2`) → **C** `wsl -d NixOS -u root -- bash -lc "curl … /cli/install.sh | bash"` → **D** Shim nach `%LOCALAPPDATA%\Programs\sot\bin`, PATH.
- **Windows-Shim** (`sot.exe`, Rust/Go, code-signiert; `sot.cmd` als Fallback) leitet argv/stdio/Exit-Code an `wsl.exe -d NixOS -e sot …` weiter (ConPTY unter Windows Terminal):
```rust
fn main() { let a: Vec<String> = std::env::args().skip(1).collect();
  let s = std::process::Command::new("wsl.exe").args(["-d","NixOS","-e","sot"]).args(&a).status().unwrap();
  std::process::exit(s.code().unwrap_or(1)); }
```
- **NixOS-WSL-Tarball** bringt `wsl.enable`, `systemd.enable`, `virtualisation.docker.enable`, Cache-Substituter mit (docker läuft **in** WSL, kein Docker Desktop).
- **Java-Berührungspunkte:** nur `runtime.WslEnvironment` (WSL-Erkennung → doctor/notifier/`SotPaths` adaptieren) + `bootstrap.windows.WindowsShimWriter` (CI-Zeit).

### 5.4 Was dein Host unter `https://<host>/cli/` ausliefert
`install.sh` · `install.ps1` · `nixos.wsl` (+`.sha256`) · `sot.exe` · `sot.cmd` · `manifest.json` `{sotVersion, wslMinVersion, distroName, tarballSha256}`. Die Binaries selbst kommen aus dem Nix-Cache (bzw. GitHub Releases als Flake-`fetchurl`-Quelle).

### 5.5 macOS
First-class nativ (Nix auf macOS reif). Secrets ohne tmpfs: `TransientPasswordFile` fällt auf `mkstemp` 0600 unter verschlüsseltem APFS-`$TMPDIR` zurück (`PosixGuards`). Damit ist die frühere „macOS nur JVM/Dev"-Einschränkung **aufgehoben**.

---

## 6. Ziel-Stack

Java 21 · Quarkus 3.37+ · quarkus-picocli · quarkus-jackson (+jackson-yaml) · quarkus-hibernate-validator · quarkus-qute · **Gradle (Groovy DSL)** · **Justfile** · **Mandrel native** (`-H:+StaticExecutableWithDynamicLibC`, mostly-static glibc) · **Nix-Flake** + **Binary-Cache** (attic/Cachix) · JReleaser (Gradle-Plugin) · GitHub Actions (native Matrix + Cache-Push).

```bash
quarkus create cli de.jklein.sot:sot --gradle -x picocli
./gradlew addExtension --extensions='quarkus-jackson,quarkus-hibernate-validator,quarkus-qute'
./gradlew quarkusDev | build | build -Dquarkus.native.enabled=true | check | jreleaserFullRelease
nix build .#default   # Flake realisiert das (Prebuilt-)Binary
```
Justfile: `setup·dev·build·native·test·lint·fmt·run·install-local(nix profile install .#default)·release·clean·nix-bootstrap·toolchain-sync·win-build·win-tarball·win-publish`.

---

## 7. Ziel-Architektur — Package-Baum

```
de.jklein.sot/
├── cli/         SotCommand(@TopCommand)·Main(@QuarkusMain)·{Bootstrap,Doctor,Vault,Runner,SelfUpdate,Delete,Interactive}Command
│               · ConsoleService/ProgressReporter · SotExitCode
│   └── app/     AppCommand(app|apps|a)·AppSelector·AppTableRenderer· App{List,Search,Info,Install,Update,Outdated,Status,Remove,Pin,Unpin,Refresh}Command · AppNameCandidates
├── app/         ★ AppManifest·SourceSpec·AppSourceType{NIX,NIX_FLAKE,GIT_REPO,DOCKER_COMPOSE,SCRIPT}·InstallStrategy
│               · Nixpkgs/NixFlake/DockerCompose/GitRepo/Script-Strategy · NixProfileManager · AppCatalog·CatalogSource
│               · InstalledAppStore·InstalledApp·AppService·AppStatus·SemVer·RunnerSpec
│   └── update/  UpdateMonitorService·VersionResolver·NixVersionResolver·{GitHubRelease,GitTag,DockerImage,Script}Resolver
│               · Version/VersionConstraint·VersionCache·OutdatedReport·UpdateScheduler/UpdateNotifier
├── nix/         ★ NixService·NixEnvironment·ToolchainManager·ToolchainFlakeRenderer·NixToolchainReconciler
│               · NixPackageCatalog·NixPkgKind·NixInstaller·NixBootstrapTask·NixDoctorCheck·BinaryCacheConfig
├── config/      SotConfig + Sektions-Records · CatalogSource-Liste · YamlConfigCodec·ConfigMerger·PlaceholderResolver
│               · ConfigValidator·SecretStore·ConfigService
├── vault/       Secret·VaultPasswordSource(sealed)·SecretResolver·TransientPasswordFile(tmpfs|APFS-mkstemp)·PosixGuards
│               · AnsibleVaultRunner·SecretGenerator·VaultTemplateRenderer·VaultService
├── process/     ProcessRunner(interface)+Impl·ProcessSpec/Result·ProgressSink/TeeSink·SecretMaterializer
│               · GitService/GitSyncSpec·WorkspaceManager·ToolPreflight   (NixService nutzt diesen Runner)
├── runner/      Ansible{Playbook,Vault}Invocation·TerraformInvocation·DockerInvocation
├── bootstrap/   BootstrapTask+Task-Beans(inkl. NixBootstrapTask)·TaskRunner·BootstrapReport·InstallLayout
│               · SelfUpdateCommand(→nix profile upgrade)·BuildInfo · windows/WindowsShimWriter
├── doctor/      DoctorService (+NixDoctorCheck)
└── runtime/     YamlMapperProducer·SotPaths·AssetExtractor·ReflectionConfig·WslEnvironment

src/main/resources/  application.properties·config/default_config.yml·templates/vault/secrets.yml·apps/**/app.yml·assets/manifest.txt
repo-root/           flake.nix·build.gradle·settings.gradle·gradle.properties·gradlew·Justfile
                     · install.sh·dist/windows/{install.ps1,sot.exe,sot.cmd,nixos.wsl}·jreleaser·.github/workflows/{ci,native-build,release}.yml
```

---

## 8. Capability-Mapping (Delta ggü. Bash) — Nix-relevant

| Bash | Java/Nix-Ersatz | Grundursache |
|---|---|---|
| `bootstrap/dependencies.sh`, `DependencyInstaller` (sdkman/docker/ansible via apt/curl) | **`nix.NixToolchainReconciler` + Toolchain-Flake** (nixpkgs pinned) | Anforderung C — apt entfällt [S] |
| App-Source `apt-deb` | **`NIX`/`NIX_FLAKE`-Strategien** | 100 % Nix [S] |
| `bootstrap/init.sh` curl\|bash Selbst-Clone | **`install.sh`: Nix + `nix profile install`** | R4/C, A/C — [S] |
| `commands/maintenance/update.sh` (`git reset --hard`) | `SelfUpdateCommand` → **`nix profile upgrade sot`** (atomar, rollback) | G — [S] |
| — (neu) Windows | **`install.ps1` + NixOS-WSL + `sot.exe`-Shim** | D — neue Fähigkeit [C] |
| **`modules/ansible/roles/*`** (UFW `allow`, Rollenname, hosts-Regex, …) | portierte, **gefixte** Ansible-Assets (bleiben YAML, via Nix-`ansible` ausgeführt) | Thema L (10) — **manuell [L]** ⚠️ |

Der Rest des Mappings (CLI/Config/Vault/Extensions→App-Manager/Tests/CI) wie in den früheren Abschnitten; die 88 Befunde lösen sich mehrheitlich **strukturell [S]** auf, ~8–10 sind zu **härten [C]**, 10 (Thema L) manuell **[L]**.

---

## 9. Native-Image / Nix-Constraints

| Bereich | Was zu tun ist |
|---|---|
| **Binary muss `nix` exec-en ⚠️** | Jeder `NixService`-Call ruft `nix`. Zusammen mit dem App-Manager, der git/docker ruft → **mostly-static glibc** (nicht musl; D1). `autoPatchelfHook` minimal halten (`cc.cc.lib`+`zlib`), sonst mis-patch. CI muss beweisen, dass das **Store-Binary** `nix --version`/`git --version` startet — vor jedem Cache-Push. |
| **Closed-World-Dynamik** | Strategie-/Resolver-Menge einkompiliert (`@All`→`Map<enum,bean>`); welche Apps/Tools = Laufzeit-Daten (Manifeste, nixpkgs-Attr, Flake-Refs). |
| **Reflection** | `@RegisterForReflection` zentral: alle Manifest-/Config-/`NixSourceSpec`/`NixEnvironment`/Report-Records + Nix-JSON-DTOs. |
| **Cache** | Pflicht-Substituter+Key **vor** erster Installation (sonst Compile-from-Source). CI pusht CLI + Toolchain + Katalog-Flakes + pinned nixpkgs-Closure. |
| **Ressourcen/TLS/Charsets** | `resources.includes` (apps/ansible/docker/templates); `quarkus.ssl.native=true` + CA (github/ghcr/dockerhub); `add-all-charsets=true`. |

---

## 10. Offene Entscheidungen (aufgelöst; ⚠️ = bitte bestätigen)

| # | Entscheidung | Festlegung |
|---|---|---|
| D1 ⚠️ | Native-Linking | **mostly-static glibc** — muss `nix`/git/docker fork/exec-en (musl kann das nicht). CI beweist Exec. |
| D2 | Root-Package | `de.jklein.sot` |
| D3 ⚠️ | Install-Root / Nix-Profile | Programm via `nix profile`; SOT-State unter **`$SOT_HOME` = `/opt/sot`** bzw. `$XDG_STATE_HOME`; dediziertes Toolchain-Profil, nie User-Default — **bestätigen** |
| D4 | Extension/Plugin → App | kollabiert in App-Manager; AAT/TID = Apps mit `runner:` |
| D5 ⚠️ | **Binary-Cache: attic (self-hosted) vs Cachix** | **Empfehlung: self-hosted attic auf deiner Domain** (`cache.<domain>`) — passt zu „eigener Host"/100 %-Souveränität; **Cachix** als zero-ops-Schnellstart. **Deine Wahl.** |
| D6 | CLI-Distribution / Self-Update | SOT = Nix-Flake; Install `nix profile install`, Update `nix profile upgrade sot`; **fetchurl-Wrapper** (nicht gradle2nix) für v1 |
| D7 | Nix-Modus | Multi-User-Daemon (Determinate); übersprungen in NixOS-WSL |
| D8 | Tool-Profil-Modell | **eine buildEnv-Toolchain** (pinned nixpkgs + `flake.lock`) im dedizierten Profil; `NixToolProvisioner` routet dadurch |
| D9 | App-Profile | pro-App-Profile (Rollback/Isolation); `nix profile install` default, `mode: build` opt-in |
| D10 | terraform | **opentofu** als Default (BSL/unfree vermeiden), via `SotConfig.tools` überschreibbar |
| D11 | AppSourceType/UpdateStrategy | wie §2 (NIX/NIX_FLAKE rein, APT_DEB/APT + GITHUB_RELEASE_BINARY-App-Source raus) |
| D12 ⚠️ | Windows-Linux-Env | **NixOS-WSL** (100 % Nix); `sot.exe`-Shim primär, `sot.cmd`-Fallback — **bestätigen** |
| D13 | macOS | first-class nativ; Secrets via APFS-`mkstemp` 0600 |
| D14 | Determinate-Installer-Trust | Version pinnen + Checksum in `install.sh`; https-only |
| D15 ⚠️ | Legacy-Migration | `apt-deb`→`nix`-Migrations-Reader + alte `/usr/local/bin/sot`-Erkennung — nötig nur bei **Feld-Installationen** — **bestätigen** |

---

## 11. Migrations-Phasen (Greenfield, „Strangler")

- **P0 — Skelett & Foundation** *(L, D1–D2)* — Gradle/Quarkus/Java-21, Justfile, `sot version` nativ, `runtime.*`, CI-JVM-Verify + **linux-amd64-Native-Smoke, der einen echten Subprozess startet**. Gate: nativ + exec-fähig.
- **P1 — Config-Kern** *(L)* — `SotConfig`-Records, ein YAML-Codec, Validierung, `SecretStore`, `CatalogSource`-Liste. Gate: Roundtrip + native-IT.
- **P2 — Prozess-Engine** *(M)* — `ProcessRunner`, `GitService`, `SecretMaterializer`, `WorkspaceManager`, `ToolPreflight`. Gate: echter `git`-Exec nativ.
- **P3 — ★ Nix-Substrat** *(L, Anf. C)* — `NixService` + `NixEnvironment`, `ToolchainManager`/`Renderer`/`Reconciler`, `NixPackageCatalog`, `NixInstaller`, `NixBootstrapTask`, `NixDoctorCheck`, Cache-Config. Gate: `sot bootstrap` stellt Toolchain (git/ansible/opentofu) rein über Nix bereit; doctor grün.
- **P4 — CLI-Gerüst** *(M)* — Command-Baum, Hilfe/Version/Completion, Exit-Codes. Gate: `@QuarkusMainTest`.
- **P5 — ★ App-Kern (Nix-first)** *(L, Anf. B)* — `AppManifest`/`ManifestParser`, `AppCatalog`, `Nixpkgs`/`NixFlake`/`DockerCompose`/`GitRepo`/`Script`-Strategien, `NixProfileManager`, `AppService`, `InstalledAppStore`. Gate: install/update/remove/persist je Strategie über Test-Katalog + Cache.
- **P6 — ★ Update-Überwachung** *(L, Anf. B)* — `VersionResolver`-SPI + `NixVersionResolver`, `UpdateMonitorService` (Virtual-Threads), `VersionCache`, Pins, Timer/Notifier. Gate: `outdated` korrekt (up-to-date/outdated/pinned/unknown).
- **P7 — ★ App-Selektor & Surface** *(M, Anf. B)* — `AppCommand`-Baum, `AppSelector`, `--json/--yes`, Completion, `ex`/deprecated Forwarder. Gate: e2e, non-TTY→list.
- **P8 — Vault, Bootstrap-Tasks, Runner & Ansible-Assets** *(L, +Thema L)* — `VaultService`/`Secret`/tmpfs|APFS, Task-Pipeline, `RunnerCommand`; **Ansible-Assets fixen** (UFW `deny`, Rollenname, hosts-Regex, Vault-Lifecycle, OS-Abstraktion; via Nix-`ansible`). Gate: `sot bootstrap` gegen Wegwerf-Container; `ansible-lint`; Vault-Roundtrip.
- **P9 — ★ Cross-Platform-Delivery** *(L, Anf. A+D)* — `flake.nix` (4 Systeme, fetchurl-Wrapper), Binary-Cache (attic/Cachix) + CI-Push, `install.sh` (Nix→profile install), `SelfUpdateCommand`, JReleaser-Multi-Arch, macOS-Runner. Gate: `install.sh` installiert `sot` in **frischem Debian-Container** und **auf macOS**; `nix profile upgrade` funktioniert.
- **P10 — ★ Windows/WSL2** *(L, Anf. D)* — `install.ps1` (reboot-resumable), NixOS-WSL-Tarball, `sot.exe`/`sot.cmd`-Shim, `WslEnvironment`. Gate: `irm … | iex` in **frischer Windows-VM** → `sot app` läuft über den Shim.
- **P11 — Parität, Cutover & Legacy** *(M)* — volle Coverage, `apt-deb→nix`/`module.yml→app.yml`/Legacy-Binary-Migration, **88-Befund-Regressions-Checkliste** ([S]/[C]/[L] mit Nachweis), Bash entfernen, README neu. Gate: Checkliste 100 %.

**Kritischer Pfad:** P0 → P1/P2 → **P3 (Nix)** → P4 → **P5 → P6 → P7 (App-Manager)** → **P9 (Delivery)** → P10 (Windows) → P11. P8 parallel ab P3.

---

## 12. Verifikation & Risiken

**Verifikation:** 3 Test-Tiers (`@QuarkusTest` mit gemocktem `ProcessRunner`/`NixService` · `@QuarkusMainTest` · nativer `@QuarkusMainIntegrationTest`). **Native-Gate** beweist Nix-/Tool-Exec aus dem Store-Binary. **Release-Smokes:** `install.sh` in frischem Debian- **und** macOS-Runner; `install.ps1` in Windows-VM. **Paritäts-Checkliste** gegen `refactoring-findings.md`. CI failt hart.

**Top-Risiken:**
1. **Cache-Miss → Compile-from-Source** (bricht Erst-Install-UX). → Pflicht-Substituter+Key vor erster Installation; CI pusht **alles** in den Cache; doctor flaggt unerreichbaren Cache; `ProgressReporter`-Warnung.
2. ⚠️ **Native-Binary kann `nix`/Tools nicht exec-en / `autoPatchelfHook` mis-patch.** → mostly-static glibc; minimale `buildInputs`; CI-Exec-Beweis vor Cache-Push.
3. **Non-trusted-user ehrt `extra-substituters` nicht → stiller Source-Build.** → Determinate macht Installierer zum trusted-user; `install.sh` verifiziert, bietet System-`/etc/nix/nix.conf`; `--accept-flake-config`.
4. **Nix absent / Flakes aus.** → `install.sh` Determinate-Installer; `ToolPreflight`/doctor mit einer klaren Remediation.
5. **Supply-Chain: Determinate `curl|sh` + `nixos.wsl`-Tarball.** → Installer-Version pinnen + Checksum; `nixos.wsl.sha256` + `manifest.json`, hartes Fail bei Mismatch.
6. **`outdated`-Fan-out langsam / Nicht-SemVer-Nix-Versionen.** → Virtual-Threads + `VersionCache` + denormalisierte Rev; Flakes per Rev-Gleichheit, nixpkgs nur bei parsebarem SemVer, sonst `UNKNOWN`.
7. **Windows:** WSL2 fehlt/Virtualisierung aus, Reboot-Resume fragil, SmartScreen blockt `sot.exe`. → Preflight ≥19041+Virt; idempotente Stages + RunOnce; `install.ps1`/`sot.exe` code-signen + `sot.cmd`-Fallback.
8. **Datenverlust/Destruktiv** (`RESET_HARD`, `rm -rf`). → `--force`-Gate; `SafeFsRemover`-Denylist; pro-App-Profil-Remove ist sauber (Generationen).

---

## 13. Aufwand

Für **eine erfahrene Person** grob **~16–20 Wochen** (jetzt inkl. Nix-Substrat P3 ~1.5–2 Wo, Cross-Platform-Delivery P9 ~1.5 Wo, Windows/WSL2 P10 ~1.5–2 Wo zusätzlich zum App-Manager-Kern). Mit 2–3 Personen ab P1 parallelisierbar (Config/Exec/Nix/Vault unabhängig; App-Kern→Update→Selektor seriell; Windows nach Delivery) auf **~9–12 Wochen**. Wichtigster Hebel: **früher End-to-End-Dünnschnitt** — `sot version` nativ → als Flake paketiert → `install.sh` (Nix + `nix profile install`) in einem Debian-Container grün — validiert D1, Cache und den ganzen Delivery-Pfad, bevor der App-Manager gebaut wird.
