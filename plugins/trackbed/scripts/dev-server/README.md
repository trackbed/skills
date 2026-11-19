# Shared Dev-server Detection

These scripts provide one detection contract for browser-facing workflows. They are used when a skill receives `auto` and needs to discover a running local app. Explicit user-provided URLs and ports always win.

## Scripts

- `detect-url.sh` resolves a reachable URL or emits a sentinel.
- `detect-project-type.sh` detects `rails`, `next`, `vite`, `nuxt`, `astro`, `remix`, `sveltekit`, `procfile`, `multiple`, or `unknown`.
- `resolve-package-manager.sh` detects the JS package manager from lockfiles and emits the dev command tail.
- `read-launch-json.sh` reads `.claude/launch.json` and emits a selected config as JSON.
- `resolve-port.sh` resolves the intended dev-server port. With `--no-default`, it prints nothing when only a framework default applies, including a port that project files name but that equals the default.

## URL Detection Contract

Run the wrapper from the plugin root:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/dev-server/detect-url.sh auto
${CLAUDE_PLUGIN_ROOT}/scripts/dev-server/detect-url.sh auto --check-owner
${CLAUDE_PLUGIN_ROOT}/scripts/dev-server/detect-url.sh --url http://localhost:3000
${CLAUDE_PLUGIN_ROOT}/scripts/dev-server/detect-url.sh --port 5173
${CLAUDE_PLUGIN_ROOT}/scripts/dev-server/detect-url.sh --launch-config web
```

Stdout is one of:

- `http://localhost:<port>` or an explicit reachable URL.
- `__NO_RUNNING_SERVER__` when nothing responds.
- `__MULTIPLE_URLS__` followed by one URL per line when discovery is ambiguous.

With `--check-owner`, a URL the detector found itself is checked against the Git checkout that serves it. Explicit `--url` and `--port` values are never checked. The detector finds the process listening on the port with `lsof` (or `ss` and `/proc` on Linux) and reads its working directory:

- A server in this checkout, including a subdirectory such as a monorepo app, prints its URL as usual.
- When every hit is served from another checkout, such as a sibling worktree or Conductor workspace or the main checkout, stdout is `__FOREIGN_SERVER__` followed by one `<url><TAB><checkout root>` line per hit.
- When only some hits are foreign, they are dropped before counting, with a `NOTE:` line on stderr for each.
- When the serving checkout cannot be determined, for example a container-published port, a server outside any Git checkout, or no inspection tool, a single hit prints `__UNCONFIRMED_OWNER__` followed by the URL.

Diagnostics and operational errors are printed to stderr.

## Precedence

Port resolution uses this order:

1. Explicit URL or `--port`.
2. `.claude/launch.json` `port` from the selected configuration, or from the only configuration. A declared port is final: when it does not answer, the detector prints `__NO_RUNNING_SERVER__` instead of trying other ports. If multiple launch configs exist and no `--launch-config` is provided, only configured launch ports are considered so discovery does not fall through to unrelated local servers.
3. Framework config files such as `next.config.*`, `vite.config.*`, `nuxt.config.*`, and `astro.config.*`.
4. Rails `config/puma.rb`.
5. `Procfile.dev` web command.
6. `docker-compose.yml` port mappings.
7. `package.json` `dev` or `start` script flags.
8. `.env.local`, `.env.development`, then `.env` `PORT=`.
9. The Conductor workspace range, `CONDUCTOR_PORT` through `CONDUCTOR_PORT+9`, when the base port is valid. It comes before framework defaults because another workspace's server often holds a default port.
10. Framework defaults. A monorepo with several apps stops here.
11. Common-port listener scan as a final running-server fallback.

A monorepo with several apps tries the Conductor range first, then every app's port from steps 3-8 and 10 together, so one app's named port cannot hide another app's server.

Do not scan prose files such as `AGENTS.md`, `CLAUDE.md`, READMEs, or issue text for ports. Those files often contain examples and stale troubleshooting notes.

## Source

`detect-project-type.sh`, `resolve-package-manager.sh`, `read-launch-json.sh`, and `resolve-port.sh` are adapted from `ce-polish` in EveryInc's `compound-engineering-plugin`, reviewed at commit `6f9ab03a031c054a8046659926251fb6c149269f`. Upstream license: MIT; the complete notice ships as `EveryInc-LICENSE` in this directory, and `sources.yaml` records each copied file's upstream path and commit. `python3 trackbed/scripts/lint-skill-contracts.py` checks that manifest by the same source-provenance rules as skill manifests. `detect-url.sh` is original code that follows ce-polish's guidance.
