# Constraint Mechanisms

Use this catalog in Step 3 to find the strongest mechanism the repository can run. Prefer tools that are already configured; the entries below are options to look for, not a list to install. Confirm a tool's version before you rely on a feature that names one.

## Detect What the Repository Runs

Look for configuration before choosing a rung:

- **TypeScript and JavaScript:** `tsconfig*.json`, `eslint.config.*` or `.eslintrc*`, `biome.json` or `biome.jsonc`, `package.json` scripts, `.dependency-cruiser.*`, and Nx `project.json` targets.
- **Python:** `pyproject.toml` sections such as `[tool.ruff]`, `[tool.mypy]`, `[tool.pyright]`, `[tool.basedpyright]`, and `[tool.importlinter]`, plus `ruff.toml`, `mypy.ini`, `setup.cfg`, and `.importlinter`.
- **Go:** `.golangci.yml`, `.golangci.yaml`, or `.golangci.toml`.
- **Rust:** `clippy.toml` and the `[lints]` table in `Cargo.toml`.
- **JVM:** Gradle or Maven configuration for Error Prone, Checkstyle, PMD, detekt, ktlint, Android Lint, and ArchUnit or Konsist test dependencies.
- **.NET:** `.editorconfig`, `Directory.Build.props`, `BannedSymbols.txt`, and analyzer package references.
- **Styles:** `.stylelintrc*` or `stylelint.config.*`.
- **Cross-language:** `sgconfig.yml` for ast-grep, `.semgrep.yml` or `.semgrep/`, `.pre-commit-config.yaml`, `lefthook.yml`, and CI workflow files.

Then confirm which of these the standard verification command and CI actually execute. A configured tool that nothing runs gives no protection until Step 5 wires it in.

## TypeScript and JavaScript

- **Unrepresentable:** a branded type such as `type UserId = string & { readonly __brand: 'UserId' }` with a single constructor; a discriminated union with an exhaustive `switch` that assigns the leftover case to `never`; required instead of optional parameters; `readonly` data; a `package.json` `exports` map that hides internal subpaths. A `@deprecated` JSDoc tag only strikes through the name in editors, so pair it with a lint rule that reports deprecated usage.
- **Compiler:** `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noImplicitReturns`, and `noFallthroughCasesInSwitch`.
- **Lint configuration:** ESLint `no-restricted-imports` (`paths` and `patterns`, each with a `message`), `no-restricted-syntax` (an AST selector with a `message`), `no-restricted-properties`, and `no-restricted-globals`; `@typescript-eslint/no-restricted-types` and the type-aware `@typescript-eslint/no-deprecated`; module boundaries through `import/no-restricted-paths` zones, `@nx/enforce-module-boundaries`, or dependency-cruiser `forbidden` rules. Biome provides `noRestrictedImports` and `noRestrictedGlobals`.
- **Structural rule:** a local ESLint rule registered as an inline plugin in the flat config and tested with `RuleTester`, or an ast-grep or Semgrep rule.
- **Tests:** a type test that marks the forbidden usage with `// @ts-expect-error`, which fails the build once the line stops erroring, or `expectTypeOf`; an invariant test in the existing runner.
- **Baseline:** ESLint 9.24+ bulk suppressions (`eslint --suppress-rule <rule>` or `--suppress-all` writes `eslint-suppressions.json`), otherwise per-path overrides in the config.
- **Suppression guard:** set `linterOptions.reportUnusedDisableDirectives` to `"error"` so a stale `eslint-disable` fails; set `linterOptions.noInlineConfig` when inline disables should not work at all. With bulk suppressions, ESLint already exits non-zero on unused entries, so treat `--pass-on-unpruned-suppressions` in a script as a bypass. typescript-eslint `ban-ts-comment` reports `@ts-ignore` and, by default, a `@ts-expect-error` without a description.

## Python

