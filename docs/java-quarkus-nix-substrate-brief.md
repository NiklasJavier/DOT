# SOT — Nix Substrate & Cross-Platform Delivery: Consolidated Brief

Source: 4 architecture agents — `nix-substrate-and-dependencies`, `app-install-and-update-via-nix`, `cli-as-flake-and-cross-platform`, `windows-wsl-bootstrap`. All four rated effort **L**.

Core thesis (shared across all areas): **Nix becomes the single package substrate.** `bootstrap.DependencyInstaller` (apt/sdkman/docker/ansible) and the `AptDeb`/`APT_DEB` path are DELETED. Every tool, app, and the SOT CLI itself arrive via `nix profile install` from a signed binary cache (download-only, no compile). One Java gateway — `NixService` over the shared `ProcessRunner` — is the only class that shells `nix`.

---

## 1. Per-Area Design

### 1.1 nix-substrate-and-dependencies

A new `de.jklein.sot.nix` package makes Nix the single substrate, DELETING `bootstrap.DependencyInstaller` and the `AptDeb`/`APT_DEB` source path. `NixService` (`@ApplicationScoped`, `NixServiceImpl`) wraps the `nix` CLI through the shared `ProcessRunner` — never `Runtime.exec` — exposing probe/ensure/profile/flake/config verbs. `probe()` returns a `NixEnvironment` record (present, version, flakesEnabled, daemonMode, `insideNixOS` via `/etc/NIXOS`, `system`, substituters). All flake calls pass `--extra-experimental-features "nix-command flakes"`; `ensureExperimentalFeatures()` persists them to `~/.config/nix/nix.conf` idempotently. `ToolchainManager` owns a SOT-generated flake at `$SOT_HOME/toolchain/flake.nix` (Qute-rendered by `ToolchainFlakeRenderer`) whose `packages.<system>.toolchain` is a `pkgs.buildEnv` over the declared tool list with a pinned `nixpkgs` input + committed `flake.lock` = full reproducibility, installed into a DEDICATED profile `--profile $SOT_HOME/state/profile` (never the user default). `NixToolchainReconciler` (bootstrap + doctor) computes DESIRED = core tools ∪ every installed app's `requires.tools` (from `InstalledAppStore`), maps via `NixPackageCatalog` (toolId→nixpkgs attr + `NixPkgKind`), re-renders, and runs `profileInstall`/`profileUpgrade` — 100% runtime-dynamic, no Java rebuild. `NixInstaller.ensure()` is the idempotent Determinate-installer fallback, SKIPPED when `insideNixOS`. `NixBootstrapTask` does ensure-nix → ensure-cache → reconcile; `NixDoctorCheck` reports nix/flakes/cache/tools/docker-daemon. `SYSTEM_SERVICE` tools (docker daemon) can't be profile packages on non-NixOS — doctor delegates (NixOS-WSL `virtualisation.docker.enable`, macOS colima/Docker Desktop).

