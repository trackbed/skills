import GithubSlugger from "github-slugger";
import { fromMarkdown } from "mdast-util-from-markdown";
import { gfmFromMarkdown } from "mdast-util-gfm";
import { toString } from "mdast-util-to-string";
import { gfm } from "micromark-extension-gfm";
import { parse as parseYaml } from "yaml";

export { toString as nodeText };

export function parseMarkdown(text) {
  return fromMarkdown(text, {
    extensions: [gfm()],
    mdastExtensions: [gfmFromMarkdown()],
  });
}

/** Depth-first walk that hands each node its ancestors, outermost first. */
export function walk(node, visit, ancestors = []) {
  visit(node, ancestors);
  if (!node.children) return;
  const next = [...ancestors, node];
  for (const child of node.children) walk(child, visit, next);
}

/**
 * Every heading in document order with the anchor GitHub gives it, including
 * the `-1`, `-2` suffixes GitHub adds to repeated headings.
 */
export function listHeadings(text, tree = parseMarkdown(text)) {
  const slugger = new GithubSlugger();
  const headings = [];
  walk(tree, (node) => {
    if (node.type !== "heading") return;
    const title = toString(node);
    headings.push({
      depth: node.depth,
      title,
      slug: slugger.slug(title),
      start: node.position.start.offset,
      end: node.position.end.offset,
    });
  });
  return headings;
}

export function splitFrontmatter(text) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(text);
  if (!match) return { data: {}, body: text };
  return { data: parseYaml(match[1]) ?? {}, body: text.slice(match[0].length) };
}

/** Apply non-overlapping `{ start, end, replacement }` edits to `text`. */
function applyEdits(text, edits) {
  const ordered = [...edits].sort((a, b) => a.start - b.start || a.end - b.end);
  let result = "";
  let cursor = 0;
  for (const edit of ordered) {
    if (edit.start < cursor) {
      throw new Error(
        `Two rewrites overlap at ${JSON.stringify(text.slice(edit.start, edit.end))}; move the link or code span out of the title or onto one line`,
      );
    }
    result += text.slice(cursor, edit.start) + edit.replacement;
    cursor = edit.end;
  }
  return result + text.slice(cursor);
}

const ABSOLUTE_URL = /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i;

export function isAbsoluteUrl(url) {
  return ABSOLUTE_URL.test(url);
}

