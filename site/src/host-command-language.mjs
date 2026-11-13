import { HOST_COMMAND_LANGUAGE } from "../scripts/lib/markdown.mjs";

/**
 * A TextMate grammar for commands typed into the host rather than a shell:
 * `/trackbed:pr:create --draft <branch>   # comment`. Shell highlighting reads
 * the leading slash as a path and draws the block as a terminal window.
 */
export const hostCommandLanguage = {
  name: HOST_COMMAND_LANGUAGE,
  scopeName: `source.${HOST_COMMAND_LANGUAGE}`,
  patterns: [
    {
      match: "(^|\\s)(#.*)$",
      captures: { 2: { name: "comment.line.number-sign" } },
    },
    { match: "^\\s*[/$][A-Za-z][\\w:.-]*", name: "entity.name.function" },
    {
      match: "(^|[\\s\\[|])(--[a-z][a-z0-9-]*)",
      captures: { 2: { name: "constant.other.option" } },
    },
    { match: "<[^<>\\s][^<>]*>", name: "string.unquoted.placeholder" },
  ],
};
