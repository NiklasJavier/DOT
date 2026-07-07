# SOT Dynamic App-Manager + Delivery — Consolidated Design Brief

Source: 4 architecture agents (app-model-and-catalog, update-monitoring, app-selector-cli-ux, gradle-justfile-github-install). Java/Quarkus/GraalVM native CLI `sot`.

---

## 1. Per-Area Design

### 1.1 app-model-and-catalog  *(effort: L)*

New package `de.jklein.sot.app` resolves the closed-world tension by splitting two axes Bash conflated: WHERE app definitions come from (`CatalogSource`, 100% runtime data) vs HOW an app is fetched/installed/version-checked (`InstallStrategy`, a fixed compiled-in CDI bean set). Adding an app = drop an `app.yml` into a catalog (zero rebuild); adding a strategy = add a bean (rebuild). This subsumes the old §1.4 CapabilityProvider layer: `ExtensionManifest`→`AppManifest`; `LocalDirectoryProvider`→a `bundled` CatalogSource over embedded `apps/**/app.yml`; `RemoteGitProvider`→a `git` CatalogSource + `git-repo`/`script` strategies; AAT/TID become two `app.yml` entries with a `runner:` block; `CapabilityStateStore`→`InstalledAppStore`, `CapabilityService`→`AppService`. Data model is immutable `@RegisterForReflection` records; `SourceSpec` carries an `AppSourceType` discriminator + raw `JsonNode options` (each strategy binds its own slice in `resolve()`, avoiding native-hostile Jackson `@JsonSubTypes`). `AppCatalog` (@ApplicationScoped) fetches each CatalogSource at runtime (git via `GitService`, http-index via JDK `HttpClient`, bundled via `AssetExtractor`), parses `index.yml`+manifests through the shared `YAMLMapper`, merges by `priority` into `Map<AppId,AppManifest>`, TTL-cached under `SotPaths.cacheRoot/catalog`. `InstalledAppStore` round-trips `installed.yml` (0600, temp+ATOMIC_MOVE). `AppService` is the single lifecycle owner (list/install with topo-resolved `requires.apps`/update/upgrade --all/remove/pin/unpin/outdated), dispatching to five strategies (git-repo, docker-compose, github-release-binary, apt-deb, script) that delegate to shared `ProcessRunner`/`GitService`/`GitHubReleaseClient`/`ChecksumVerifier`. `outdated()` fans `queryLatest()` across virtual threads, comparing a compiled `SemVer`.

Key components:
- `AppManifest` — record — typed model of `app.yml`; apiVersion+id+SourceSpec/VersionSpec/Requires/InstallSpec/RunnerSpec; @RegisterForReflection; subsumes ExtensionManifest/module.yml.
- `SourceSpec` — record — AppSourceType discriminator + raw JsonNode options; per-strategy typed binding, avoids Jackson polymorphism.
- `AppSourceType` — enum — GIT_REPO, DOCKER_COMPOSE, GITHUB_RELEASE_BINARY, APT_DEB, SCRIPT; maps 1:1 to a strategy bean.
- `InstallStrategy` — interface — THE single SPI: type()/resolve()/install()/update()/remove()/queryLatest(); five @ApplicationScoped beans, discovered `@All` at build time.
- `GitRepoStrategy / DockerComposeStrategy / GithubReleaseBinaryStrategy / AptDebStrategy / ScriptStrategy` — CDI-bean — the five compiled-in strategies; each delegates to shared ProcessRunner/GitService/GitHubReleaseClient/ChecksumVerifier.
- `AppCatalog` — CDI-bean — fetches all CatalogSources at runtime, parses+merges manifests by priority into one index; TTL-cached, refreshable.
- `CatalogSource` — record — runtime-configured origin (id, type git|http-index|bundled, url, ref, priority, trust); from SotConfig, not compiled in.
- `CatalogIndex` — record — parsed `index.yml`: app id→manifest path (+denormalised latest version) for fast listing.
- `InstalledAppStore` — CDI-bean — typed round-trip of `installed.yml`; atomic 0600 writes; replaces CapabilityStateStore.
- `InstalledApp` — record — per-app installed state: id, installedVersion, sourceType, sourceRef, catalogSourceId, installPath, pinned, pinnedVersion, timestamps, checksum.
- `AppService` — CDI-bean — single lifecycle owner: list/search/info/install/update/upgrade/remove/pin/unpin/outdated + topo-resolution + strategy dispatch; replaces CapabilityService.
- `AppStatus` — enum — joined catalog∪installed verdict: NOT_INSTALLED / INSTALLED / OUTDATED / PINNED.
- `SemVer` — record — compiled-in parse+compare+constraint match (no reflection); powers outdated + version.constraint gating.
- `RunnerSpec` — record — optional manifest block marking an app as an ansible/runner extension (AAT/TID roles+playbooks).
- `AppCommand` — @Command — picocli parent `sot app` (alias `ex` filters role=runner) with install/update/remove/pin/list/outdated/catalog subcommands + interactive selector.

### 1.2 update-monitoring  *(effort: L)*

Package `de.jklein.sot.app.update`, sibling to the App/catalog layer. Core seam is a closed-world `VersionResolver` SPI: one compiled-in strategy per source type, injected `@All List<VersionResolver>`, indexed by an `UpdateStrategy` enum (GITHUB_RELEASE, GIT_TAG, DOCKER_IMAGE, APT, SCRIPT). The SET of strategies is fixed/compiled; WHICH apps/repos/tag-patterns/pins exist is runtime data from each manifest `update:` block. `UpdateMonitorService` (@ApplicationScoped) is the single owner: `checkAll(CheckOptions)` reads installed apps via read-only port `InstalledApps`, builds a `VersionQuery` per app, dispatches to the matching resolver concurrently over virtual threads (StructuredTaskScope + semaphore), and folds into an `OutdatedReport`; any per-app failure degrades to `UpdateStatus.UNKNOWN`, never aborting. Resolvers return `ResolvedVersion` (optional parsed `Version` + raw tag + optional digest); a hand-rolled native-safe `Version`/`VersionConstraint` implements semver precedence. Pinning lives in user state, not the manifest: EXACT pin→PINNED (frozen), RANGE pin→UPDATE_AVAILABLE only for a newer satisfying version; non-semver apps (calver/sha/`:latest`) compare by equality/digest, with an optional `tagPattern` regex extracting a version. `VersionCache` persists per-`cacheKey(appId+strategy+paramsHash)` to `update-cache.yml`; HTTP resolvers issue conditional GETs (If-None-Match), 304→HIT, rate-limit→serve-stale+RATE_LIMITED. The binary is NOT a daemon: bootstrap installs a systemd timer (`sot-update-check.timer`→`.service` running `sot app check --quiet --notify`), cron fallback; the tick writes `last-check.json` and `UpdateNotifier` emits only on state-change. `sot app status`/`outdated` read `last-check.json` for instant offline display unless `--refresh`.

