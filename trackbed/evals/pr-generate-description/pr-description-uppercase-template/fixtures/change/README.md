# docs-site-tools

Helpers for the documentation site build.

## slugify

`slugify(title)` turns a page title into the last part of its URL:

```ts
slugify("Getting started"); // "getting-started"
slugify("Crème brûlée"); // "creme-brulee"
```

Accented letters keep their base letter. Letters with no base letter, such as
`ø`, still become a hyphen.