- **Unrepresentable:** `NewType` or small value classes for identifiers and units; `Literal` or `Enum` with `assert_never` for exhaustive handling (`typing` in Python 3.11+, otherwise `typing_extensions`); `Final` and `@final`; frozen dataclasses; leading-underscore modules with `__all__` for private surfaces; `@deprecated` (`warnings` in Python 3.13+, otherwise `typing_extensions`) so type checkers flag callers.
- **Type checker:** mypy `strict = true` or targeted options such as `disallow_untyped_defs`, `warn_unreachable`, and `strict_equality`, ratcheted per module with `[[tool.mypy.overrides]]`; Pyright or basedpyright `strict` mode or individual `report*` settings.
- **Lint configuration:** Ruff banned APIs under `[tool.ruff.lint.flake8-tidy-imports.banned-api]`, each with a `msg` (rule `TID251`), and `banned-module-level-imports` (rule `TID253`); import-linter `forbidden`, `layers`, and `independence` contracts, checked by `lint-imports`.
- **Structural rule:** Ruff has no plugin API, so use ast-grep or Semgrep, a Pylint or Flake8 plugin when the repository already runs one, or a pytest test that walks the `ast` module.
- **Tests:** pytest invariant tests and architecture tests through import-linter or an `ast` walk.
- **Baseline:** `ruff check --add-noqa` for existing sites, Ruff `per-file-ignores`, mypy per-module overrides, or basedpyright `--writebaseline`.
- **Suppression guard:** Ruff `RUF100` reports unused `noqa` directives and `PGH004` reports blanket `noqa` without a rule code; mypy `warn_unused_ignores` reports unneeded `# type: ignore` comments, and enabling the `ignore-without-code` error code through `enable_error_code` requires each one to name a code.

## Go

- **Unrepresentable:** `internal/` packages, which the compiler refuses to import from outside the parent tree; unexported struct fields behind a validating constructor; defined types such as `type UserID string`; sealed interfaces with an unexported method.
- **Compiler and vet:** `go vet` analyzers that the build already runs.
- **Lint configuration (golangci-lint):** `forbidigo` forbids identifiers by pattern, each with a `msg`; `depguard` denies imports, each with a `desc`; `exhaustive` requires complete enum switches; `errorlint`, `wrapcheck`, and `gomodguard` cover common error and dependency mistakes.
- **Structural rule:** a custom `go/analysis` analyzer loaded as a golangci-lint module plugin or run through `go vet -vettool`.
- **Tests:** table tests, or an architecture test that reads `go list -deps -json` output.
- **Baseline:** golangci-lint `issues.new-from-rev` or `issues.new-from-merge-base` reports only new issues; use `//nolint:<linter> // <reason>` for individual sites.
- **Suppression guard:** the `nolintlint` linter with `allow-unused: false`, `require-specific: true`, and `require-explanation: true` rejects unused, blanket, and unexplained `//nolint` directives.

## Rust

- **Unrepresentable:** newtypes and private fields behind smart constructors; the typestate pattern; `#[non_exhaustive]`; `pub(crate)` visibility; `#[must_use]`; `#[deprecated]`.
- **Compiler:** the `[lints]` table in `Cargo.toml`, such as `unsafe_code = "forbid"` and Clippy group levels, or crate-level `#![deny(...)]`.
- **Lint configuration:** Clippy `disallowed-methods`, `disallowed-types`, and `disallowed-macros` in `clippy.toml`, each with a `reason`.
- **Structural rule:** a Dylint library or an ast-grep rule.
- **Tests:** `trybuild` compile-fail tests or `compile_fail` doctests pin that the mistake does not compile.
- **Baseline:** `#[expect(clippy::<lint>, reason = "...")]` at existing sites (Rust 1.81+), which warns once the suppression becomes unnecessary.
- **Suppression guard:** set Clippy `allow_attributes` and `allow_attributes_without_reason` and the rustc lint `unfulfilled_lint_expectations` to `deny`, so every suppression is an `#[expect]` with a `reason` and a stale one fails the build.

## Java and Kotlin