Key components:
- `VersionResolver` — interface (SPI) — strategy per source type; resolves LATEST for a VersionQuery; fixed compiled-in set, @All List-injected, discriminated by UpdateStrategy.
- `GitHubReleaseResolver` — CDI-bean — GitHub Releases API (latest non-draft/non-prerelease) via JDK HttpClient, ETag conditional GET + rate-limit aware.
- `GitTagResolver` — CDI-bean — `git ls-remote --tags` via ProcessRunner, filters by tagPattern, semver-sorts.
- `DockerImageResolver` — CDI-bean — registry v2 tag/manifest digest (bearer-token dance for ghcr/dockerhub); compares by digest for mutable tags.
- `AptPolicyResolver` — CDI-bean — `apt-cache policy <pkg>` via ProcessRunner (installed vs candidate).
- `ScriptResolver` — CDI-bean — executes a manifest-declared command whose stdout is the latest version (data-driven escape hatch).
- `UpdateMonitorService` — CDI-bean — single owner: dispatches resolvers concurrently, computes outdated status, builds OutdatedReport, degrades to UNKNOWN.
- `VersionCache` — CDI-bean — persistent per-app cache (etag/last-modified/ttl/lastLatest) for conditional requests, serve-stale, offline reads.
- `Version / VersionConstraint` — record + comparator — native-safe semver parse/precedence + pin constraint (EXACT vs RANGE); equality fallback.
- `AppUpdateReport / OutdatedReport` — record — per-app status + aggregate counts + generatedAt.
- `UpdateScheduler / UpdateNotifier` — CDI-bean — bootstrap-installed systemd timer (cron fallback); change-only summary to console/file/hook.
- `InstalledApps` — interface (port) — read-only view of installed apps (appId, installedVersion, digest, pin); the only cross-layer coupling.

### 1.3 app-selector-cli-ux  *(effort: L)*

The `sot app` surface is the tool's front door and single vocabulary subsuming old extensions/plugins/capability commands; an "App" is a catalog entry whose SourceType is one of the fixed strategies. Package `de.jklein.sot.cli.app`. One picocli parent `AppCommand` (@Command name="app", aliases {apps,a}) declares the subcommand tree; run bare on a TTY it launches the interactive App-Selektor via its Callable, run bare without a TTY it prints `list` (never blocks a script). Every subcommand is a CDI bean constructor-injecting `AppService` + `ConsoleService` + `ProgressReporter`. Subcommands: browse/select, list (ls), search, info, install (add,i), update (up), outdated (stale), remove (rm,uninstall), pin, unpin, refresh (sync), status. Automation flags live on `AppCommand` scope=INHERIT: `--json`, `--yes/-y`, `--no-color`, `--catalog <url>`, `--dry-run`. The selector `AppSelector` is deliberately line-oriented (NOT a raw-mode TUI): it renders a numbered table via `ConsoleService` and loops on a `BufferedReader` over stdin (numbers toggle multi-select, `/query` fuzzy-filter, `a` all, `i` install, `u` update, enter confirm, q quit); `AppStatus` (AVAILABLE/INSTALLED/OUTDATED/PINNED/BROKEN) drives colored glyphs. On confirm it builds a `SelectionOutcome`, delegates to `AppService`, streams per-app progress through `ProgressReporter`/`ProgressSink`. No JLine/ncurses/`stty` — trivially GraalVM-native-safe; `System.console()==null` (piped) → selector refuses. `AppService` is the renamed/expanded `CapabilityService`; `sot extensions`/`sot plugins` remain thin deprecated alias commands forwarding to `app list`/`app install`.

Key components:
- `AppCommand` — @Command — parent `sot app` (aliases apps,a); subcommand tree + inherited automation flags; bare-on-TTY launches AppSelector, bare-piped prints list.
- `AppSelectCommand` — @Command — `sot app browse|select`: explicit interactive entry instantiating AppSelector with full catalog view.
- `AppSelector` — class — native-safe line-oriented engine: numbered table + BufferedReader(stdin) toggle/filter/action loop → SelectionOutcome; no raw-mode/JLine.
- `AppTableRenderer` — class — formats ordered List<AppView> into numbered, column-aligned glyph+color table (also the `list` output).
- `AppStatus` — enum — AVAILABLE/INSTALLED/OUTDATED/PINNED/BROKEN → glyph+color; single source for selector and list/outdated.
- `SelectionState` — class — mutable per-session model: filter query, toggled name set, visible-row index map; fuzzy-matches summary+name.
- `AppListCommand / AppSearchCommand / AppInfoCommand / AppOutdatedCommand / AppStatusCommand` — @Command — non-interactive read verbs, honor --json; AppOutdatedCommand is the monitoring surface.
- `AppInstallCommand / AppUpdateCommand / AppRemoveCommand` — @Command — mutating verbs (names/--all, --yes/--dry-run); delegate to AppService + stream ProgressReporter.
- `AppPinCommand / AppUnpinCommand / AppRefreshCommand` — @Command — pin/unpin exclude/include from updates; refresh re-pulls catalog index.
- `ExtensionsCommand / PluginsCommand` — @Command — deprecated thin aliases forwarding to app list/install with a deprecation notice.
- `AppNameCandidates` — class — picocli Iterable<String> completionCandidates reading local catalog cache at runtime; @RegisterForReflection.
- `AppService` — interface (consumed) — collaborator from the app/catalog layer (renamed CapabilityService); the single lifecycle owner this UX injects.

### 1.4 gradle-justfile-github-install  *(effort: L)*

