import js from "@eslint/js";
import { defineConfig } from "eslint/config";
import globals from "globals";
import tseslint from "typescript-eslint";
import jsconfig from "./jsconfig.json" with { type: "json" };

export default defineConfig(
  {
    ignores: [
      "skills/pr:walkthrough/assets/d3.v7.9.0.min.js",
      // Eval fixture projects contain deliberate code smells.
      "evals/refactor-opportunities/**",
    ],
  },
  js.configs.recommended,
  {
    files: ["**/*.js"],
    languageOptions: { globals: globals.node, sourceType: "commonjs" },
  },
  {
    files: ["skills/*/assets/*.js", "shared/*/assets/*.js"],
    languageOptions: { globals: globals.browser, sourceType: "script" },
  },
  {
    // Type-aware rules need each file in a TypeScript project, so they apply
    // to exactly the files jsconfig.json type-checks.
    files: jsconfig.include,
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        // Give CommonJS files their own module scope, as ESLint's default
        // parser does for sourceType "commonjs".
        ecmaFeatures: { globalReturn: true },
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: { "@typescript-eslint": tseslint.plugin },
    rules: {
      "@typescript-eslint/no-floating-promises": [
        "error",
        {
          allowForKnownSafeCalls: [
            {
              from: "package",
              name: ["describe", "it", "suite", "test"],
              package: "node:test",
            },
          ],
        },
      ],
    },
  },
  {
    linterOptions: { reportUnusedDisableDirectives: "error" },
    // `== null` is the deliberate null-or-undefined check; every other loose
    // comparison fails.
    rules: { eqeqeq: ["error", "always", { null: "ignore" }] },
  },
);