- `NixService` — interface + `@ApplicationScoped` impl — the one gateway to nix (probe, profile install/upgrade/remove/list, build, eval, flake metadata/update, run, substituter config).
- `NixEnvironment` — record — detected substrate facts; drives skip-when-NixOS and single-vs-multi-user decisions.
- `ToolchainManager` + `ToolchainFlakeRenderer` — `@ApplicationScoped` + Qute template — owns/renders `$SOT_HOME/toolchain/flake.nix` (buildEnv + pinned nixpkgs + flake.lock), installs one atomic profile entry.
- `NixToolchainReconciler` — `@ApplicationScoped` — desired set = core ∪ union(apps' requires.tools); replaces `DependencyInstaller`.
- `NixPackageCatalog` + `NixPackageRef` — `@ApplicationScoped` + record — toolId → nixpkgs attr + `NixPkgKind` (PROFILE_PKG vs SYSTEM_SERVICE); overridable via `SotConfig.tools`.
- `NixInstaller` — `@ApplicationScoped` — idempotent Determinate nix-installer ensure; no-op inside NixOS.
- `NixBootstrapTask` — `BootstrapTask` bean — plugs ensure + cache + reconcile into the TaskRunner pipeline.
- `NixDoctorCheck` — `DoctorService` check — nix/flakes/cache/tools/docker socket.
- `BinaryCacheConfig` + `BinaryCache` — `@ApplicationScoped` + record — idempotently ensures SOT substituter + trusted-public-key.

**Effort: L**

### 1.2 app-install-and-update-via-nix

Nix becomes the PRIMARY app substrate. `AppSourceType` ADDS `NIX` (nixpkgs attribute) + `NIX_FLAKE` (flake installable ref), KEEPS `DOCKER_COMPOSE`/`GIT_REPO`/`SCRIPT`, REMOVES `APT_DEB` (old `AptDebStrategy` + the sdkman/docker/ansible `DependencyInstaller` deleted). Two new `InstallStrategy` beans — `NixpkgsInstallStrategy` (`type()==NIX`) and `NixFlakeInstallStrategy` (`type()==NIX_FLAKE`) — delegate to a shared `NixProfileManager` wrapping `nix` via a thin `NixCli` in `process/`. Default model = a PER-APP profile at `{stateRoot}/profiles/<appId>` (independent generations, atomic rollback, clean removal), then symlinks `<profile>/bin/*` into the sot-managed `{binRoot}` on PATH. `install()` runs `nix profile install --profile {p} <installable>`; NIX uses a locked `github:NixOS/nixpkgs/<pinnedRev>#<attr>`, NIX_FLAKE uses `source.flakeRef` (flake's own `flake.lock` pins transitively). Both honor the owner binary cache. `update()` = `nix profile upgrade`; `remove()` = `nix profile remove` + delete profile dir + bin symlinks. A `nix build .#attr --out-link` (`mode: build`) variant exists but profiles are default. `NixToolProvisioner` provisions system tools (git/docker/ansible/terraform) into ONE shared `system` profile — docker still comes FROM Nix; `DockerComposeStrategy` shells to that nix-provided `docker compose`. Update-monitoring gets `UpdateStrategy.NIX`/`NIX_FLAKE` (drops `APT`). `NixVersionResolver` reads installed locked rev from `nix profile list --json` and upstream from `nix flake metadata <ref> --json` (`.locked.rev`/`.lastModified`) or `nix eval --raw <nixpkgsRef>#<attr>.version`; folds into `UpdateMonitorService.checkAll()` virtual-thread fan-out. EXACT pin ⇒ frozen locked rev in `installed.yml`; RANGE ⇒ upgrade within a nixpkgs branch/rev window.

- `AppSourceType` — enum — ADD NIX + NIX_FLAKE; KEEP GIT_REPO, DOCKER_COMPOSE, SCRIPT; REMOVE APT_DEB. Selects strategy via `@All Map<AppSourceType,InstallStrategy>`.
- `NixpkgsInstallStrategy` — CDI bean (InstallStrategy) — `type()==NIX`; installs locked `github:NixOS/nixpkgs/<rev>#<attr>` into per-app profile.
- `NixFlakeInstallStrategy` — CDI bean (InstallStrategy) — `type()==NIX_FLAKE`; installs flake installable, relies on flake.lock for transitive pinning.
- `NixProfileManager` — class (app/) — shared engine: profile install/upgrade/remove into `{stateRoot}/profiles/<appId>`, generation rollback, bin symlinking, optional `nix build --out-link`.
- `NixCli` — class (process/) — thin typed wrapper over ProcessRunner for the nix binary (build/eval/profile/flake-metadata, `--json`, substituter flags).
- `NixToolProvisioner` — class (bootstrap/ or process/) — replaces DependencyInstaller; installs system tools into one shared `system` profile.
- `UpdateStrategy` — enum — ADD NIX + NIX_FLAKE, REMOVE APT; keeps GITHUB_RELEASE, GIT_TAG, DOCKER_IMAGE, STATIC, SCRIPT.
- `NixVersionResolver` — CDI bean (VersionResolver, app.update/) — reads installed locked rev + resolves upstream; emits `ResolvedVersion(rev as digest)`.
- `NixSourceSpec` / `NixFlakeSourceSpec` — records — `@RegisterForReflection` Jackson slices bound in `resolve()`.

**Effort: L**

### 1.3 cli-as-flake-and-cross-platform

SOT itself becomes a Nix flake at the repo root; `nix profile install` (backed by a binary cache) replaces the old "curl install.sh → download GitHub-Release asset → sha256/cosign → /usr/local/bin" path. GitHub Releases stays the artifact store (JReleaser publishes `sot-<os>-<arch>`), but `packages.<system>.default` is a `fetchurl`-wrapper derivation pinning each asset by SHA-256; Cachix serves the realized `/nix/store` path as a signed CDN. **BUILD CHOICE: fetchurl-wrapper over gradle2nix for v1** — a reproducible from-source GraalVM/Mandrel `native-image` build in the pure Nix sandbox is heavy/brittle across 4 systems and buys no UX gain (cache means download-anyway). The flake wraps the CI-built binary with `fetchurl` + `autoPatchelfHook` (Linux, `stdenv.cc.cc.lib`+`zlib` buildInputs) and plain `install -Dm755` on darwin (Mach-O, no patchelf); gradle2nix is a future `packages.sot-src`. Flake enumerates `x86_64-linux, aarch64-linux, x86_64-darwin, aarch64-darwin` via `flake-utils.eachSystem`. macOS is first-class (CI adds `macos-14`/`macos-13` runners). Windows delegated to WSL sibling. Java: new `de.jklein.sot.nix.NixService` port (process/); `bootstrap.SelfUpdateCommand`/`BinaryUpdater` rewritten to `nix profile upgrade sot`. `install.sh` (Linux+macOS): (1) Determinate `nix-installer` if absent; (2) append `extra-substituters`/`extra-trusted-public-keys`; (3) `nix profile install github:NiklasJavier/SOT --accept-flake-config`; (4) print `sot bootstrap`. Flake declares `nixConfig.extra-substituters` so `--accept-flake-config` self-configures. Cachix (managed) for v1; self-hosted attic (`cache.jklein.de`) as sovereignty option. macOS secrets: no tmpfs — `TransientPasswordFile` falls back to `mkstemp` 0600 on encrypted APFS `$TMPDIR`.

- `flake.nix` — nix-flake (repo root) — inputs=nixpkgs(+flake-utils); outputs packages/apps/devShells for 4 systems; nixConfig declares cache.
- `packages.<system>.default (mkSot)` — Nix derivation — fetchurl-wrapper, SHA-256-pinned; autoPatchelfHook (Linux) / plain install (darwin); `meta.mainProgram=sot`.
- `apps.default` — Nix app output — `flake-utils.mkApp` so `nix run github:NiklasJavier/SOT` works.
- `devShells.default` — Nix devShell — jdk21 + gradle + just + mandrel/graalvm + native toolchain.
- `install.sh` — POSIX bootstrap — install Nix if absent → write cache → nix profile install → next-steps.
- `de.jklein.sot.nix.NixService` — Java port (process/) — typed wrapper for profile install/upgrade/list/remove + build.
- `bootstrap.SelfUpdateCommand` / `NixSelfUpdater` — Java CLI command — self-update = `nix profile upgrade sot`; retires the GitHub-Release re-download `BinaryUpdater`; atomic, no re-exec/ATOMIC_MOVE.
- `.github/workflows/release.yml` — CI — build native → JReleaser publish → compute SHA-256 → update flake hashes → `nix build .#default` per runner → `cachix-action@v17` push.
- Cachix cache (`sot`) / attic — binary cache — serves prebuilt native store paths; attic self-hosted as sovereign alt.

**Effort: L**

### 1.4 windows-wsl-bootstrap

Windows = a *thin Windows-side bootstrapper + shim*; ALL real logic runs inside a NixOS-WSL Linux env where the ordinary Linux `install.sh` + Nix path runs unchanged. No Windows-native GraalVM target — the native binary stays Linux-only, executed inside WSL. New assets under `dist/windows/` served at `https://<host>/cli/`: `install.ps1`, `sot.cmd` + a compiled single-file `sot.exe` shim (Rust/Go), and the `nixos.wsl` tarball (+`.sha256`). Only two Java touchpoints: `de.jklein.sot.runtime.WslEnvironment` (record; detects WSL via `$WSL_DISTRO_NAME` / `/proc/sys/kernel/osrelease` so doctor, `UpdateNotifier` Windows toast, `SotPaths` adapt) and `de.jklein.sot.bootstrap.windows.WindowsShimWriter` (CI-only shim regeneration). `install.ps1` is an idempotent, reboot-resumable state machine driven by `$env:SOT_RESUME`: **0 Preflight** (build ≥19041, self-elevate `Start-Process -Verb RunAs`, virtualization); **A Ensure WSL2** (`wsl --install --no-distribution`, RunOnce re-invoke with `SOT_RESUME=B` + reboot if pending); **B Install NixOS-WSL** (idempotent `wsl -l -q` scan, download+verify `nixos.wsl`, `wsl --install --from-file` on WSL ≥2.4.4 else `wsl --import NixOS $dataDir nixos.wsl --version 2`); **C Provision sot** (`wsl -d NixOS -u root -- bash -lc "curl … install.sh | bash"` → reduces to `nix profile install github:NiklasJavier/SOT` from cache); **D Shim** (copy `sot.exe`/`sot.cmd` to `%LOCALAPPDATA%\Programs\sot\bin`, prepend PATH, broadcast `WM_SETTINGCHANGE`). The shim forwards argv + stdio + exit code to `wsl.exe -d NixOS -e sot …`; line-oriented selector (no JLine) reads ConPTY under Windows Terminal, degrades to `list` when `System.console()==null`. Docker/systemd run inside NixOS-WSL (no Docker Desktop); services reachable on `localhost` via localhostForwarding (mirrored networking recommended on Win11). Self-update stays Linux-side.

- `install.ps1` — powershell-script — reboot-resumable state machine; `irm https://<host>/cli/install.ps1 | iex`.
- `sot.exe` — compiled shim (Rust/Go) — primary PATH entry; spawns `wsl.exe -d NixOS -e sot <argv>` with faithful argv, inherited ConPTY, propagated exit code.
- `sot.cmd` — cmd-shim — zero-dependency fallback (`wsl.exe -d NixOS -e sot %*`).
- `nixos.wsl` — nix-wsl-tarball — NixOS-WSL rootfs (wsl.enable + systemd + docker + cache substituters), sha256-verified, imported as distro `NixOS`.
- `WslEnvironment` — java-record (runtime/) — runtime WSL detection; doctor/notifier/SotPaths adapt.
- `WindowsShimWriter` — java-class (bootstrap/windows) — CI-time shim generator/validator; not at user runtime.
- `/cli/` asset set — http-assets (owner host) — single distribution surface: install.sh, install.ps1, nixos.wsl(+.sha256), sot.exe/sot.cmd, manifest.json.

**Effort: L**

---

## 2. Concrete Schemas, Interfaces & Nix/Shell Snippets (VERBATIM)

### 2.1 `NixService` — the two published shapes

**Area nix-substrate-and-dependencies** (full port):

```java
public interface NixService {
  NixEnvironment probe();                         // detect nix, version, flakes, daemon, NixOS, system
  boolean        isNixPresent();
  void           ensureExperimentalFeatures();    // persist + pass 'nix-command flakes'

  ProfileList profileList(NixProfileRef p);        // nix profile list --json
  NixResult   profileInstall(NixProfileRef p, FlakeRef ref);
  NixResult   profileUpgrade(NixProfileRef p, String nameOrAll);
  NixResult   profileRemove(NixProfileRef p, String name);

  NixResult      build(FlakeRef ref);              // nix build <ref> --no-link --print-out-paths
  JsonNode       eval(FlakeRef ref, String attr);  // nix eval <ref>#<attr> --json
  FlakeMetadata  flakeMetadata(FlakeRef ref);      // nix flake metadata <ref> --json
  NixResult      flakeUpdate(Path flakeDir);       // nix flake update (bump flake.lock, gated)
  NixResult      run(FlakeRef ref, List<String> appArgs); // nix run <ref> -- <args>

  void      ensureSubstituter(BinaryCache cache);  // add substituter + trusted-public-key idempotently
  NixConfig currentConfig();                        // nix config show --json (subset)
}
```

Supporting records/enums (same area):

```java
record NixEnvironment(boolean present, Optional<String> version, boolean flakesEnabled,
                      boolean daemonMode, boolean insideNixOS, String system,
                      List<String> substituters) {}
record FlakeRef(String value) {                     // "nixpkgs#git", "github:NiklasJavier/SOT", "/home/u/.sot/toolchain#toolchain"
  static FlakeRef nixpkgs(String attr){ return new FlakeRef("nixpkgs#"+attr); } }
record NixProfileRef(Path path) {}                  // $SOT_HOME/state/profile (isolated from user default)
record ProfileEntry(int index, String name, String storePath, List<String> flakeRefs) {}
record ProfileList(List<ProfileEntry> entries) {}
record FlakeMetadata(String resolvedUrl, String lockedRev, Instant lastModified, JsonNode raw) {}
record NixResult(int exitCode, String stdout, String stderr, Duration took){ boolean ok(){return exitCode==0;} }
record BinaryCache(String url, String publicKey) {}
enum   NixPkgKind { PROFILE_PKG, SYSTEM_SERVICE }
record NixPackageRef(String toolId, String nixAttr, NixPkgKind kind, Optional<String> minVersion) {}
```

**Area cli-as-flake-and-cross-platform** (thinner port variant, `de.jklein.sot.nix.NixService`):

```java
public interface NixService {
  NixResult profileInstall(String flakeRef);      // nix profile install <ref> --accept-flake-config
  NixResult profileUpgrade(String name);          // nix profile upgrade sot  (self-update)
  List<NixProfileEntry> profileList();            // nix profile list --json
  NixResult install(String pkg);                  // nix profile install nixpkgs#<pkg>  (tools: git/ansible/...)
}
// backed by shared ProcessRunner; used by SelfUpdateCommand + DependencyInstaller (nix-substrate area)
```

### 2.2 `InstallStrategy` contract + `NixProfileManager` (area app-install-and-update-via-nix)

```java
public interface InstallStrategy {              // unchanged contract; NIX/NIX_FLAKE are new impls
  AppSourceType type();                         // NIX | NIX_FLAKE | GIT_REPO | DOCKER_COMPOSE | SCRIPT
  ResolvedSource resolve(AppManifest m, InstallContext ctx);
  InstallOutcome install(ResolvedSource s, InstallContext ctx);
  InstallOutcome update (ResolvedSource s, InstalledApp cur, InstallContext ctx);
  void           remove (InstalledApp cur, InstallContext ctx);
}
```

```java
final class NixProfileManager {
  Path profileDir(String appId);                                  // {stateRoot}/profiles/<appId>
  InstallOutcome install(String appId, String installable);        // nix profile install --profile p <installable>
  InstallOutcome upgrade(String appId, String name);               // nix profile upgrade --profile p <name>
  void           remove (String appId);                            // nix profile remove + unlink bin/*, rm profile
  void           linkBinaries(String appId);                       // symlink <profile>/bin/* -> {binRoot}
  String         lockedRev(String appId);                          // from `nix profile list --json`
}
```

### 2.3 `NixVersionResolver` + `UpdateStrategy` (area app-install-and-update-via-nix)

```java
interface VersionResolver { UpdateStrategy strategy(); ResolvedVersion resolveLatest(VersionQuery q, ResolverContext ctx); }
@ApplicationScoped
class NixVersionResolver implements VersionResolver {
  // registered for BOTH NIX and NIX_FLAKE via a small StrategySet, or two thin subclasses
  public UpdateStrategy strategy() { return UpdateStrategy.NIX_FLAKE; }
  public ResolvedVersion resolveLatest(VersionQuery q, ResolverContext ctx) {
    // NIX_FLAKE: nix flake metadata <ref> --json -> node.at("/locked/rev") + /locked/lastModified
    // NIX:       nix eval --raw <nixpkgsRef>#<attr>.version
    // returns ResolvedVersion(latest, rawLatest, digest=rev, at, cache)
  }
}
enum UpdateStrategy { NIX, NIX_FLAKE, GITHUB_RELEASE, GIT_TAG, DOCKER_IMAGE, STATIC, SCRIPT }  // APT removed
```

### 2.4 Revised `app.yml` source/version blocks

**nixpkgs attribute app** (area app-install-and-update-via-nix):

```yaml
# app.yml — nixpkgs attribute app (system tool or CLI)
source:
  type: nix                       # -> NixpkgsInstallStrategy
  attr: terraform                 # nixpkgs attribute
  nixpkgs: github:NixOS/nixpkgs/nixos-24.05   # optional channel/rev pin (else global default pin)
  mode: profile                   # profile (default) | build   (build => nix build --out-link)
version:
  strategy: nix                   # -> NixVersionResolver (NIX)
  constraint: '>=1.7.0 <2.0.0'    # applied to nixpkgs attr .version when SemVer-parseable
```

**flake app** (area app-install-and-update-via-nix):

```yaml
# app.yml — flake app (owner's own app, incl. SOT-catalog apps)
source:
  type: nix-flake                 # -> NixFlakeInstallStrategy
  flakeRef: github:NiklasJavier/grafana-stack   # flake installable
  attr: default                   # outputs.packages.<system>.<attr> (default)
  rev: v10.4.0                    # optional explicit pin; else flake.lock governs
version:
  strategy: nix-flake             # -> NixVersionResolver (NIX_FLAKE)
  # compares installed locked rev vs `nix flake metadata --json` .locked.rev
```

**docker-compose app; docker itself comes FROM nix** (area app-install-and-update-via-nix):

```yaml
# app.yml — docker-compose app; docker itself comes FROM nix
source:
  type: docker-compose
  repoUrl: https://github.com/NiklasJavier/monitoring
  composeFile: docker-compose.yml
requires:
  tools: [docker]                 # NixToolProvisioner.ensure("docker") -> shared system nix profile
```

**nix source + version block (area nix-substrate-and-dependencies variant):**

```yaml
# app.yml — nix source + version block (replaces apt-deb)
source:
  type: nix                      # AppSourceType.NIX (reuses NixService.profileInstall)
  attr: nixpkgs#hello            # or a flake: github:owner/app#default
  flakeRef: github:NixOS/nixpkgs/nixos-24.11   # optional pin for reproducibility
version:
  strategy: nix                  # NixVersionResolver: nix eval <attr>.version / flake metadata
  attr: nixpkgs#hello
```

### 2.5 `NixPackageCatalog` defaults (area nix-substrate-and-dependencies)

```
// NixPackageCatalog defaults (toolId -> nixpkgs attr, kind); overridable via SotConfig.tools
git->git(PROFILE), ansible->ansible(PROFILE), terraform->terraform(PROFILE) [opentofu default option],
kubectl->kubectl, helm->kubernetes-helm, jq->jq, yq->yq-go, curl->curl, cosign->cosign,
age->age, sops->sops, docker-cli->docker-client(PROFILE),
docker->docker(SYSTEM_SERVICE: NixOS virtualisation.docker / colima / Docker Desktop)
```

### 2.6 Repo `flake.nix` outline (area cli-as-flake-and-cross-platform)

```nix
{
  description = "SOT — dynamic app-manager CLI (native GraalVM)";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };
  nixConfig = {
    extra-substituters = [ "https://sot.cachix.org" ];
    extra-trusted-public-keys = [ "sot.cachix.org-1:BASE64KEY=" ];
  };
  outputs = { self, nixpkgs, flake-utils }:
    let
      version = "1.2.0";                     # single-sourced with JReleaser tag
      assets = {                              # hashes regenerated by CI per release
        "x86_64-linux"   = { file = "sot-linux-amd64";  hash = "sha256-AAAA..."; };
        "aarch64-linux"  = { file = "sot-linux-arm64";  hash = "sha256-BBBB..."; };
        "x86_64-darwin"  = { file = "sot-darwin-amd64"; hash = "sha256-CCCC..."; };
        "aarch64-darwin" = { file = "sot-darwin-arm64"; hash = "sha256-DDDD..."; };
      };
    in flake-utils.lib.eachSystem (builtins.attrNames assets) (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        a = assets.${system};
        linux = pkgs.stdenv.isLinux;
        sot = pkgs.stdenv.mkDerivation {
          pname = "sot"; inherit version;
          src = pkgs.fetchurl {
            url = "https://github.com/NiklasJavier/SOT/releases/download/v${version}/${a.file}";
            hash = a.hash;
          };
          dontUnpack = true;
          nativeBuildInputs = pkgs.lib.optionals linux [ pkgs.autoPatchelfHook ];
          buildInputs = pkgs.lib.optionals linux [ pkgs.stdenv.cc.cc.lib pkgs.zlib ];
          installPhase = ''runHook preInstall; install -Dm755 $src $out/bin/sot; runHook postInstall'';
          meta.mainProgram = "sot";
        };
      in {
        packages.default = sot; packages.sot = sot;
        apps.default = flake-utils.lib.mkApp { drv = sot; };
        devShells.default = pkgs.mkShell {
          packages = [ pkgs.jdk21 pkgs.gradle pkgs.just pkgs.mandrel ];
        };
      });
}
```

### 2.7 SOT-managed toolchain flake `$SOT_HOME/toolchain/flake.nix` (area nix-substrate-and-dependencies)

```nix
# $SOT_HOME/toolchain/flake.nix  (Qute-rendered from the declared tool set; flake.lock committed => reproducible)
{
  description = "SOT-managed toolchain";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";      # SOT-pinned channel
  outputs = { self, nixpkgs }:
    let systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
        forAll = f: nixpkgs.lib.genAttrs systems (s: f nixpkgs.legacyPackages.${s});
    in {
      packages = forAll (pkgs: {
        toolchain = pkgs.buildEnv {
          name  = "sot-toolchain";
          paths = with pkgs; [ git ansible terraform jq ];       # {#each declaredTools} rendered {/each}
        };
      });
    };
}
```

### 2.8 Binary-cache `nix.conf` config

**Cachix / owner-cache variant (area app-install-and-update-via-nix):**

```
# nix.conf (written by bootstrap) — owner binary cache so installs pull prebuilt closures
experimental-features = nix-command flakes
substituters = https://cache.nixos.org https://<owner-cache>.cachix.org
trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY= <owner-cache>.cachix.org-1:<key>
```

**Self-hosted attic variant (area cli-as-flake-and-cross-platform):**

```
extra-substituters = https://cache.jklein.de/sot
extra-trusted-public-keys = sot:BASE64PUBKEY=
```

### 2.9 Rewritten `install.sh` outline (Linux + macOS)

**Area cli-as-flake-and-cross-platform (canonical):**

```bash
#!/usr/bin/env bash
set -euo pipefail
FLAKE="github:NiklasJavier/SOT"
CACHE_URL="https://sot.cachix.org"
CACHE_KEY="sot.cachix.org-1:BASE64KEY="
# 1. Nix present? else Determinate installer (flakes on by default, adds trusted-user)
if ! command -v nix >/dev/null 2>&1; then
  curl -fsSL https://install.determinate.systems/nix | sh -s -- install --no-confirm
  . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
fi
# 2. Configure the binary cache in the user nix.conf (trusted-user honors these)
mkdir -p "$HOME/.config/nix"
if ! grep -q "$CACHE_URL" "$HOME/.config/nix/nix.conf" 2>/dev/null; then
  cat >>"$HOME/.config/nix/nix.conf" <<EOF
experimental-features = nix-command flakes
extra-substituters = $CACHE_URL
extra-trusted-public-keys = $CACHE_KEY
EOF
fi
# 3. Install SOT from the flake — download-only via the cache, no compile
nix profile install "$FLAKE" --accept-flake-config
# 4. Next steps
echo "sot installed. Next: sot bootstrap"
```

**Area nix-substrate-and-dependencies (condensed variant, owner-host cache):**

```bash
# install.sh (Linux/macOS/WSL) — Nix first, then SOT via flake + binary cache
curl -fsSL https://install.determinate.systems/nix | sh -s -- install --no-confirm   # multi-user daemon, flakes on
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
mkdir -p ~/.config/nix
printf 'substituters = https://cache.nixos.org https://sot.jklein.de/cache\ntrusted-public-keys = cache.nixos.org-1:6NCHdD... sot.jklein.de:BASE64KEY=\n' >> ~/.config/nix/nix.conf
nix profile install github:NiklasJavier/SOT          # pulls prebuilt GraalVM-native binary from cache
sot bootstrap                                        # ensures toolchain profile
```

### 2.10 `install.ps1` outline (area windows-wsl-bootstrap)

```powershell
# install.ps1 — outline (served at https://<host>/cli/install.ps1)
#requires -Version 5.1
$ErrorActionPreference = 'Stop'
$Host_ = 'https://<owner-host>/cli'
$Distro = 'NixOS'
$Resume = $env:SOT_RESUME  # '', 'B' after reboot

function Assert-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p  = New-Object Security.Principal.WindowsPrincipal($id)
  if (-not $p.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList \
      "-NoProfile -Command `"irm $Host_/install.ps1 | iex`""; exit
  }
}
function Set-Resume([string]$stage) {
  Set-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce' `
    -Name 'SotResume' -Value "powershell -NoProfile -Command `"$env:SOT_RESUME='$stage'; irm $Host_/install.ps1 | iex`""
}

Assert-Admin
if ([Environment]::OSVersion.Version.Build -lt 19041) { throw 'Windows 10 2004+/11 required' }

if ($Resume -ne 'B') {                       # --- Stage A: ensure WSL2 ---
  $hasWsl = (& wsl.exe --version 2>$null)
  if (-not $hasWsl) {
    wsl.exe --install --no-distribution      # enables VM Platform + WSL kernel
    Set-Resume 'B'; Write-Host 'Rebooting to finish WSL2 setup...'; Restart-Computer -Force; exit
  }
  wsl.exe --update --web-download
}

# --- Stage B: install NixOS-WSL (idempotent) ---
$installed = (wsl.exe -l -q) -contains $Distro
if (-not $installed) {
  $tar = "$env:TEMP\nixos.wsl"
  Invoke-WebRequest "$Host_/nixos.wsl"        -OutFile $tar
  Invoke-WebRequest "$Host_/nixos.wsl.sha256" -OutFile "$tar.sha256"
  $want = (Get-Content "$tar.sha256").Split(' ')[0]
  if ((Get-FileHash $tar -Algorithm SHA256).Hash -ne $want) { throw 'nixos.wsl checksum mismatch' }
  $ver = [version]((wsl.exe --version | Select-String 'WSL-Version').ToString().Split(':')[1].Trim())
  if ($ver -ge [version]'2.4.4') { wsl.exe --install --from-file $tar }
  else { $d="$env:LOCALAPPDATA\WSL\NixOS"; wsl.exe --import $Distro $d $tar --version 2 }
}

# --- Stage C: install sot inside the distro (Nix already present) ---
wsl.exe -d $Distro -u root -- bash -lc "curl -fsSL $Host_/install.sh | bash"

# --- Stage D: drop the Windows shim + PATH ---
$bin = "$env:LOCALAPPDATA\Programs\sot\bin"; New-Item -Force -ItemType Directory $bin | Out-Null
Invoke-WebRequest "$Host_/sot.exe" -OutFile "$bin\sot.exe"
Invoke-WebRequest "$Host_/sot.cmd" -OutFile "$bin\sot.cmd"
$u = [Environment]::GetEnvironmentVariable('Path','User')
if ($u -notlike "*$bin*") { [Environment]::SetEnvironmentVariable('Path',"$bin;$u",'User') }
Write-Host 'Done. Open a new terminal and run: sot app'
```

### 2.11 Windows `sot` shim (area windows-wsl-bootstrap)

`sot.cmd` (zero-dependency fallback):

```bat
REM sot.cmd — thin fallback shim (served at /cli/sot.cmd)
@echo off
wsl.exe -d NixOS -e sot %*
exit /b %ERRORLEVEL%
```

`sot.exe` (Rust — correct argv + stdio + exit-code passthrough):

```rust
// sot.exe shim (Rust) — correct argv + stdio + exit-code passthrough
use std::process::{Command, exit};
fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let status = Command::new("wsl.exe")
        .args(["-d", "NixOS", "-e", "sot"]).args(&args)
        .status().expect("wsl.exe not found — run install.ps1");
    exit(status.code().unwrap_or(1)); // stdin/stdout/stderr inherited (ConPTY)
}
```

### 2.12 NixOS-WSL tarball config + `/cli/` asset manifest (area windows-wsl-bootstrap)

```nix
# nixos.wsl flake (configuration.nix highlights baked into the tarball)
{ modulesPath, pkgs, ... }: {
  imports = [ "${modulesPath}/../nixos-wsl/modules" ]; # NixOS-WSL
  wsl.enable = true;
  wsl.defaultUser = "nixos";
  wsl.startMenuLaunchers = true;
  systemd.enable = true;                 # required for docker + sot systemd-timer
  virtualisation.docker.enable = true;   # docker runs INSIDE WSL, no Docker Desktop
  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    substituters = [ "https://<cache>.cachix.org" ];
    trusted-public-keys = [ "<cache>.cachix.org-1:<key>" ];
  };
  system.stateVersion = "24.11";
}
```

```
# What the owner host MUST serve under https://<host>/cli/
install.sh          # Linux + macOS bootstrap (Determinate nix-installer -> nix profile install)
install.ps1         # Windows bootstrap (this file)
nixos.wsl           # NixOS-WSL rootfs tarball  (imported as distro 'NixOS')
nixos.wsl.sha256    # checksum for the tarball
sot.exe             # compiled Windows shim (code-signed)
sot.cmd             # fallback shim
manifest.json       # { sotVersion, wslMinVersion, distroName, tarballSha256 }
```

### 2.13 CI release cache push (area cli-as-flake-and-cross-platform)

```yaml
# release.yml cache push (per-system runner):
- uses: cachix/cachix-action@v17
  with:
    name: sot
    authToken: "${{ secrets.CACHIX_AUTH_TOKEN }}"
    signingKey: "${{ secrets.CACHIX_SIGNING_KEY }}"
- run: nix build .#default && nix profile install .#default   # realizes + pushes on job end
```

---

## 3. Full Command & Recipe Surface

### (a) Nix commands SOT runs internally

- `nix profile install --profile {stateRoot}/profiles/<id> github:NixOS/nixpkgs/<rev>#<attr>` — install a NIX (nixpkgs attr) app into its per-app profile.
- `nix profile install --profile {stateRoot}/profiles/<id> <flakeRef>#<attr>` — install a NIX_FLAKE app (owner cache supplies prebuilt closure).
- `nix profile install --profile $SOT_HOME/state/profile $SOT_HOME/toolchain#toolchain` — install the SOT-managed toolchain as one atomic, isolated profile entry.
- `nix profile install github:NiklasJavier/SOT [--accept-flake-config]` — install the prebuilt native `sot` from the flake + cache (download-only).
- `nix profile install nixpkgs#<pkg>` — provision a system tool (git/ansible/…) via `NixService.install` / `NixToolProvisioner`.
- `nix profile upgrade --profile {stateRoot}/profiles/<id> <name>` — app update for a nix-managed app.
- `nix profile upgrade --profile $SOT_HOME/state/profile --all` — reconcile toolchain after declared tool set changes.
- `nix profile upgrade sot` — CLI self-update (replaces GitHub-Release re-download).
- `nix profile remove --profile {stateRoot}/profiles/<id> <name>` — app remove (then unlink `bin/*`, rm profile dir).
- `nix profile list [--profile …] --json` — read installed locked rev + store-path version for the update monitor.
- `nix flake metadata <flakeRef> --json` — `NixVersionResolver` reads `.locked.rev` / `.lastModified` for upstream comparison.
- `nix eval --raw github:NixOS/nixpkgs/<rev>#<attr>.version` — resolve upstream version of a nixpkgs attr.
- `nix build <flakeRef>#<attr> --out-link {stateRoot}/apps/<id>/result` — `mode: build` alternative to profile install.
- `nix build .#default` — build/realize the native derivation locally (CI + contributors).
- `nix build <ref> --no-link --print-out-paths` — `NixService.build`.
- `nix flake update $SOT_HOME/toolchain` — gated bump of the pinned nixpkgs (updates `flake.lock`).
- `nix run github:NiklasJavier/SOT -- <args>` — run without installing (`apps.default`).
- `nix config show --json` — `NixService.currentConfig`.
- `curl -fsSL https://install.determinate.systems/nix | sh -s -- install --no-confirm` — Determinate multi-user daemon install (flakes on).

### (b) New / changed `sot` CLI commands

- `sot bootstrap` — `NixBootstrapTask`: ensure nix present → ensure SOT cache substituter → reconcile toolchain.
- `sot doctor` — `NixDoctorCheck`: nix/flakes/cache/tools/docker-daemon status (WSL-aware via `WslEnvironment`).
- `sot app install <id>` / `sot app update <id>` / `sot app remove <id>` — now run on the nix substrate (profile install/upgrade/remove).
- `sot app outdated` — update monitor over nix flake metadata / nix eval fan-out.
- `sot app` — interactive App-Selektor (through the Windows shim on Windows; ConPTY under Windows Terminal).
- `sot self-update` — `SelfUpdateCommand` → `NixService.profileUpgrade` (`nix profile upgrade sot`).
- `sot toolchain update` — gated `nix flake update` of the pinned nixpkgs.
- `sot nix status` — inspect the SOT profile.
- `sot nix gc` — garbage-collect old profile generations.

### (c) Install one-liners per platform

- **Linux / macOS:** `curl -fsSL https://jklein.de/cli/install.sh | bash` (Nix + cache + `nix profile install github:NiklasJavier/SOT`).
- **Any (no install):** `nix run github:NiklasJavier/SOT -- app list`.
- **Any (explicit):** `nix profile install github:NiklasJavier/SOT --accept-flake-config`.
- **Windows:** `irm https://<host>/cli/install.ps1 | iex` (elevates → WSL2 → NixOS-WSL → runs Linux `install.sh` inside → drops shim).
- **Cache-only client config:** `cachix use sot`.

### (d) justfile / gradle / release additions

- `just install-local` → `nix profile install .#default` — install the local flake (dev).
- `just apps-add <id>` → `sot app install <id>` (nix substrate).
- `just tools-ensure docker` → `NixToolProvisioner` shared system profile.
- `just nix-bootstrap` — wrapper over ensure-nix.
- `just toolchain-sync` — wrapper over reconcile.
- `just release TAG` → `gradlew jreleaserFullRelease` + regen flake asset hashes + cachix push.
- `just win-build` — cross-compile `sot.exe` shim + assemble `dist/windows/` assets for `/cli/`.
- `just win-tarball` — build the NixOS-WSL `nixos.wsl` rootfs from the flake + emit `nixos.wsl` + `nixos.wsl.sha256`.
- `just win-publish` — upload `install.ps1`, `sot.exe`/`sot.cmd`, `nixos.wsl`(+sha256), `manifest.json` to owner `/cli/`.
- `nix develop` — enter devShell (jdk21 + gradle + just + mandrel) for hermetic contributor builds.
- **CI `release.yml`:** build native per system → JReleaser publish assets → compute asset SHA-256 → update `flake.nix` asset hashes → `nix build .#default` on each runner → `cachix-action@v17` push signed store paths.
- **Windows raw WSL commands** (invoked by `install.ps1` / shim): `wsl --install --no-distribution`; `wsl --install --from-file nixos.wsl` (≥2.4.4) / `wsl --import NixOS <dir> nixos.wsl --version 2`; `wsl -d NixOS -u root -- bash -lc 'curl -fsSL https://<host>/cli/install.sh | bash'`; `wsl -d NixOS -e sot <args>`.

---

## 4. Consolidated Decisions (question → recommendation)

**AGREED across areas:**

1. **Source build (gradle2nix) vs fetchurl-wrapper for the SOT flake?** → **fetchurl-wrapper for v1** (autoPatchelfHook on Linux, plain install on darwin). The cache means users download prebuilt either way, so a hermetic in-sandbox GraalVM/Mandrel build buys no UX gain and is brittle across 4 systems. Keep gradle2nix as a documented future `packages.sot-src` track. *(cli-as-flake AND nix-substrate agree.)*
2. **How does self-update work now?** → `nix profile upgrade sot` — atomic, rollback-able (`nix profile rollback`), no re-exec/ATOMIC_MOVE. Retire `BinaryUpdater`'s GitHub-Release download; `SelfUpdateCommand` shells `NixService.profileUpgrade`. On Windows it stays entirely Linux-side inside WSL; the thin shim is version-agnostic. *(cli-as-flake + windows-wsl agree.)*
3. **Multi-user (daemon) vs single-user Nix?** → **Multi-user daemon** (Determinate default) on Linux/macOS/WSL; fall back to single-user only where systemd/root unavailable; skip nix install entirely inside NixOS/NixOS-WSL. *(nix-substrate; consistent with all.)*
4. **Flake reference?** → `github:NiklasJavier/SOT` as canonical (git host is source of truth, works with `nix profile upgrade`). `install.sh` served from owner `/cli/` but internally targets the github flake; a tarball flake on owner host is a fallback.
5. **Does JReleaser + sha256 + cosign survive?** → Yes — JReleaser still publishes per-platform assets (the fetchurl source); cosign stays as defense-in-depth; Nix per-asset hash pinning + cache signing key become the primary integrity gate. The loose `.sha256` sidecar consumption in install.sh is dropped; asset hashes live in `flake.nix`, regenerated by CI.
6. **Which Linux distro backs the Windows path — Ubuntu+Nix vs NixOS-WSL?** → **NixOS-WSL** (the 100%-Nix mandate means the Linux env should itself be declaratively Nix; `sot` installs identically to native Linux, zero Windows-specific install logic). *(windows-wsl; no area disagrees.)*
7. **Cross-platform SOT flake systems** → enumerate `x86_64-linux, aarch64-linux, x86_64-darwin, aarch64-darwin`; macOS promoted to first-class native. Resolves D19 (was macOS JVM-only, Windows absent).

**⚠️ FLAGGED DISAGREEMENTS between areas:**

8. **⚠️ Binary cache: Cachix (managed) vs self-hosted attic?** — **DISAGREEMENT.**
   - `cli-as-flake` → **Cachix for v1** (`sot.cachix.org`, `cachix-action@v17`, zero-ops); attic on `cache.jklein.de` as sovereignty option.
   - `nix-substrate` → **Self-hosted attic default** (`sot.jklein.de/cache`, to keep everything on owner infra per the `/cli/` host requirement); Cachix as zero-ops quick-start.
   - *Same substituter+trusted-key mechanism either way — swap two nix.conf lines. Needs an owner call on which is v1 default. (windows-wsl tarball references a generic `<cache>.cachix.org`.)*

9. **⚠️ Per-app Nix profiles vs one shared profile** — **PARTIAL TENSION (different scopes, but two profile models coexist).**
   - `app-install` → **Per-app profiles** at `{stateRoot}/profiles/<appId>` for APPS (independent generations/rollback, isolated failure, clean removal; `bin/*` symlinked onto one sot-managed PATH dir). A shared `system` profile is used ONLY for system tools via `NixToolProvisioner` (installs `nixpkgs#docker` etc. individually).
   - `nix-substrate` → **One dedicated profile** `$SOT_HOME/state/profile` holding ALL tools as a single `buildEnv` `toolchain` entry (generated flake + committed `flake.lock`), via `NixToolchainReconciler`. Explicitly rejects per-tool `nix profile install nixpkgs#x` (unpinned, clutters profile) except as a `--simple` fallback.
   - *Reconcile: apps = per-app profiles (both compatible); TOOLS have TWO competing mechanisms — `NixToolProvisioner`'s shared `system` profile with individual installs vs `ToolchainManager`'s single buildEnv toolchain profile. Pick the buildEnv/reconciler model (reproducible, pinned) and have `NixToolProvisioner` route through it.*

10. **⚠️ terraform vs opentofu default** — **RESOLVED-ish, but examples diverge.** `nix-substrate` decides: map `terraform` → **opentofu** by default in `NixPackageCatalog` (avoids BSL + unfree flag), overridable via `SotConfig.tools`. `app-install`'s `app.yml` example still uses `attr: terraform` illustratively — align the example to the opentofu default.

11. **How does a NIX (nixpkgs attr) app get pinned/updated within a constraint?** → Pin the nixpkgs input to a channel/rev in `source.nixpkgs` (or global default). EXACT pin ⇒ frozen rev in `installed.yml`; RANGE (`version.constraint`) ⇒ move the nixpkgs rev/branch only while resolved attr `.version` stays in range; fall back to input-rev comparison when `.version` isn't SemVer.

12. **`nix profile install` vs `nix build`+symlink as default install mechanism?** → Default `nix profile install` (generation history, upgrade/rollback, matches self-update story). Offer `mode: build` (`nix build --out-link`) as opt-in for apps needing only a stable store-path result.

13. **Keep GITHUB_RELEASE_BINARY / DOCKER_IMAGE source+version types?** → **Drop GITHUB_RELEASE_BINARY** as an app source (fold owner apps into `NIX_FLAKE`). KEEP `DOCKER_IMAGE` version strategy for docker-compose apps and `GIT_TAG`/`SCRIPT` for git-repo/script apps. Definitively REMOVE `APT_DEB` (source) and `APT` (version).

14. **One `NixVersionResolver` bean for both NIX and NIX_FLAKE, or two?** → One implementation with two registrations (small `StrategySet` or two 1-line subclasses) so `UpdateMonitorService`'s `Map<UpdateStrategy,VersionResolver>` stays exact while `nix flake metadata` / `nix eval` logic is shared.

15. **SOT-managed generated flake (buildEnv) vs per-tool `nix profile install nixpkgs#x`?** → Generated flake `buildEnv` in `$SOT_HOME/toolchain`, one profile entry; atomic, one PATH entry, committed `flake.lock` = reproducibility. Per-tool installs only as a `--simple` fallback. *(Feeds decision #9.)*

16. **Mutate the user default nix profile or a dedicated one?** → **Dedicated** profile `$SOT_HOME/state/profile`; never clobber the user default; SOT owns and can wipe its own.

17. **docker daemon (not a profile package)?** → Install docker CLI as `PROFILE_PKG`; treat the daemon as `SYSTEM_SERVICE` — doctor delegates (NixOS-WSL `virtualisation.docker.enable`, macOS colima/Docker Desktop). Never profile-install a running daemon.

18. **macOS secret handling without tmpfs?** → On darwin `TransientPasswordFile` falls back to `mkstemp` 0600 under encrypted APFS `$TMPDIR` (no tmpfs on macOS); guard perms via `PosixGuards`. Resolves D19.

19. **`sot.cmd` vs compiled `sot.exe` as the Windows PATH shim?** → Ship code-signed `sot.exe` as primary (faithful argv vector, inherited ConPTY stdio, exact exit code); `sot.cmd` as zero-dependency fallback for policy/SmartScreen-blocked environments.

20. **Pre-bake sot into the `nixos.wsl` tarball, or install via `install.sh` after import?** → Minimal NixOS-WSL tarball + `install.sh` from the binary cache (single source of truth with Linux/macOS, always-current sot). Optionally publish a batteries-included tarball for offline/air-gapped.

21. **`wsl --install --from-file` vs `wsl --import`?** → Prefer `--from-file` (WSL ≥2.4.4, cleaner registration); fall back to `--import NixOS <dir> nixos.wsl --version 2` on older WSL, gated by a version probe.

22. **How to survive the WSL-feature-enablement reboot?** → `HKCU\...\RunOnce` entry re-invoking `irm .../install.ps1 | iex` with `SOT_RESUME=B`; every stage idempotent so a repeated run is safe.

23. **WSL2 networking mode for services (docker etc.)?** → Default NAT + `localhostForwarding=true`; recommend mirrored networking on Win11 22H2+ for inbound/parity. Document, don't hard-require.

---

## 5. Native-Image / Reproducibility / Risks

### 5.1 GraalVM-native-in-Nix build concern (gradle2nix vs fetchurl-wrapper)

Both `cli-as-flake` and `nix-substrate` recommend the **fetchurl-wrapper** flake around the CI-built GraalVM/Mandrel native binary as the v1 default, NOT a from-source gradle2nix build. Rationale: a reproducible from-source `native-image` build inside the pure Nix sandbox is heavy (large builder image, offline dep-vendoring via a fixed-output derivation, slow, brittle across the 4 systems), and — because the binary cache means users download the prebuilt closure regardless — it buys **no UX benefit**. The CI native binary is the tested source of truth. The wrapper uses `fetchurl` + `autoPatchelfHook` on Linux (mostly-static glibc binary from D1, `buildInputs = [stdenv.cc.cc.lib zlib]` kept minimal) and plain `install -Dm755` on darwin (Mach-O, no patchelf). gradle2nix is documented as a future, audited `packages.sot-src` hermetic-source-build track behind the default.

### 5.2 Reproducibility notes

- **App/CLI pinning:** flake `flake.lock` governs transitive pins for `NIX_FLAKE`; nixpkgs input pinned by channel/rev for `NIX`; EXACT pin ⇒ frozen locked rev in `installed.yml`.
- **Toolchain:** SOT-generated `$SOT_HOME/toolchain/flake.nix` with a SOT-pinned nixpkgs input + **committed `flake.lock`** = full reproducibility; one atomic `buildEnv` entry. Updates only on demand via gated `sot toolchain update` (`nix flake update`).
- **Asset integrity:** `flake.nix` asset SHA-256 hashes regenerated by CI in the same release job; release fails if `nix build .#default` mismatches. Cache signing key + per-asset hash pinning are the primary integrity gate (cosign kept as defense-in-depth).
- **Version comparison correctness:** flakes compared by locked rev / `lastModified` equality (never invented ordering); nixpkgs attrs by hand-rolled `SemVer` only when parseable, else input-rev equality + report `UNKNOWN`.

### 5.3 Top 7 Risks (ranked, deduplicated across areas)

1. **Binary-cache miss forces compile-from-source (huge, slow) — undermines the whole download-only value prop and breaks first-run UX on every platform.** *(app-install, nix-substrate, cli-as-flake all raise it.)* → Mandatory substituter + trusted-public-key configured in nix.conf BEFORE first install; CI pushes every catalog flake app + pinned nixpkgs closure + native CLI + toolchain to the owner Cachix/attic cache; surface a "building from source, no cache hit" warning in `ProgressReporter`; doctor flags an unreachable cache.
2. **The mostly-static/musl native binary cannot `fork/exec` — yet EVERY `NixService` call shells out to `nix`; and `autoPatchelfHook` can mis-patch the glibc binary, breaking fork/exec of external tools (D1).** *(nix-substrate + cli-as-flake.)* → Keep the D1 mostly-static **glibc** decision (not musl); keep `buildInputs` minimal (`cc.cc.lib`+`zlib`); the native-image CI gate must prove the binary actually execs `nix --version` / `git --version` from the store path on every system before cachix push.
3. **A non-trusted-user cannot honor `extra-substituters`/keys in user nix.conf → silently falls back to compiling from source (needs Mandrel).** *(cli-as-flake.)* → Determinate installer adds the installing user as a trusted-user; `install.sh` verifies and, on multi-user daemon installs, offers to write the system `/etc/nix/nix.conf`; flake `nixConfig` + `--accept-flake-config` is a second path.
4. **`nix` binary absent / flakes not enabled → every nix strategy fails.** *(app-install.)* → `install.sh` runs the Determinate nix-installer (flakes on by default) before first `sot` run; `ToolPreflight`/doctor verify `nix --version` + experimental-features, emitting a single actionable remediation instead of raw nix errors.
5. **`nix flake metadata` / `nix eval` fan-out over all installed apps is slow + network-bound (stalls `sot app outdated`); and non-SemVer nixpkgs `.version` strings / rev-less flake refs cause wrong ordering / "always outdated".** *(app-install ×2.)* → Keep the virtual-thread `StructuredTaskScope` fan-out + `VersionCache` (TTL / serve-stale, keyed by flakeRef); use the denormalized rev in the catalog index; per-app failure ⇒ `UNKNOWN`, never abort; compare flakes by locked rev equality, nixpkgs by SemVer only when parseable.
6. **Supply-chain / MITM: the Determinate `curl | sh` installer pipe and the `nixos.wsl` tarball download.** *(nix-substrate + windows-wsl.)* → Pin the installer version + verify its checksum in `install.sh`; https-only; publish `nixos.wsl.sha256` + `manifest.json` on the owner host and hard-fail `install.ps1` on checksum mismatch.
7. **Legacy migration breakage: existing manifests using `source.type: apt-deb` (+ `version.strategy: apt`), and old curl-binary `/usr/local/bin/sot` users who can't `nix profile upgrade`.** *(nix-substrate + cli-as-flake.)* → Legacy migration reader rewrites `apt-deb`→`nix` and `apt`→`nix` with a tool→nixpkgs-attr guess flagged for owner review (D20); Phase-9 doctor detects a legacy `/usr/local/bin/sot` and offers a one-shot `nix profile install` reinstall; `SelfUpdateCommand` errors clearly if not nix-managed.

### 5.4 Remaining risks (deduplicated)

- **fetchurl asset-hash drift** from JReleaser output → flake build fails or points at the wrong asset → CI regenerates hashes from just-published assets in the same job; asset name schema single-sourced. *(cli-as-flake.)*
- **Cachix outage / key rotation** blocks installs / breaks trust → substituters degrade to source build; maintain an attic mirror as extra-substituter; key rotation via append (old key kept during overlap). *(cli-as-flake.)*
- **macOS Gatekeeper / quarantine / unsigned Mach-O** → nix store execution bypasses quarantine for daemon-fetched paths; `codesign --sign -` (ad-hoc) in CI; document `xattr -d com.apple.quarantine` fallback. *(cli-as-flake.)*
- **docker daemon can't be a user-profile package on non-NixOS** → split `PROFILE_PKG` vs `SYSTEM_SERVICE`; doctor gives platform-specific daemon guidance. *(nix-substrate + app-install + windows-wsl.)*
- **Per-app profiles multiply /nix/store closures + PATH symlink collisions** → shared-store dedup; resolve `bin/*` conflicts by app priority + warn; `nix store gc` hooked into remove. *(app-install.)*
- **Pinned `flake.lock` drifts from upstream security fixes** → gated `sot toolchain update`; UpdateMonitor surfaces a stale-nixpkgs signal. *(nix-substrate.)*
- **macOS Nix install needs /nix volume + sudo; NixOS-WSL bootstrap differs** → `probe().insideNixOS` + `system` branch the flow; Determinate macOS volume handling; doctor verifies `daemonMode`. *(nix-substrate.)*
- **WSL2 unavailable** (Windows Home older builds, virtualization off, nested VM) → preflight build ≥19041 + virtualization; actionable message; offline manual `Enable-WindowsOptionalFeature` path. *(windows-wsl.)*
- **RunOnce reboot resume is fragile** → every stage idempotent (`wsl -l -q` scan, checksum-gated download, PATH-contains guard). *(windows-wsl.)*
- **SmartScreen / AV blocks `irm | iex` or unsigned `sot.exe`** → code-sign `install.ps1` + `sot.exe`; ship `sot.cmd` fallback; offline `-LocalAssets` install. *(windows-wsl.)*
- **Interactive App-Selektor TTY misbehaves in legacy conhost** → line-oriented selector degrades to `list` when `System.console()==null`; recommend Windows Terminal. *(windows-wsl.)*
- **docker/systemd not running in WSL** → NixOS-WSL tarball ships `systemd.enable` + `virtualisation.docker.enable`; `sot doctor` checks. *(windows-wsl.)*
- **Windows-path args through the shim break inside Linux** (`C:\` vs `/mnt/c`) → keep the shim thin (verbatim argv); document `wslpath`; warn on slow `/mnt/c`. *(windows-wsl.)*
- **Distro-name collision** / pre-existing `NixOS` registration → detect via `wsl -l -q`, skip re-import; versioned name override; never overwrite without a reinstall flag. *(windows-wsl.)*

### 5.5 Final enum values (apt-deb removed, nix/nix-flake added)

**`AppSourceType`** (source types):
```
NIX, NIX_FLAKE, GIT_REPO, DOCKER_COMPOSE, SCRIPT
```
- ADDED: `NIX` (nixpkgs attribute), `NIX_FLAKE` (flake installable ref).
- KEPT: `GIT_REPO`, `DOCKER_COMPOSE`, `SCRIPT`.
- REMOVED: `APT_DEB` (definitively), and `GITHUB_RELEASE_BINARY` dropped as an app source (owner apps fold into `NIX_FLAKE`).

**`UpdateStrategy`** (version/update monitoring):
```
NIX, NIX_FLAKE, GITHUB_RELEASE, GIT_TAG, DOCKER_IMAGE, STATIC, SCRIPT
```
- ADDED: `NIX`, `NIX_FLAKE`.
- REMOVED: `APT`.
- KEPT: `GITHUB_RELEASE`, `GIT_TAG`, `DOCKER_IMAGE`, `STATIC`, `SCRIPT`.

**Supporting enum:** `NixPkgKind { PROFILE_PKG, SYSTEM_SERVICE }` — splits profile-installable tools (docker CLI) from platform-managed daemons (docker daemon).