Build + delivery migrate from Maven to a single-module Gradle (Groovy DSL) build and a GitHub-Release-fed native install path. Bootstrap: `quarkus create cli de.jklein.sot:sot --gradle -x picocli` emits `settings.gradle`, `build.gradle`, `gradle.properties`, and the Gradle wrapper; every `mvnw`/`pom.xml` reference is replaced 1:1 (`./mvnw -B verify`→`./gradlew check`, `./mvnw install -Dnative`→`./gradlew build -Dquarkus.native.enabled=true`). `build.gradle` applies `plugins { java; io.quarkus; com.diffplug.spotless; jacoco; org.jreleaser }`, pins the platform via `enforcedPlatform("io.quarkus.platform:quarkus-bom:${quarkusPlatformVersion}")`. Native flags — `quarkus.native.builder-image` (pinned Mandrel/UBI9) + `-H:+StaticExecutableWithDynamicLibC` (mostly-static glibc, resolving D1 vs musl) — live in `application.properties`, not the build file. A root `Justfile` is the human entrypoint (setup/dev/build/native/test/lint/fmt/run/install-local/release/clean), shelling to `./gradlew` (CI calls Gradle directly). Delivery has two tiers: Tier 1 = one-liner `curl -fsSL .../install.sh | bash`; `install.sh` (the ONLY shell, shellcheck-gated) detects os/arch via `uname`, resolves the release tag (arg/`SOT_VERSION`/GitHub API), downloads `sot-<os>-<arch>` + `.sha256` (+ cosign `.sig`/`.pem`), verifies checksum then cosign keyless, and `install -m755`s to `/usr/local/bin/sot` or `~/.local/bin` fallback. Tier 2 = in-binary `sot self-update` reusing the same asset/verify contract. CI: `native-build.yml` (reusable matrix, glibc runners ubuntu-24.04 amd64 + arm) builds+smoke-tests each binary; `release.yml` (tag `v*`) runs `./gradlew jreleaserFullRelease` to produce checksums, Syft SBOM, cosign signatures and the GitHub Release.

Key components:
- `build.gradle` — config — single-module build: io.quarkus+spotless+jacoco+jreleaser plugins, enforcedPlatform quarkus-bom, all extensions as deps; replaces pom.xml.
- `settings.gradle` — config — rootProject.name='sot' + pluginManagement resolving io.quarkus from pinned platform.
- `gradle.properties` — config — pins quarkusPlatform{GroupId,ArtifactId,Version} + plugin version; single version source.
- `gradlew + gradle/wrapper` — config — pinned Gradle wrapper; replaces mvnw/.mvn.
- `Justfile` — config — human recipes wrapping ./gradlew.
- `install.sh` — resource — the only remaining shell: uname detect, resolve tag, download+verify(sha256+cosign), install -m755 to /usr/local/bin or ~/.local/bin fallback, print next steps.
- `.github/workflows/native-build.yml` — config — reusable workflow_call matrix over glibc runners; builds+smokes+uploads each sot-<os>-<arch>.
- `.github/workflows/release.yml` — config — on tag v*: invoke native-build, collect binaries, run gradlew jreleaserFullRelease.
- `.github/workflows/ci.yml` — config — PR/push gate: gradlew check (Spotless+JaCoCo+tests), shellcheck install.sh, one linux-amd64 native smoke.
- `jreleaser config` — config — NATIVE_IMAGE distributions per os/arch, checksum, Syft SBOM, cosign signing, GitHub Releases publisher.
- `.pre-commit-config.yaml` — config — Spotless, shellcheck/shfmt on install.sh, yamllint, ansible-lint, gitleaks.

---

## 2. Concrete Schemas & Interfaces

### 2.1 `app.yml` — the declarative unit (source.type picks the strategy)
```yaml
apiVersion: sot.dev/v1
kind: App
id: grafana                 # catalog-unique stable id
name: Grafana
description: Monitoring dashboards
category: observability
labels: [monitoring, ui]
source:
  type: docker-compose      # git-repo|docker-compose|github-release-binary|apt-deb|script
  repoUrl: https://github.com/owner/grafana-stack
  ref: v10.4.0              # tag/branch/commit
  composeFile: docker-compose.yml
version:
  strategy: compose-image-tag # git-tag|github-release|compose-image-tag|apt-policy|static|script
  constraint: '>=10.0.0 <11.0.0'
requires:
  tools: [docker]
  apps:  [prometheus]        # topo-ordered before install
  os:    [debian, ubuntu]
install:
  path: '{appsRoot}/grafana' # templated via SotPaths
  env:  { GF_PORT: '3000' }
  hooks: { postInstall: scripts/post.sh }
runner:                      # OPTIONAL — present => app is an AAT/TID-style extension
  playbooks: [site.yml]
```

### 2.2 `index.yml` — a CatalogSource's manifest listing
```yaml
apiVersion: sot.dev/v1
kind: CatalogIndex
apps:
  - { id: grafana,    manifest: apps/grafana/app.yml,    version: 10.4.0 }
  - { id: prometheus, manifest: apps/prometheus/app.yml, version: 2.53.0 }
```

### 2.3 `installed.yml` — typed state store (0600, atomic)
```yaml
apiVersion: sot.dev/v1
kind: InstalledApps
apps:
  grafana:
    installedVersion: 10.3.1
    sourceType: docker-compose
    sourceRef: v10.3.1
    catalogSourceId: owner-catalog
    installPath: /opt/sot/apps/grafana
    pinned: false
    pinnedVersion: null
    installedAt: 2026-07-01T10:00:00Z
    lastCheckedAt: 2026-07-07T08:00:00Z
    checksum: 'sha256:...'
```

### 2.4 `InstallStrategy` — the ONE strategy interface (5 compiled-in beans, apps are data)
```java
public interface InstallStrategy {
  AppSourceType type();                                     // discriminator
  ResolvedSource resolve(AppManifest m, InstallContext ctx);// bind+validate source.options
  InstallOutcome install(ResolvedSource s, InstallContext ctx);
  InstallOutcome update(ResolvedSource s, InstalledApp cur, InstallContext ctx);
  void           remove(InstalledApp cur, InstallContext ctx);
  VersionInfo    queryLatest(ResolvedSource s, InstallContext ctx); // outdated detection
}
// wired: @All List<InstallStrategy> -> Map<AppSourceType,InstallStrategy> at build time
```

