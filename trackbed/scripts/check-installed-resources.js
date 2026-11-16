const fs = require("fs");
const path = require("path");

const skillsDir = path.resolve(
  process.argv[2] || path.join(__dirname, "../skills"),
);
const pluginRoot = path.dirname(skillsDir);
const failures = [];
const fileTailPattern =
  "[A-Za-z0-9._~:/?#\\[\\]@!$&()+,;=%-]+\\.(?:md|sh|js|ts|mjs|cjs|py|json|ya?ml|txt|html|css|png|jpe?g|gif|svg|webp)";
const resourceTailPattern = `(?:references|assets|scripts)/${fileTailPattern}`;
const repositoryPathPattern = `(?:(?:docs|tests)/${fileTailPattern}|(?:AGENTS|CLAUDE|README|CONTRIBUTING)\\.md)`;
const localResourcePathPattern = `(?:\\./+)*${resourceTailPattern}`;
const parentResourcePathPattern = `(?:\\./+)*(?:\\.\\./+)+(?:[A-Za-z0-9:_.-]*/)*(?:${resourceTailPattern}|${repositoryPathPattern})`;
const skillResourcePathPattern = `(?:\\$\\{(?:CLAUDE_)?PLUGIN_ROOT\\}/)?skills/[A-Za-z0-9:_-]+/${resourceTailPattern}`;
// Capture the complete rooted resource before resolving dot segments.
const rootedResourcePathPattern = `\\$\\{(?:CLAUDE_)?PLUGIN_ROOT\\}/(?:[A-Za-z0-9:_.-]*/)*(?:${resourceTailPattern}|${repositoryPathPattern})`;
const resourceReferencePathPattern = `(?:${rootedResourcePathPattern}|${skillResourcePathPattern}|${parentResourcePathPattern}|${localResourcePathPattern})`;
const referencePattern = new RegExp(
  `(?:^|[^A-Za-z0-9_./-])(${resourceReferencePathPattern})(?![A-Za-z0-9_/-]|\\.[A-Za-z0-9_/-])`,
  "g",
);
const loadInstructionPattern =
  /\b(read|follow|load|open|use|see|run|execute|copy|populate|template|from|consult|resolve|import|extract|compare|audit|check)\b/i;
const inertFenceContextPattern =
  /\b(?:illustrative\s+)?authoring (?:example|snippet)\b/i;
const runtimeFenceContextPattern =
  /\b(read|load|open|run|execute|copy|populate|import|extract)\b/i;
const markdownResourceLinkPattern = new RegExp(
  `!?\\[[^\\]\\n]*\\]\\(\\s*<?(${resourceReferencePathPattern})(?=$|[\\s)>#?])`,
  "g",
);
const markdownResourceLinkDefinitionPattern = new RegExp(
  `^\\s*\\[[^\\]\\n]+\\]:\\s*<?(${resourceReferencePathPattern})(?=$|[\\s>#?])`,
  "g",
);
const resourceListItemPattern = new RegExp(
  `^\\s*(?:[-*]|\\|)\\s*\`?${resourceReferencePathPattern}`,
);

function walkMarkdownFiles(dir) {
  const files = [];

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "sources-snapshot") {
        continue;
      }
      files.push(...walkMarkdownFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith(".md")) {
      files.push(fullPath);
    }
  }

  return files;
}

