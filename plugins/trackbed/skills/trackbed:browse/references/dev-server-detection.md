# Dev Server Detection

Auto-detect a running development server for live inspection. The detector resolves an already running local app; it does not start a server.

## Command

Run:

```bash
${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.0.1/scripts/dev-server/detect-url.sh auto --check-owner
```

`--check-owner` makes the detector check which Git checkout serves a URL it found itself, so a server from a sibling worktree or the main checkout is not tested as if it were this branch.

Optional caller inputs:

```bash
${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.0.1/scripts/dev-server/detect-url.sh --url http://localhost:3000
${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.0.1/scripts/dev-server/detect-url.sh --port 5173
${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.0.1/scripts/dev-server/detect-url.sh --launch-config web
```

## Detection Order

Use explicit caller values first. If no explicit URL or port is provided, the detector resolves candidates in this order:

1. `.claude/launch.json` `port` from the selected launch configuration, or from the only one. A declared port is final: when it does not answer, the detector reports no running server instead of trying other ports. If multiple launch configs exist and no config is selected, only configured launch ports are considered.
2. Framework config files such as `next.config.*`, `vite.config.*`, `nuxt.config.*`, and `astro.config.*`.
3. Rails `config/puma.rb`.
4. `Procfile.dev` web command.
5. `docker-compose.yml` port mappings.
6. `package.json` `dev` or `start` script flags.
7. `.env.local`, `.env.development`, then `.env` `PORT=`.
8. The Conductor workspace range, `CONDUCTOR_PORT` through `CONDUCTOR_PORT+9`, when the base port is valid. It comes before framework defaults because another workspace's server often holds a default port.
9. Framework defaults. A monorepo with several apps stops here.
10. Common-port listener scan as the final running-server fallback.

A monorepo with several apps tries the Conductor range first, then every app's port from steps 2-7 and 9 together, so one app's named port cannot hide another app's server.

Do not scan prose files such as `AGENTS.md`, `CLAUDE.md`, READMEs, or issue text for ports. Those files often contain examples and stale troubleshooting notes.

## Output Handling

- `http://...` or `https://...` -> use that as `TARGET_URL`.
- `__MULTIPLE_URLS__` followed by candidates -> ask the user to choose a URL; if the runtime is non-interactive, stop and print the candidate list.
- `__NO_RUNNING_SERVER__` -> stop and tell the user to start the dev server.
- `__FOREIGN_SERVER__` followed by `<url><TAB><checkout root>` lines -> another checkout serves every server found. Ask the user before using one, naming the URL and the directory that serves it. If the runtime cannot ask, stop with that list.
- `__UNCONFIRMED_OWNER__` followed by a URL -> use that URL as `TARGET_URL`, and report `UNVERIFIED: could not confirm which checkout serves <url>` with the run's results.
- `ERROR: ...` on stderr -> stop and show the diagnostic.

After a URL is selected, still run the normal curl health check from the parent skill. That preserves the explicit 4xx warning and 5xx hard-stop behavior.

## Maintenance Source

The implementation source of truth is `${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.0.1/scripts/dev-server/`. Keep this reference self-contained for runtime use, and update it when the detector contract changes.