### 2.5 `CatalogSource` + `AppService` (app-model area surface)
```java
record CatalogSource(String id, CatalogSourceType type, // GIT|HTTP_INDEX|BUNDLED
  String url, String ref, int priority, CatalogTrust trust) {}
// AppService surface (app-model-and-catalog)
interface AppService {
  List<AppView> list(EnumSet<AppStatus> filter);
  AppView info(String id); List<AppView> outdated();
  void install(String id, Optional<String> version);
  void update(String id); void upgradeAll();
  void remove(String id); void pin(String id, Optional<String> v); void unpin(String id);
}
```

### 2.6 `VersionResolver` SPI + update-report shapes (update-monitoring)
```java
interface VersionResolver { UpdateStrategy strategy(); ResolvedVersion resolveLatest(VersionQuery q, ResolverContext ctx); }
enum UpdateStrategy { GITHUB_RELEASE, GIT_TAG, DOCKER_IMAGE, APT, SCRIPT }
record VersionQuery(String appId, UpdateStrategy strategy, Map<String,String> params, Optional<VersionConstraint> pin, Optional<String> installedVersion, Optional<String> installedDigest, boolean includePrerelease, Optional<String> tagPattern) {}
record ResolvedVersion(Optional<Version> latest, String rawLatest, Optional<String> digest, Instant resolvedAt, CacheDisposition cache) {} // CacheDisposition: MISS|HIT|REVALIDATED|RATE_LIMITED
enum UpdateStatus { UP_TO_DATE, UPDATE_AVAILABLE, PINNED, UNKNOWN, NOT_INSTALLED }
record AppUpdateReport(String appId, UpdateStatus status, UpdateStrategy strategy, Optional<String> installedVersion, Optional<String> latestVersion, Optional<VersionConstraint> pin, Instant checkedAt, boolean fromCache, Optional<String> error) {}
record OutdatedReport(Instant generatedAt, List<AppUpdateReport> apps, int upToDate, int updatable, int pinned, int unknown) {}
sealed interface VersionConstraint { record Exact(Version v) implements VersionConstraint; record Range(String expr) implements VersionConstraint; } // Exact=frozen->PINNED, Range=bounded update
// VersionCache entry: { cacheKey, appId, strategy, rawLatest, digest, etag, lastModified, resolvedAt, ttl }
// UpdateMonitorService: OutdatedReport checkAll(CheckOptions); AppUpdateReport check(String appId, CheckOptions); // CheckOptions(refresh, cachedOnly, notify)
```

### 2.7 App manifest `update:` block (catalog data, no rebuild — update-monitoring)
```yaml
update:
  strategy: github-release   # git-tag | docker-image | apt | script
  repo: NiklasJavier/myapp   # or image: ghcr.io/.../x, or package: nginx, or command: "myapp --print-latest"
  tagPattern: '^v(\d+\.\d+\.\d+)$'
  includePrerelease: false
  ttl: 6h
```

### 2.8 CLI-layer `AppCommand` + DTOs (app-selector — note: a SECOND `AppService` shape)
```java
@Command(name="app", aliases={"apps","a"}, subcommands={AppSelectCommand.class, AppListCommand.class, AppSearchCommand.class, AppInfoCommand.class, AppInstallCommand.class, AppUpdateCommand.class, AppOutdatedCommand.class, AppRemoveCommand.class, AppPinCommand.class, AppUnpinCommand.class, AppRefreshCommand.class, AppStatusCommand.class})
class AppCommand implements Callable<Integer> {
  @Option(names="--json", scope=INHERIT) boolean json;
  @Option(names={"-y","--yes"}, scope=INHERIT) boolean assumeYes;
  @Option(names="--catalog", scope=INHERIT) Optional<String> catalogOverride;
  @Inject AppService apps; @Inject ConsoleService console;
}

// collaborator injected from the app/catalog layer (app-selector's view of AppService)
interface AppService { List<AppView> catalog(); List<AppView> installed(); List<AppView> outdated(); AppView info(String name); InstallResult install(String name, InstallOptions o); UpdateResult update(String name); void remove(String name); void pin(String name, Optional<String> version); void unpin(String name); CatalogIndex refresh(); }

record AppView(String name, String summary, AppStatus status, String installedVersion, String latestVersion, boolean pinned, SourceType source) {}
enum AppStatus { AVAILABLE, INSTALLED, OUTDATED, PINNED, BROKEN }
class AppSelector { SelectionOutcome run(List<AppView> rows, SelectorMode mode, ProgressReporter progress); }
record SelectionOutcome(List<String> chosen, SelectorAction action) {}
enum SelectorAction { INSTALL, UPDATE, REMOVE, CANCEL }

// completion: `sot app install <TAB>` -> live app names from local catalog cache
class AppNameCandidates implements Iterable<String> { @Inject AppService apps; public Iterator<String> iterator(){ return apps.catalog().stream().map(AppView::name).iterator(); } }

// selector key-loop grammar (line reads, native-safe):
// <int>[,<int>]  toggle rows | /<query>  fuzzy filter | a all | i install | u update | r remove | enter confirm | q quit
```

### 2.9 `build.gradle` (Groovy DSL)
```groovy
plugins {
  id 'java'
  id 'io.quarkus'
  id 'com.diffplug.spotless' version '6.25.0'
  id 'jacoco'
  id 'org.jreleaser' version '1.13.1'
}
dependencies {
  implementation enforcedPlatform("${quarkusPlatformGroupId}:${quarkusPlatformArtifactId}:${quarkusPlatformVersion}")
  implementation 'io.quarkus:quarkus-picocli'
  implementation 'io.quarkus:quarkus-arc'
  implementation 'io.quarkus:quarkus-jackson'
  implementation 'com.fasterxml.jackson.dataformat:jackson-dataformat-yaml'
  implementation 'io.quarkus:quarkus-hibernate-validator'
  implementation 'io.quarkus:quarkus-qute'
  testImplementation 'io.quarkus:quarkus-junit5'
  testImplementation 'io.quarkus:quarkus-junit5-mockito'
  testImplementation 'org.assertj:assertj-core'
  testImplementation 'net.jqwik:jqwik'
}
java { sourceCompatibility = JavaVersion.VERSION_21 }
spotless { java { googleJavaFormat() } }
jacoco { toolVersion = '0.8.12' }
```

### 2.10 `gradle.properties` (single version source)
```properties
quarkusPlatformGroupId=io.quarkus.platform
quarkusPlatformArtifactId=quarkus-bom
quarkusPlatformVersion=3.37.0
quarkusPluginId=io.quarkus
quarkusPluginVersion=3.37.0
```