/** Where a link, image, or definition's destination sits in the source text. */
function destinationRange(text, node) {
  const nodeStart = node.position.start.offset;
  const nodeEnd = node.position.end.offset;
  let start;
  let limit = nodeEnd;

  if (node.type === "definition") {
    const label = /^\[(?:\\.|[^\]\\])*\]:[ \t\r\n]*/.exec(
      text.slice(nodeStart, nodeEnd),
    );
    if (!label) return null;
    start = nodeStart + label[0].length;
  } else {
    // `[text](destination "title")`: the destination follows the last child.
    const lastChild = node.children?.at(-1);
    const open =
      node.type === "image"
        ? // Search inside the image only: an enclosing link's own `](` starts at nodeEnd.
          text.lastIndexOf("](", nodeEnd - 2)
        : text.indexOf(
            "](",
            lastChild ? lastChild.position.end.offset : nodeStart,
          );
    if (open < nodeStart || open >= nodeEnd || text[nodeEnd - 1] !== ")") {
      return null;
    }
    start = open + 2;
    limit = nodeEnd - 1;
  }

  while (start < limit && /\s/.test(text[start])) start += 1;
  let end = start;
  if (text[start] === "<") {
    end = text.indexOf(">", start) + 1;
    if (end === 0 || end > limit) return null;
  } else {
    while (end < limit && !/\s/.test(text[end])) end += 1;
  }
  if (end <= start) return null;
  // The scan above is simpler than Markdown's grammar. Check it found exactly
  // the destination the parser read, so an unusual form fails instead of
  // being rewritten in the wrong place.
  const raw = text.slice(start, end);
  const written = raw.startsWith("<") ? raw.slice(1, -1) : raw;
  const unescaped = written.replace(/\\([!-/:-@[-`{-~])/g, "$1");
  return unescaped === node.url ? { start, end } : null;
}

const ALERTS = {
  NOTE: "note",
  TIP: "tip",
  IMPORTANT: "note[Important]",
  WARNING: "caution[Warning]",
  CAUTION: "danger[Caution]",
};

/** Turn a GitHub alert (`> [!NOTE]`) into the Starlight aside it reads as. */
function alertEdits(text, lineStarts, node) {
  const firstLine = node.position.start.line;
  const lastLine = node.position.end.line;
  const lineText = (line) => {
    const start = lineStarts[line - 1];
    const end = line < lineStarts.length ? lineStarts[line] - 1 : text.length;
    return { start, text: text.slice(start, end).replace(/\r$/, "") };
  };

  const marker = lineText(firstLine);
  const match = /^> ?\[!([A-Z]+)\][ \t]*$/.exec(marker.text);
  if (!match || !ALERTS[match[1]]) return [];

  const edits = [
    {
      start: marker.start,
      end: marker.start + marker.text.length,
      replacement: `:::${ALERTS[match[1]]}`,
    },
  ];
  for (let line = firstLine + 1; line <= lastLine; line += 1) {
    const current = lineText(line);
    const prefix = /^> ?/.exec(current.text);
    if (prefix) {
      edits.push({
        start: current.start,
        end: current.start + prefix[0].length,
        replacement: "",
      });
    }
  }
  const end = node.position.end.offset;
  edits.push({ start: end, end, replacement: "\n:::" });
  return edits;
}

const RELATIVE_HTML_LINK =
  /\b(?:href|src)\s*=\s*["'](?![a-z][a-z0-9+.-]*:|\/\/)/i;

/**
 * Rewrite one Markdown source into the text of a site page. Edits are spliced
 * into the original text by source position, so everything that is not
 * rewritten stays byte-for-byte what the source says.
 *
 * - `resolveLink(url, { image })` returns the destination to use for a link
 *   or, when `image` is true, for an image.
 * - `linkForCode(value)` returns a URL to link an inline code span to, or null.
 * - `headingShift` moves every heading by that many levels.
 * - `dropTitle` removes the single `#` heading and returns its text as `title`.
 */
export function transformMarkdown(
  text,
  {
    resolveLink,
    linkForCode = () => null,
    headingShift = 0,
    dropTitle = false,
  },
) {
  const tree = parseMarkdown(text);
  const lineStarts = [0];
  for (
    let index = text.indexOf("\n");
    index !== -1;
    index = text.indexOf("\n", index + 1)
  ) {
    lineStarts.push(index + 1);
  }

  const edits = [];
  let title = null;

  walk(tree, (node, ancestors) => {
    const start = node.position?.start.offset;
    const end = node.position?.end.offset;

    switch (node.type) {
      case "link":
      case "image":
      case "definition": {
        const destination = resolveLink(node.url, {
          image: node.type === "image",
        });
        if (destination === node.url) break;
        const range = destinationRange(text, node);
        if (!range) {
          throw new Error(`Cannot rewrite the link to ${node.url}`);
        }
        edits.push({ ...range, replacement: destination });
        break;
      }
      case "inlineCode": {
        const inLinkOrHeading = ancestors.some((ancestor) =>
          ["link", "linkReference", "heading"].includes(ancestor.type),
        );
        const url = inLinkOrHeading ? null : linkForCode(node.value);
        if (url) {
          edits.push({
            start,
            end,
            replacement: `[${text.slice(start, end)}](${url})`,
          });
        }
        break;
      }
      case "heading": {
        const hashes = /^#{1,6}(?=[ \t]|$)/.exec(text.slice(start, end));
        if (!hashes) {
          throw new Error(`Only "#" headings are supported: ${toString(node)}`);
        }
        if (dropTitle && node.depth === 1) {
          if (title !== null) {
            throw new Error(`More than one "#" heading: ${toString(node)}`);
          }
          title = toString(node);
          const lineEnd = text[end] === "\n" ? end + 1 : end;
          edits.push({ start, end: lineEnd, replacement: "" });
          break;
        }
        const depth = Math.min(6, Math.max(1, node.depth + headingShift));
        if (depth !== node.depth) {
          edits.push({
            start,
            end: start + hashes[0].length,
            replacement: "#".repeat(depth),
          });
        }
        break;
      }
      case "blockquote": {
        if (ancestors.length === 1 && node.position.start.column === 1) {
          edits.push(...alertEdits(text, lineStarts, node));
        }
        break;
      }
      case "html": {
        if (RELATIVE_HTML_LINK.test(node.value)) {
          throw new Error(
            `Relative links inside raw HTML are not supported: ${node.value}`,
          );
        }
        break;
      }
      default:
    }
  });

  return { text: applyEdits(text, edits), title };
}