function markdownLines(raw) {
  let activeFence = null;
  let precedingParagraph = [];
  let paragraphBreak = false;

  return raw.split(/\r?\n/).map((line) => {
    const fenceMatch = line.match(/^ {0,3}(`{3,}|~{3,})(.*)$/);

    if (fenceMatch) {
      const marker = fenceMatch[1];
      const remainder = fenceMatch[2];

      if (activeFence === null) {
        activeFence = {
          context: precedingParagraph.join("\n"),
          language: remainder.trim().split(/\s+/, 1)[0].toLowerCase(),
          length: marker.length,
          marker: marker[0],
        };
        return {
          fenceContext: "",
          fenceLanguage: "",
          inFence: false,
          text: "",
        };
      }

      if (
        marker[0] === activeFence.marker &&
        marker.length >= activeFence.length &&
        remainder.trim() === ""
      ) {
        activeFence = null;
        precedingParagraph = [];
        paragraphBreak = false;
        return {
          fenceContext: "",
          fenceLanguage: "",
          inFence: false,
          text: "",
        };
      }
    }

    if (activeFence !== null) {
      return {
        fenceContext: activeFence.context,
        fenceLanguage: activeFence.language,
        inFence: true,
        text: line,
      };
    }

    if (line.trim() === "") {
      paragraphBreak = precedingParagraph.length > 0;
    } else {
      if (paragraphBreak) {
        precedingParagraph = [];
      }
      precedingParagraph.push(line);
      paragraphBreak = false;
    }

    return {
      fenceContext: "",
      fenceLanguage: "",
      inFence: false,
      text: line,
    };
  });
}

function hasLoadInstruction(text) {
  const proseOnly = text.replace(referencePattern, (match, resourcePath) =>
    match.slice(0, -resourcePath.length),
  );

  return loadInstructionPattern.test(proseOnly);
}

function maskInlineCode(text) {
  return text.replace(/(`+)(.*?)\1/g, (match) => " ".repeat(match.length));
}

function resourcePathRange(match) {
  const start = match.index + match[0].lastIndexOf(match[1]);

  return {
    end: start + match[1].length,
    start,
  };
}

function markdownResourceLinkRanges(text) {
  const renderedText = maskInlineCode(text);

  return [
    ...renderedText.matchAll(markdownResourceLinkPattern),
    ...renderedText.matchAll(markdownResourceLinkDefinitionPattern),
  ].map(resourcePathRange);
}

function isMarkdownResourceLink(match, linkRanges) {
  const matchRange = resourcePathRange(match);

  return linkRanges.some(
    (linkRange) =>
      linkRange.start === matchRange.start && linkRange.end === matchRange.end,
  );
}

function isMarkdownFenceLanguage(language) {
  return language === "markdown" || language === "md";
}

function hasInstructionContext(lines, index, linkRanges) {
  const { fenceContext, fenceLanguage, inFence, text } = lines[index];

  if (inFence) {
    if (inertFenceContextPattern.test(fenceContext)) {
      return false;
    }

    return !isMarkdownFenceLanguage(fenceLanguage)
      ? true
      : runtimeFenceContextPattern.test(fenceContext) ||
          hasLoadInstruction(text);
  }

  return (
    hasLoadInstruction(text) ||
    resourceListItemPattern.test(text) ||
    linkRanges.length > 0
  );
}

function resolveResourcePath(skillDir, resourcePath, referenceBase = skillDir) {
  const pluginRooted = /^\$\{(?:CLAUDE_)?PLUGIN_ROOT\}\//.test(resourcePath);
  const cleanedPath = resourcePath
    .replace(/[),.;:]+$/g, "")
    .split("#")[0]
    .split("?")[0]
    .replace(/^\$\{(?:CLAUDE_)?PLUGIN_ROOT\}\/+/, "");
  const normalizedPath = path.posix.normalize(cleanedPath);
  const declaredPath = cleanedPath.replace(/^(?:\.\/+)+/, "");

  if (declaredPath.startsWith("skills/")) {
    return {
      allowedRoot: skillDir,
      resourcePath: cleanedPath,
      scope: "skill",
      targetPath: path.resolve(pluginRoot, normalizedPath),
    };
  }

  if (pluginRooted) {
    const scope = declaredPath.startsWith("shared/") ? "shared" : "scripts";

    return {
      allowedRoot: path.join(pluginRoot, scope),
      resourcePath: cleanedPath,
      scope,
      targetPath: path.resolve(pluginRoot, normalizedPath),
    };
  }

  return {
    allowedRoot: skillDir,
    resourcePath: cleanedPath,
    scope: "skill",
    targetPath: path.resolve(referenceBase, normalizedPath),
  };
}

// Claude Code substitutes ${CLAUDE_PLUGIN_ROOT} only in a skill's SKILL.md body,
// so every plugin-level path a reference file uses must also appear there.
function pluginPathsNamedIn(skillFile) {
  const named = new Set();
  const pattern = new RegExp(rootedResourcePathPattern, "g");

  for (const match of fs.readFileSync(skillFile, "utf8").matchAll(pattern)) {
    named.add(
      resolveResourcePath(path.dirname(skillFile), match[0]).targetPath,
    );
  }

  return named;
}

function isWithin(allowedRoot, targetPath) {
  const relativePath = path.relative(allowedRoot, targetPath);

  return (
    relativePath === "" ||
    (!relativePath.startsWith(`..${path.sep}`) &&
      relativePath !== ".." &&
      !path.isAbsolute(relativePath))
  );
}

const skillDirs = fs
  .readdirSync(skillsDir, { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .sort((a, b) => a.name.localeCompare(b.name));

for (const skill of skillDirs) {
  const skillDir = path.join(skillsDir, skill.name);
  const skillFile = path.join(skillDir, "SKILL.md");
  const markdownFiles = walkMarkdownFiles(skillDir).sort();
  const namedPluginPaths = fs.existsSync(skillFile)
    ? pluginPathsNamedIn(skillFile)
    : new Set();

  for (const file of markdownFiles) {
    const relativeFile = path.relative(pluginRoot, file);
    const lines = markdownLines(fs.readFileSync(file, "utf8"));

    lines.forEach((line, index) => {
      const matches = [...line.text.matchAll(referencePattern)];
      const linkRanges = markdownResourceLinkRanges(line.text);

      if (
        matches.length === 0 ||
        !hasInstructionContext(lines, index, linkRanges)
      ) {
        return;
      }

      for (const match of matches) {
        const referenceBase = isMarkdownResourceLink(match, linkRanges)
          ? path.dirname(file)
          : skillDir;
        const { allowedRoot, resourcePath, scope, targetPath } =
          resolveResourcePath(skillDir, match[1], referenceBase);

        if (!isWithin(allowedRoot, targetPath)) {
          failures.push(
            `${relativeFile}:${index + 1}: escapes ${scope === "skill" ? "skill" : `plugin ${scope}`} directory: ${resourcePath}`,
          );
        } else if (!fs.existsSync(targetPath)) {
          failures.push(
            `${relativeFile}:${index + 1}: missing ${resourcePath}`,
          );
        } else if (
          scope !== "skill" &&
          file !== skillFile &&
          !namedPluginPaths.has(targetPath)
        ) {
          failures.push(
            `${relativeFile}:${index + 1}: ${resourcePath} is not named in SKILL.md, the only file where Claude Code substitutes \${CLAUDE_PLUGIN_ROOT}`,
          );
        }
      }
    });
  }
}

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exit(1);
}