### 2.11 `application.properties` (owns native flags, not build.gradle)
```properties
quarkus.native.builder-image=quay.io/quarkus/ubi9-quarkus-mandrel-builder-image:jdk-21
quarkus.native.container-build=true
quarkus.native.additional-build-args=-H:+StaticExecutableWithDynamicLibC  # mostly-static glibc (fork/exec-safe), NOT --libc=musl
quarkus.native.resources.includes=ansible/**,docker/**,templates/**,config/**,modules/**,assets/manifest.txt
quarkus.native.add-all-charsets=true
```

### 2.12 GitHub Release asset-naming contract (install.sh ⇄ jreleaser)
```
sot-linux-amd64       sot-linux-amd64.sha256   sot-linux-amd64.sig   sot-linux-amd64.pem
sot-linux-arm64       sot-linux-arm64.sha256   ...
checksums_sha256.txt  sbom.syft.json
```

### 2.13 `install.sh` core flow (bash, set -euo pipefail)
```bash
REPO=NiklasJavier/SOT
os=$(uname -s | tr A-Z a-z)                 # linux|darwin
arch=$(uname -m); case $arch in x86_64) arch=amd64;; aarch64|arm64) arch=arm64;; esac
tag=${SOT_VERSION:-$(curl -fsSL https://api.github.com/repos/$REPO/releases/latest | grep -m1 tag_name | cut -d'"' -f4)}
base=https://github.com/$REPO/releases/download/$tag
asset=sot-$os-$arch
curl -fsSL -o "$tmp/$asset"        "$base/$asset"
curl -fsSL -o "$tmp/$asset.sha256" "$base/$asset.sha256"
( cd $tmp && sha256sum -c "$asset.sha256" )      # or shasum -a 256 on darwin
command -v cosign >/dev/null && cosign verify-blob --certificate "$asset.pem" --signature "$asset.sig" \
   --certificate-identity-regexp 'https://github.com/NiklasJavier/SOT/.+' \
   --certificate-oidc-issuer https://token.actions.githubusercontent.com "$asset"
if [ -w /usr/local/bin ] || command -v sudo >/dev/null; then dest=/usr/local/bin; else dest=$HOME/.local/bin; mkdir -p $dest; fi
${SUDO} install -m755 "$tmp/$asset" "$dest/sot"
```

### 2.14 The owner one-liner (system-wide vs per-user)
```bash
curl -fsSL https://raw.githubusercontent.com/NiklasJavier/SOT/<ref>/install.sh | sudo bash   # -> /usr/local/bin/sot
curl -fsSL https://raw.githubusercontent.com/NiklasJavier/SOT/<ref>/install.sh | bash        # -> ~/.local/bin/sot
```

> No standalone `justfile` code block appears in the schemas; the full recipe set is enumerated verbatim in §3(b).

---

## 3. Full Command & Recipe Surface

### (a) `sot app …` CLI commands
- `sot app` — bare: interactive App-Selektor on a TTY, `list` when piped (never blocks).
- `sot app browse` / `sot app select` — force the interactive numbered selector.
- `sot app list [--json] [--outdated] [--role runner]` (alias `ls`) — catalog∪installed overview with AppStatus.
- `sot app search <query|term>` — fuzzy-filter the catalog non-interactively (all sources).
- `sot app info <name|id> [--json]` — full manifest, source type, installed/available versions, dependency tree.
- `sot app install <name|id>[@version]…` (aliases `add`, `i`) `[--yes] [--dry-run]` — topo-resolve `requires.apps`, dispatch InstallStrategy, record state.
- `sot app update <name|id>|--all` (alias `up`) `[--yes]` — update to latest satisfying constraint, skips pinned.
- `sot app upgrade --all` — apply every non-pinned outdated app.
- `sot app outdated [--json] [--cached]` (alias `stale`) — the monitoring surface: apps with UPDATE_AVAILABLE (network unless `--cached` reads `last-check.json`).
- `sot app status [<app>]` — dashboard/table: counts of up-to-date / outdated / pinned / unknown / broken (reads cached report by default).
- `sot app check [--quiet] [--notify] [--refresh]` — the scheduled/refresh entrypoint; refreshes cache, writes `last-check.json`, notifies on change.
- `sot app remove <name|id>` (aliases `rm`, `uninstall`) `[--yes]` — strategy.remove + SafeFsRemover + store delete.
- `sot app pin <name|id>[@version|range] [--version <v>]` / `sot app unpin <name|id>` — freeze/unfreeze from updates.
- `sot app refresh` (alias `sync`) — re-pull the catalog index from the configured remote. *(overlaps with `sot app catalog refresh` below — see §4)*
- `sot app catalog list | add <url> | remove <id> | refresh` — manage runtime catalog sources + bust cache.
- `sot ex …` — retained alias filtering `role=runner` (AAT/TID) over the same AppService.
- `sot extensions …` / `sot plugins …` — deprecated aliases forwarding to `app list`/`app install` with a one-line deprecation notice.
- Inherited automation flags (on `AppCommand`, scope=INHERIT): `--json`, `--yes/-y`, `--no-color`, `--catalog <url>`, `--dry-run`.

### (b) justfile recipes
- `just setup` — gradle wrapper bootstrap + addExtension (first-time contributors).
- `just dev` → `./gradlew quarkusDev` — live-reload dev inner loop.
- `just build` → `./gradlew build` — JVM jar + unit tests.
- `just native` → `./gradlew build -Dquarkus.native.enabled=true` — mostly-static glibc native binary.
- `just test` → `./gradlew check` — test + quarkusIntTest + JaCoCo.
- `just lint` → `./gradlew spotlessCheck && shellcheck install.sh`.
- `just fmt` → `./gradlew spotlessApply` — auto-format Java.
- `just run *ARGS` → `./gradlew quarkusRun --quarkus-args='{{ARGS}}'` — run the CLI on the JVM.
- `just install-local` → build native then `install -m755 build/sot ~/.local/bin/sot` — local dogfooding.
- `just release TAG` → `git tag {{TAG}} && git push origin {{TAG}}` — triggers release.yml.
- `just clean` → `./gradlew clean`.
- `just apps` → wrapper for `sot app list`.
- `just install <id>` → wrapper for `sot app install <id>`.
- `just check` — wraps native `sot app check --refresh` for local runs.
- `just install-timer` — installs the systemd timer/service (or cron) running `sot app check --quiet --notify` (delegated to `sot bootstrap`).
- `just run-selector` — dev-loop: `./gradlew quarkusDev --quarkus-args='app'` to drive the selector on the JVM.
- `just app-outdated` — CI helper wrapping `sot app outdated --json` for update-monitoring pipelines.

