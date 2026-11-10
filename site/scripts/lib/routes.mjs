import path from "node:path";
import { DEFAULT_BRANCH, HOME_PAGE, README_PATH, REPO_URL } from "./config.mjs";
import { isAbsoluteUrl } from "./markdown.mjs";

export function pageUrl(slug, anchor = null, currentPage = null) {
  if (anchor && slug === currentPage) return `#${anchor}`;
  const pathname = slug === HOME_PAGE ? "/" : `/${slug}/`;
  return anchor ? `${pathname}#${anchor}` : pathname;
}

function encodeRepoPath(repoPath) {
  return encodeURI(repoPath).replaceAll("(", "%28").replaceAll(")", "%29");
}

const GITHUB_VIEWS = { file: "blob", directory: "tree", image: "raw" };

/**
 * A repository path on GitHub as it is at `ref` (a branch, tag, or commit).
 * `kind` is "file", "directory", or "image" (the file's bytes, for `<img>`).
 */
export function githubUrl(
  repoPath,
  { ref = DEFAULT_BRANCH, kind = "file", anchor = null } = {},
) {
  const url = `${REPO_URL}/${GITHUB_VIEWS[kind]}/${ref}/${encodeRepoPath(repoPath)}`;
  return anchor ? `${url}#${anchor}` : url;
}

export function githubEditUrl(repoPath) {
  return `${REPO_URL}/edit/${DEFAULT_BRANCH}/${encodeRepoPath(repoPath)}`;
}

function decodeLinkPath(rawPath) {
  try {
    return decodeURIComponent(rawPath);
  } catch {
    throw new Error(`link has a malformed percent-escape: ${rawPath}`);
  }
}

/**
 * Build the function that turns a link written in a repository file into the
 * link the site should carry: a site page when the target is on the site,
 * otherwise the file on GitHub. A link whose target does not exist throws, so
 * link rot in the sources fails the build instead of shipping. An image always
 * points at the file's bytes on GitHub.
 *
 * - `pathKind(repoPath)` returns "file", "directory", or null.
 * - `filePages` maps a repository file to the page that renders all of it.
 * - `readmeAnchors` maps a README anchor to `{ page, anchor }` (see readme.mjs).
 * - `sourceRef` is the branch, tag, or commit that GitHub links point at.
 *
 * Errors do not name the source file; the caller knows it and adds it.
 */
export function createLinkResolver({
  pathKind,
  filePages,
  readmeAnchors,
  sourceRef = DEFAULT_BRANCH,
}) {
  return function resolveLink(url, { sourceFile, currentPage, image = false }) {
    if (isAbsoluteUrl(url)) return url;

    const hashIndex = url.indexOf("#");
    const rawPath = hashIndex === -1 ? url : url.slice(0, hashIndex);
    const anchor = hashIndex === -1 ? null : url.slice(hashIndex + 1) || null;

    let target = sourceFile;
    if (rawPath !== "") {
      const linked = decodeLinkPath(rawPath);
      // GitHub reads a leading "/" as the repository root.
      target = linked.startsWith("/")
        ? linked.slice(1)
        : path.posix.join(path.posix.dirname(sourceFile), linked);
      target = path.posix.normalize(target).replace(/\/$/, "");
    }
    const kind = target.startsWith("..") ? null : pathKind(target);
    if (kind === null) {
      throw new Error(`link target does not exist: ${url}`);
    }
    if (image) return githubUrl(target, { ref: sourceRef, kind: "image" });

    if (target === README_PATH) {
      if (anchor === null) return pageUrl(HOME_PAGE);
      const entry = readmeAnchors.get(anchor.toLowerCase());
      if (!entry) {
        throw new Error(`README has no heading for: ${url}`);
      }
      return entry.page === null
        ? githubUrl(README_PATH, { ref: sourceRef, anchor })
        : pageUrl(entry.page, entry.anchor, currentPage);
    }

    const page = filePages.get(target);
    if (page !== undefined) return pageUrl(page, anchor, currentPage);
    return githubUrl(target, { ref: sourceRef, kind, anchor });
  };
}