- **Unrepresentable:** sealed classes and interfaces with exhaustive `switch` or `when`; records and value classes; package-private or Kotlin `internal` visibility; JPMS `module-info.java` `exports`.
- **Lint configuration:** Checkstyle `IllegalImport` and `ImportControl`; PMD rules; detekt `ForbiddenImport` and `ForbiddenMethodCall`, each with a `reason`; Error Prone checks raised to errors.
- **Structural rule:** an Error Prone `BugChecker`, a PMD XPath rule, a detekt or ktlint custom rule set, or an Android Lint check.
- **Tests:** ArchUnit or Konsist architecture tests.
- **Baseline:** ArchUnit `FreezingArchRule`, detekt `baseline.xml`, Android Lint `lint-baseline.xml`, or Checkstyle suppressions.

## C# and .NET

- **Unrepresentable:** `internal` types with `InternalsVisibleTo` for tests; `required` members; records; nullable reference types (`<Nullable>enable</Nullable>`); `[Obsolete("Use X instead", error: true)]` once callers have migrated.
- **Compiler and analyzers:** `<TreatWarningsAsErrors>` or `.editorconfig` entries such as `dotnet_diagnostic.<ID>.severity = error`; `Microsoft.CodeAnalysis.BannedApiAnalyzers` with `BannedSymbols.txt` lines such as `P:System.DateTime.Now;Use TimeProvider instead` (rule `RS0030`).
- **Structural rule:** a custom Roslyn analyzer.
- **Tests:** NetArchTest or ArchUnitNET architecture tests.
- **Baseline:** `[SuppressMessage]` or `#pragma warning disable` with a justification at existing sites, or folder-scoped `.editorconfig` severity.

## Styles

- **Lint configuration (Stylelint):** `color-no-hex` or `declaration-property-value-disallowed-list` to force design tokens; `property-disallowed-list`, `function-disallowed-list`, `unit-disallowed-list`, and `selector-max-id`; the `stylelint-declaration-strict-value` plugin to require variables for chosen properties.

## Cross-Language Structural Search

- **ast-grep:** YAML rules with `rule`, `message`, `note`, and an optional `fix`, run by `ast-grep scan`. `ast-grep test` checks `valid` and `invalid` cases, which keeps the red and green runs as permanent tests.
- **Semgrep:** YAML rules with `pattern`, `pattern-not`, `message`, and an optional `fix`. `semgrep --test` checks `# ruleid:` and `# ok:` annotations, and `--baseline-commit` reports only new findings.
- **Text-search scripts:** the weakest option, because they break on formatting and miss aliases. Use them only for literal strings, such as a forbidden flag or URL.

## Repository-Shape Checks

Use a test or script when no single file shows the mistake:

- **Generated artifacts match their source:** regenerate in CI and fail on `git diff --exit-code`.
- **Paired files exist:** assert that every X has its Y, such as a rollback for every migration or a test for every route.
- **Registries stay complete:** enumerate implementations and assert that each one is registered.

## Guard the Check Against Bypass

Use this catalog in Step 5 to block each way a check can go green without a fix. Prefer a guard the repository already runs, and report a route with no guard as a follow-up.

- **Inline disable:** the suppression guards above, enabled and raised to error, keep suppressions specific, explained, and pruned once stale, but none rejects a new disable of the rule that is in use. Only ESLint `noInlineConfig`, a `forbid` lint level in Rust, or a check that fails when a suppression naming the new rule appears blocks this route.
- **New baseline entry:** the shrink-only check from Step 2.
- **Widened exclude or path filter:** a test that places violating input at a path inside the governed scope, for example by copying a fixture into place, runs the real entry point with the repository's configuration, and expects a non-zero exit with the diagnostic. It catches only an exclude that covers that path. A rule-unit test such as `RuleTester` never reads the configuration, so it does not count.
- **Lowered severity:** an assertion that the rule is configured at error level, or the entry-point test above, which requires a non-zero exit rather than a warning. A rule-unit test ignores the configured severity.
- **Deleted or emptied fixture:** a test that names the fixture paths it expects and fails when one is missing or no longer fails the check.

## Agent Hooks

Use a hook only for agent actions, such as running a command or editing a protected path. Claude Code `PreToolUse` hooks in project settings can block a tool call and return the reason to the agent, and other hosts offer equivalents. A hook does not protect humans, CI, or other agent hosts, so pair it with a repository check whenever the action leaves a trace in files.