### (c) gradle / install commands
- `quarkus create cli de.jklein.sot:sot --gradle -x picocli` — scaffold the Gradle project (replaces `mvn create`).
- `./gradlew addExtension --extensions='quarkus-jackson,quarkus-hibernate-validator,quarkus-qute'` — add remaining extensions.
- `./gradlew quarkusDev` — live-reload dev.
- `./gradlew build` — JVM jar + unit tests.
- `./gradlew build -Dquarkus.native.enabled=true` — native binary in `build/`.
- `./gradlew check` — Surefire/Failsafe equivalents (test + quarkusIntTest) + JaCoCo (CI gate).
- `./gradlew spotlessCheck` / `./gradlew spotlessApply` — google-java-format check/apply.
- `./gradlew quarkusRun --quarkus-args='…'` — run the CLI on the JVM.
- `./gradlew jreleaserFullRelease` — aggregate collected native binaries → checksums + Syft SBOM + cosign + GitHub Release.
- `./gradlew clean`.
- `curl -fsSL https://raw.githubusercontent.com/NiklasJavier/SOT/<ref>/install.sh | sudo bash` — end-user system-wide install to `/usr/local/bin/sot`.
- `curl -fsSL …/install.sh | bash` — per-user install to `~/.local/bin/sot`.
- `SOT_VERSION=vX.Y.Z curl … | bash` (or first positional arg) — pin a version for reproducible installs (bypasses GitHub API).
- `sot self-update` — in-binary update reusing the same asset/verify contract.

---

## 4. Consolidated Decisions

| # | Question | Recommendation |
|---|----------|----------------|
| D1 | **Linux native linking (musl-static vs mostly-static glibc)** — the D1/Risk-1 contradiction | **Mostly-static glibc** (`-H:+StaticExecutableWithDynamicLibC`), NOT `--static --libc=musl`. The tool fork/execs ansible/git/docker; musl-static cannot. Default glibc runners; prove subprocess exec in native smoke before any release. |
| D2 | Polymorphic `source:` block across strategies in a closed-world native binary | Keep `SourceSpec` generic (`AppSourceType` + raw `JsonNode options`); each strategy binds+validates its own typed slice in `resolve()`. Avoid Jackson `@JsonTypeInfo`/`@JsonSubTypes` (forces every subtype into reflection config). |
| D3 | Does the old extension/CapabilityProvider layer survive as a separate subsystem? | **No — collapse it.** extension = an App with a `runner:` block. LocalDirectoryProvider→bundled CatalogSource, RemoteGitProvider→git CatalogSource + git-repo strategy, CapabilityService→AppService, CapabilityStateStore→InstalledAppStore. Keep old vocabulary only as aliases. |
| D4 | Bring a semver library or hand-roll comparison? | **Hand-roll** a native-safe `Version`/`VersionConstraint`/`SemVer` (semver precedence, v-prefix, prerelease ordering, ranges); `org.semver4j` (pure-Java) an acceptable fallback if range grammar grows. *(Both areas agree.)* |
| D5 | Where does the INSTALLED version come from? | A read-only `InstalledApps` port owned by the install/catalog layer (appId, version, digest, pin). Update-monitoring only reads, never writes install state — outdated is a pure function of catalog + installed state. |
| D6 | How is the periodic check scheduled (binary is not a daemon)? | Bootstrap installs a **systemd timer** (primary) invoking `sot app check --quiet --notify`, cron fallback; the binary runs once per tick and exits. No in-process scheduler/daemon. |
| D7 | Pin semantics? | EXACT pin = frozen → status PINNED (excluded from apply); RANGE pin = constraint-bounded → UPDATE_AVAILABLE only for a newer satisfying version. Pins stored in **user state** (`installed.yml`), not the catalog-owned manifest. |
| D8 | Apps with non-semver tags (calver, git sha, docker `:latest`)? | Resolvers return a digest/opaque raw string; compare by **equality** (changed vs same), never a fabricated ordering. Optional manifest `tagPattern` regex extracts a semver where one exists; else report UNKNOWN. |
| D9 | How is "latest available version" resolved without bloating strategies? | A `VersionSpec.strategy` separate from `source.type` (git-tag/github-release/compose-image-tag/apt-policy/static/script), resolved by `queryLatest()`; compare via compiled SemVer honouring `version.constraint` + pin. |
| D10 | GitHub/registry rate limits and auth? | ETag conditional GETs + TTL cache + serve-stale on 429/remaining==0; optional PAT from config/env raises the ceiling. Docker uses anonymous bearer-token flow, upgradeable to configured creds. |
| D11 | Catalog/manifest supply-chain trust (a manifest can invoke the script strategy)? | `CatalogSource` carries `CatalogTrust` (pinned git ref, or sha256/cosign for http-index); the **script strategy requires an interactive confirm** unless the catalog is signed+trusted. Owner's own catalog is the sole default trusted source. |
| D12 | `apiVersion` / manifest & config schema evolution? | Carry `apiVersion: sot.dev/v1` from day one; unknown newer fields **warn-not-fail** within a compat window. One migration policy covers both manifests and config. |
| D13 | Full-screen raw-mode TUI (JLine/lanterna) vs line-oriented selector? | **Line-oriented selector** (numbered list + BufferedReader loop + ANSI via ConsoleService). No JLine/lanterna/stty — the only trivially GraalVM-native-safe option that still gives multi-select + fuzzy filter. |
| D14 | What happens when `sot app` is run bare? | On a TTY launch the selector; when not a TTY (`System.console()==null`, piped, CI) fall back to `list`(`--json`) and never block. Interactive verbs requiring input must fail loud with a hint to pass explicit flags. |
| D15 | Is the interactive selector its own subcommand or the parent default? | **Both**: `AppCommand`'s bare Callable launches it (best UX), and an explicit `sot app browse|select` exists so scripts/help/tests can target it deterministically. |
| D16 | How are app names completed given the catalog is runtime data (closed-world)? | picocli `completionCandidates=AppNameCandidates` reading the local catalog cache at runtime; `@RegisterForReflection`. Names cannot be baked at build time. |
| D17 | Groovy vs Kotlin DSL for build.gradle? | **Groovy DSL** — what `quarkus create cli --gradle` emits by default, minimal single build file, no other Kotlin in the project. |
| D18 | Run JReleaser as a Gradle plugin or standalone CLI in CI? | **Gradle plugin** (`org.jreleaser`) via `./gradlew jreleaserFullRelease` in one aggregating release job after the matrix uploads each binary — keeps versioning in gradle.properties. |
| D19 | Should install.sh apt-install ansible/docker on Debian? | **No.** install.sh installs only the `sot` binary (assumes curl/ca-certificates). Runtime tools (git/ansible/docker) are detected/reported by `sot doctor`/`sot bootstrap`, never silently apt-installed by a piped-to-bash script. |
| D20 | How does the one-liner pin a version? | Default to GitHub API `releases/latest`; allow `SOT_VERSION=vX.Y.Z` env or first positional arg for pinned installs; the `<ref>` in the raw URL only selects which install.sh runs, decoupled from which binary it fetches. |
| D21 | cosign verification: keyless vs key-pair? | **Keyless** (Fulcio/Rekor, GitHub OIDC) — no long-lived key; install.sh verifies `certificate-identity-regexp` against the repo + the GitHub Actions OIDC issuer, treats cosign as best-effort (sha256 mandatory, cosign skipped-with-warning if absent). |
| D22 | macOS release scope for the install path? | v1: ship linux amd64/arm64 as the mandated target; keep macOS JVM/dev only. install.sh detects darwin and prints a "build from source / JVM" message rather than 404ing. |

