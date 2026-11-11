// Combining marks left behind once a letter is split from its accent.
const COMBINING_MARKS = /[̀-ͯ]/g;

export function slugify(title: string): string {
  return title
    .normalize("NFKD")
    .replace(COMBINING_MARKS, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