**Flagged disagreements / overlaps to reconcile before writing the plan:**
- **⚠️ Two designs for "resolve latest version":** app-model-and-catalog folds version-checking into `InstallStrategy.queryLatest()` (the same 5 install-strategy beans), while update-monitoring designs a **separate** `VersionResolver` SPI (5 resolver beans in `de.jklein.sot.app.update`). Same responsibility, two abstractions — pick one, or define the relationship (e.g. InstallStrategy delegates to VersionResolver).
- **⚠️ Strategy-enum drift:** app-model `VersionSpec.strategy` = {git-tag, github-release, compose-image-tag, apt-policy, static, script} vs update-monitoring `UpdateStrategy` = {GITHUB_RELEASE, GIT_TAG, DOCKER_IMAGE, APT, SCRIPT}. Overlapping but not identical (compose-image-tag / apt-policy / static vs DOCKER_IMAGE / APT) — unify the vocabulary.
- **⚠️ Two `AppService` interface shapes:** app-model's (`list(EnumSet<AppStatus>)`, `install(id, Optional<version>)`, `upgradeAll()`) vs app-selector's (`catalog()`/`installed()`/`outdated()`, `install(name, InstallOptions)`, `refresh()`). Reconcile into one contract.
- **⚠️ Old-vocabulary alias semantics:** app-model keeps `sot ex` as a **live** `role=runner` filter alias; app-selector keeps `extensions`/`plugins` as **deprecated** forwarders. Decide whether legacy names are functional filters or deprecation shims.
- **Minor:** catalog refresh has two spellings — `sot app refresh`/`sync` (app-selector) vs `sot app catalog refresh` (app-model). Pick one canonical command.

---

## 5. Native-Image Considerations & Risks

### 5a. Native-image considerations (deduplicated union)
1. **Closed-world fit (core pattern):** the fixed strategy/resolver SET is compiled in via `@All List<InstallStrategy>` / `@All List<VersionResolver>` → `Map<enum,bean>` at BUILD time; WHICH apps exist stays pure runtime data (git/http manifests). No `Class.forName`, no runtime classloading — this is exactly how "deeply dynamic without recompiling" is achieved.
2. **Central `@RegisterForReflection`** in `runtime.ReflectionConfig` for every Jackson-mapped record: AppManifest, SourceSpec, VersionSpec, Requires, InstallSpec, RunnerSpec, CatalogIndex, InstalledApp, per-strategy option records, GitHub-release DTOs, Docker registry manifest/token DTOs, VersionCache/report records — or they bind empty/null.
3. **Prefer per-strategy `JsonNode` binding** over Jackson base-type `@JsonSubTypes` to keep the polymorphic-deserialisation reflection surface small and predictable.
4. **Bundled catalog** ships under `src/main/resources/apps/**/app.yml`, embedded via `quarkus.native.resources.includes` + materialised through `AssetExtractor` + `assets/manifest.txt` (native can't `Files.walk` the classpath). `assets/manifest.txt` is generated during the Gradle build (`processResources`/custom task).
5. **TLS:** `quarkus.ssl.native=true` + embedded CA truststore covering api.github.com, ghcr.io, registry-1.docker.io, Debian mirrors (shared with self-update); http-index checksum/cosign verification uses `MessageDigest` (SUN provider, default-registered).
6. **All strategies/resolvers shell out via shared `ProcessRunner`** → reinforces the mostly-static-glibc (NOT musl) constraint; musl-static would break all install/update/version-check. `ToolPreflight`/`sot doctor` confirms git/apt/docker/skopeo presence, degrades to UNKNOWN when absent.
7. **No in-binary daemon/cron:** scheduling is external systemd/cron unit files materialised by bootstrap; native invoked per tick (fast start is the whole point).
8. **No JLine/lanterna/ncurses/`stty`:** selector is plain ANSI writes + line reads — zero terminal reflection surface. `System.console()==null` under a pipe → selector must refuse (drives bare-`app`→`list` fallback).
9. `AppNameCandidates` + any picocli help/version providers need `@RegisterForReflection` (reflectively instantiated by picocli).
10. `--json` paths use the one shared build-time `YAMLMapper`/`ObjectMapper`.
11. `add-all-charsets=true` / UTF-8 so glyphs + non-ASCII app summaries and release/tag names render in the binary.
12. Version parsing is hand-rolled / reflection-free; inject a `Clock` (not System-time) for deterministic native + test behaviour. `SemVer` compare is pure Java, zero registration.
13. Catalog cache dir, `installed.yml`, and install paths are runtime-writable dirs resolved from `SotPaths` at invocation — never captured at build time.
14. Native build runs container-build via the pinned Mandrel builder image (`quarkus.native.container-build=true`) so CI runners need no local GraalVM; pin the exact builder-image tag to avoid Mandrel drift.
15. JReleaser must declare NATIVE_IMAGE/BINARY distributions (no JRE bundled); install.sh must match the single-sourced `sot-<os>-<arch>` asset-naming contract.
16. `quarkus.native.resources.includes` + `add-all-charsets` are build-behavior config → belong in `application.properties`, carried over verbatim from the Maven setup.

### 5b. Top risks, ranked (risk → mitigation)
1. **musl-static breaks fork/exec (the D1 contradiction)** — a portability-driven musl-static binary silently breaks every ansible/git/docker/apt shell-out, shipping a tool that cannot run. → Force `-H:+StaticExecutableWithDynamicLibC` (glibc); mandatory native smoke job execs a real subprocess (`git --version`) from the built binary and **gates release** (`fail-fast:false` per arch).
2. **Supply-chain / arbitrary code execution** — an untrusted catalog manifest selecting the `script` (or apt-deb) strategy runs arbitrary code on install; `curl|bash` is a tampering/MITM surface. → Sign/pin catalog sources (git ref or cosign/sha256 on http-index); script strategy needs interactive confirm unless signed+trusted; install.sh does mandatory sha256 **and** cosign keyless verify (cert-identity pinned to repo + GitHub OIDC issuer), https only.
3. **Native reflection miss binds silently to null → mis-install** — a per-strategy option record or DTO missing from ReflectionConfig deserialises to null and mis-installs. → Central ReflectionConfig lists every manifest+option+DTO record; a native integration test parses one manifest of each `source.type` and asserts full binding (release gate).
4. **`outdated()`/`checkAll()` fan-out is slow / rate-limited** — N network calls (git ls-remote, Releases API 60/hr unauth, registry, apt) exhaust limits and drag. → Virtual-thread fan-out + per-app ETag conditional GETs (304 = free) + TTL cache keyed on `lastCheckedAt` + serve-stale on remaining==0 + optional PAT + denormalised latest version in CatalogIndex for a cheap first pass.
5. **Version heterogeneity → false ordering** — many apps ship non-semver tags (calver/date/sha/`:latest`), yielding a fabricated up/down ordering. → Equality/digest comparison (changed-vs-same) when semver parse fails; optional manifest `tagPattern`; report UNKNOWN rather than guess a direction.
6. **Selector blocks/hangs non-interactively** (CI, piped stdin, `curl | sot`) hanging automation. → Detect `System.console()==null`/non-TTY → fall back to `list`; every mutating verb has a non-interactive `--yes` form so nothing needs the selector.

Further ranked risks (lower):
7. **install.sh asset-naming/verification drifts** from what Gradle/JReleaser publishes → 404s or false verify failures. → Single-source the `sot-<os>-<arch>` schema referenced by both jreleaser config and install.sh; a release-smoke job runs the published one-liner against the fresh Release in a clean Debian container.
8. **Scheduled check spams notifications** every tick. → Notify only on state-change (diff vs `last-check` report); debounce/summarise; `--quiet` default for the timer.
9. **Docker/ghcr auth token dance + mutable tags** cause wrong "up-to-date". → Anonymous bearer-token flow with configurable creds; compare manifest DIGEST not tag string for `:latest`.
10. **`sudo bash` fails / `/usr/local/bin` not writable** leaving no `sot` on PATH. → install.sh falls back to `~/.local/bin`, creates it, installs there, prints a PATH-export hint; honours existing SUDO/root; exits non-zero with a clear message.
11. **Network flakiness / offline** aborts or misleads the whole report. → Per-app failure isolation → UpdateStatus.UNKNOWN with error text; aggregate always completes; `--cached`/`status` serve `last-check.json` offline.
12. **Prerelease/draft GitHub releases** surface as latest → spurious updates. → Filter draft+prerelease by default; `includePrerelease` is an explicit per-app manifest opt-in.
13. **Manifest expressiveness gap → strategy explosion** breaking closed-world simplicity. → Keep the `script` strategy as a typed escape hatch (install/update/remove/version hooks); only promote to a first-class strategy when a pattern recurs.
14. **Dependency cycles among `requires.apps`** deadlock topo install order. → Kahn/DFS topo-sort with explicit cycle detection, failing loud with the offending chain before any strategy runs.
15. **Legacy `module.yml` mismatch** — doesn't match AppManifest; the docker module bundles 3 compose apps as one entry. → Migration explodes each docker template into its own `docker-compose` app.yml, maps ansible/sdkman modules to runner/dependency apps; warn-not-fail apiVersion window.
16. **Multi-arch native builds slow/flaky + Mandrel/Gradle drift** → non-reproducible binaries. → PRs run only JVM `check` + one linux-amd64 native smoke; full arm64+amd64 matrix only on tag; pin wrapper + quarkus platform + Mandrel builder-image; Renovate bumps must pass the native gate.
17. **GitHub API rate-limit on unauthenticated `releases/latest`** breaks unattended installs. → `SOT_VERSION` pin (arg/env) bypasses the API and hits the deterministic `/releases/download/<tag>/` URL.
18. **Raw-mode TUI temptation** pulls JLine/lanterna (native reflection + SSH/pipe breakage). → Commit to line-oriented; gate any future arrow-key nav behind an opt-in, separately native-verified module.
19. **Deprecated `extensions`/`plugins` aliases drift/duplicate logic.** → Implement as forwarders that construct+invoke the corresponding `app` subcommand; cover in `@QuarkusMainTest`.
20. **Dynamic completion reads stale/missing catalog cache.** → `AppNameCandidates` returns empty (not error) when absent; `sot app refresh` primes the cache; completion failure never aborts the command.
21. **Long install/update runs look frozen in the selector.** → Stream every step through `ProgressReporter`/`ProgressSink` (Tee to log) with per-app progress lines.
22. **Partial Maven→Gradle migration** leaves stale `mvnw`/`pom.xml`/`--libc=musl` references. → Delete pom.xml/mvnw/.mvn and grep the repo (README, workflows, pre-commit, docs) for `mvnw`/`mvn `/`pom.xml`/`--libc=musl` as a release-phase checklist.
